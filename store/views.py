# store/views.py
from decimal import Decimal
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny, BasePermission
from rest_framework.views import APIView
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate, get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters import rest_framework as django_filters
from django.db.models import Q
from django.conf import settings
import telegram
import logging

from .models import Category, Product, ProductImage, WoodType, Grade, Cart, CartItem, Order, OrderItem
from .serializers import (
    CategorySerializer, ProductSerializer, ProductImageSerializer,
    WoodTypeSerializer, GradeSerializer, CartSerializer, CartItemSerializer,
    OrderSerializer, OrderItemSerializer, UserSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)

class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_staff

class UserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        serializer = UserSerializer(user)
        return Response(serializer.data)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]

class WoodTypeViewSet(viewsets.ModelViewSet):
    queryset = WoodType.objects.all()
    serializer_class = WoodTypeSerializer
    permission_classes = [AllowAny]

class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer
    permission_classes = [AllowAny]

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    category = django_filters.NumberFilter(field_name="category__id")
    wood_type = django_filters.CharFilter(field_name="wood_type__name")
    grade = django_filters.CharFilter(field_name="grade__name")
    width = django_filters.NumberFilter(field_name="width")
    thickness = django_filters.NumberFilter(field_name="thickness")
    length = django_filters.NumberFilter(field_name="length")
    search = django_filters.CharFilter(method='filter_search')
    ordering = django_filters.OrderingFilter(
        fields=(
            ('name', 'name'),
            ('price', 'price'),
        )
    )
    is_active = django_filters.BooleanFilter(field_name='is_active', initial=True)

    class Meta:
        model = Product
        fields = ['category', 'wood_type', 'grade', 'width', 'thickness', 'length', 'min_price', 'max_price', 'is_active']

    def filter_search(self, queryset, name, value):
        return queryset.filter(name__icontains=value)

class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = ProductFilter
    permission_classes = [AllowAny]

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        
        active_order_items = OrderItem.objects.filter(
            product=product,
            order__status='in_process'
        ).select_related('order')
        
        if active_order_items.exists():
            order_numbers = ", ".join(str(item.order.id) for item in active_order_items)
            return Response(
                {"error": f"Этот товар присутствует в активных заказах (№{order_numbers}). Сначала завершите или отмените эти заказы."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        product.is_active = False
        product.save()
        
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        product = self.get_object()
        product.is_active = True
        product.save()
        serializer = self.get_serializer(product)
        return Response(serializer.data)

class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [AllowAny]


# ========== КОРЗИНА ==========
class CartViewSet(viewsets.ModelViewSet):
    queryset = Cart.objects.all()
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Cart.objects.filter(user=self.request.user)

    @action(detail=False, methods=['get'])
    def my_cart(self, request):
        cart, created = Cart.objects.get_or_create(user=request.user)
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
            cart.items.all().delete()
            return Response({'status': 'Корзина очищена'}, status=status.HTTP_200_OK)
        except Cart.DoesNotExist:
            return Response({'error': 'Корзина не найдена'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'])
    def add_to_cart(self, request):
        user = request.user
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))

        if not product_id:
            return Response({'error': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        if quantity <= 0:
            return Response({'error': 'Количество должно быть больше 0'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return Response({'error': 'Товар не найден'}, status=status.HTTP_404_NOT_FOUND)

        cart, created = Cart.objects.get_or_create(user=user)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)

        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity

        cart_item.save()
        return Response({'status': 'Товар добавлен в корзину'}, status=status.HTTP_200_OK)

class CartItemViewSet(viewsets.ModelViewSet):
    queryset = CartItem.objects.all()
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]


# ========== ЗАКАЗЫ (ОБНОВЛЕННЫЕ) ==========
class OrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name='status')
    user = django_filters.NumberFilter(field_name='user__id')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Order
        fields = ['status', 'user']
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            Q(id__icontains=value) | 
            Q(user__username__icontains=value) |
            Q(phone_number__icontains=value) |
            Q(guest_name__icontains=value) |
            Q(guest_email__icontains=value)
        )

def send_telegram_notification(order):
    try:
        bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        items_list = ""
        for item in order.items.all():
            items_list += f"\n• {item.product.name} - {item.quantity} шт. x {item.price} руб. = {item.quantity * item.price} руб."
        
        
        # Определяем тип клиента
        client_info = f"👤 Клиент: {order.user.username if order.user else order.guest_name or 'Гость'}"
        if order.guest_email:
            client_info += f"\n📧 Email: {order.guest_email}"
        
        comment_text = f"\n💬 Комментарий: {order.comment}" if order.comment else ""
        
        message = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order.id}</b>

{client_info}
📞 Телефон: {order.phone_number}
📍 Адрес: {order.address}{comment_text}

💰 <b>ИТОГО: {order.total_price} руб.</b>

🛒 <b>Товары:</b>{items_list}
"""
        
        result = bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        
        logger.info(f"✅ Telegram notification sent for order #{order.id}, message ID: {result.message_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram notification: {e}")
        return False

# store/views.py - ПОЛНОСТЬЮ ИСПРАВЛЕННЫЙ OrderViewSet

# store/views.py - полностью исправленный OrderViewSet

# store/views.py - полностью исправленный OrderViewSet

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer
    permission_classes = [AllowAny]
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = OrderFilter

    def get_queryset(self):
        user = self.request.user
        
        if user.is_authenticated:
            queryset = Order.objects.filter(user=user)
        else:
            session_key = self.request.session.session_key
            if session_key:
                queryset = Order.objects.filter(session_key=session_key)
            else:
                queryset = Order.objects.none()
        
        if user.is_staff:
            queryset = Order.objects.all()
        
        return queryset.select_related('user').prefetch_related(
            'items', 'items__product', 'items__product__images'
        ).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                # Проверяем только обязательные поля
                if not request.data.get('address'):
                    return Response(
                        {'error': 'Поле address (адрес доставки) обязательно для заполнения'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                if not request.data.get('phone_number'):
                    return Response(
                        {'error': 'Поле phone_number (номер телефона) обязательно для заполнения'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

                # Для авторизованных пользователей
                if request.user.is_authenticated:
                    cart = Cart.objects.select_related('user').prefetch_related('items__product').get(user=request.user)
                    
                    if not cart.items.exists():
                        return Response(
                            {'error': 'Ваша корзина пуста'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    total_price = Decimal('0.00')
                    order_items_data = []
                    
                    for cart_item in cart.items.all():
                        item_price = Decimal(str(cart_item.product.price))
                        total_price += item_price * cart_item.quantity
                        order_items_data.append({
                            'product': cart_item.product,
                            'quantity': cart_item.quantity,
                            'price': item_price
                        })

                    # Создание заказа для авторизованного - только нужные поля
                    order = Order.objects.create(
                        user=request.user,
                        address=request.data.get('address'),
                        phone_number=request.data.get('phone_number'),
                        comment=request.data.get('comment', ''),
                        status='in_process',
                        total_price=total_price
                    )

                # Для гостей
                else:
                    # Получаем или создаем session_key
                    if not request.session.session_key:
                        request.session.create()
                    
                    session_key = request.session.session_key

                    # Получаем товары из корзины
                    cart_items = request.data.get('cart_items', [])
                    
                    if not cart_items:
                        return Response(
                            {'error': 'Корзина пуста'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    total_price = Decimal('0.00')
                    order_items_data = []
                    
                    for item in cart_items:
                        try:
                            product = Product.objects.get(id=item['product_id'], is_active=True)
                            quantity = int(item['quantity'])
                            
                            if quantity <= 0:
                                raise ValueError("Количество должно быть положительным")
                            
                            item_price = Decimal(str(product.price))
                            total_price += item_price * quantity
                            
                            order_items_data.append({
                                'product': product,
                                'quantity': quantity,
                                'price': item_price
                            })
                        except (Product.DoesNotExist, ValueError, KeyError) as e:
                            return Response(
                                {'error': f'Ошибка в данных корзины: {str(e)}'}, 
                                status=status.HTTP_400_BAD_REQUEST
                            )

                    # Создание заказа для гостя - только нужные поля
                    order = Order.objects.create(
                        session_key=session_key,
                        guest_name=request.data.get('guest_name', 'Гость'),
                        guest_email=request.data.get('guest_email'),
                        address=request.data.get('address'),
                        phone_number=request.data.get('phone_number'),
                        comment=request.data.get('comment', ''),
                        status='in_process',
                        total_price=total_price
                    )

                # Создаем элементы заказа
                OrderItem.objects.bulk_create([
                    OrderItem(
                        order=order,
                        product=item['product'],
                        quantity=item['quantity'],
                        price=item['price']
                    ) for item in order_items_data
                ])

                # Отправляем уведомление в Telegram
                try:
                    order_with_items = Order.objects.prefetch_related('items__product').get(id=order.id)
                    send_telegram_notification(order_with_items)
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification for order #{order.id}: {e}")

                # Очищаем корзину для авторизованных
                if request.user.is_authenticated:
                    cart.items.all().delete()
                
                serializer = self.get_serializer(order)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Cart.DoesNotExist:
            return Response(
                {'error': 'Корзина не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            return Response(
                {'error': f'Ошибка при создании заказа: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if request.method == 'PATCH' and 'status' in request.data:
            old_status = instance.status
            instance.status = request.data['status']
            instance.save()
            
            if old_status != instance.status:
                try:
                    bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
                    client_info = f"{instance.user.username if instance.user else instance.guest_name or 'Гость'}"
                    message = f"""
ℹ️ <b>Статус заказа #{instance.id} изменен</b>

Старый статус: {old_status}
Новый статус: {instance.status}

👤 Клиент: {client_info}
📞 Телефон: {instance.phone_number}
💰 Сумма: {instance.total_price} руб.
"""
                    bot.send_message(
                        chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
                        text=message,
                        parse_mode='HTML'
                    )
                except Exception as e:
                    logger.error(f"Failed to send status update notification: {e}")
            
            serializer = self.get_serializer(instance)
            return Response(serializer.data)
            
        serializer = self.get_serializer(
            instance, 
            data=request.data, 
            partial=partial
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}

        return Response(serializer.data)

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsAuthenticated]


# ========== АВТОРИЗАЦИЯ С ПРИВЯЗКОЙ ЗАКАЗОВ (ОБНОВЛЕННАЯ) ==========
# store/views.py - добавим отладку в RegisterView

# store/views.py - исправленный RegisterView

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")
        
        # ВАЖНО: Используем session_key из текущей сессии Django
        # А не из request.data
        session_key = request.session.session_key
        
        print(f"Register attempt - username: {username}, Django session_key: {session_key}")

        if not username or not password:
            return Response(
                {"error": "Логин и пароль обязательны"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "Пользователь с таким логином уже существует"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Создаем пользователя
            user = User.objects.create(
                username=username,
                password=make_password(password),
                email=email,
            )

            # ПРИВЯЗКА ГОСТЕВЫХ ЗАКАЗОВ
            linked_orders_count = 0
            if session_key:
                print(f"Looking for orders with Django session_key: {session_key}")
                
                # Находим все заказы с этой сессией
                guest_orders = Order.objects.filter(session_key=session_key)
                linked_orders_count = guest_orders.count()
                
                print(f"Found {linked_orders_count} guest orders")
                
                # Привязываем их к пользователю
                for order in guest_orders:
                    print(f"Linking order {order.id} to user {user.id}")
                    order.user = user
                    order.session_key = None
                    order.save()
                    
                logger.info(f"Привязано {linked_orders_count} заказов к пользователю {user.username}")

            # Создаем корзину для пользователя
            Cart.objects.get_or_create(user=user)

        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Пользователь успешно зарегистрирован',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'user': UserSerializer(user).data,
            'linked_orders_count': linked_orders_count
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response(
                {'error': 'Логин и пароль обязательны'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(username=username, password=password)

        if user:
            refresh = RefreshToken.for_user(user)
            
            # Создаем корзину если её нет
            Cart.objects.get_or_create(user=user)
            
            return Response({
                'message': 'Успешный вход',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
            
        return Response(
            {'error': 'Неверный логин или пароль'},
            status=status.HTTP_400_BAD_REQUEST
        )

class TelegramNotificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get('order_id')
            order = Order.objects.prefetch_related('items__product').get(id=order_id)
            
            success = send_telegram_notification(order)
            
            if success:
                return Response({'status': 'ok', 'message': 'Уведомление отправлено'})
            else:
                return Response(
                    {'error': 'Не удалось отправить уведомление в Telegram'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except Order.DoesNotExist:
            return Response(
                {'error': 'Заказ не найден'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Telegram notification error: {e}")
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )