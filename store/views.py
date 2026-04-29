# store/views.py
import re  # Добавьте эту строку
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
import requests
import threading
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.db.models import OuterRef, Subquery, F
from django.db.models.functions import Coalesce
from django.core.mail import send_mail
from datetime import datetime


from .models import Category, Product, ProductImage, WoodType, Grade, Cart, CartItem, Order, OrderItem, UnitType, ProductPrice
from .serializers import (
    CategorySerializer, ProductSerializer, ProductImageSerializer,
    WoodTypeSerializer, GradeSerializer, CartSerializer, CartItemSerializer,
    OrderSerializer, OrderItemSerializer, UserSerializer, UnitTypeSerializer, ProductPriceSerializer
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

class UnitTypeViewSet(viewsets.ModelViewSet):
    """
    ViewSet для типов единиц измерения
    """
    queryset = UnitType.objects.all()
    serializer_class = UnitTypeSerializer
    permission_classes = [AllowAny]
    
class ProductPriceViewSet(viewsets.ModelViewSet):
    """
    ViewSet для цен товаров
    """
    queryset = ProductPrice.objects.all()
    serializer_class = ProductPriceSerializer
    permission_classes = [AllowAny]
    
    def get_queryset(self):
        queryset = ProductPrice.objects.all()
        product_id = self.request.query_params.get('product', None)
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset

# store/views.py - замените существующий ProductFilter на этот

class ProductFilter(django_filters.FilterSet):
    # Фильтр по цене через связанную модель ProductPrice
    min_price = django_filters.NumberFilter(method='filter_min_price')
    max_price = django_filters.NumberFilter(method='filter_max_price')
    
    category = django_filters.NumberFilter(field_name="category__id")
    wood_type = django_filters.CharFilter(field_name="wood_type__name")
    grade = django_filters.CharFilter(field_name="grade__name")
    width = django_filters.NumberFilter(field_name="width")
    thickness = django_filters.NumberFilter(field_name="thickness")
    length = django_filters.NumberFilter(field_name="length")
    search = django_filters.CharFilter(method='filter_search')
    
    # НОВАЯ СТРУКТУРА ДЛЯ СОРТИРОВКИ - используем аннотированное поле с ценой по умолчанию
    ordering = django_filters.OrderingFilter(
        fields=(
            ('name', 'name'),
            ('default_price', 'price'),  # Используем аннотированное поле default_price
        ),
        distinct=False  # Убираем distinct, так как теперь у нас нет дублей
    )
    
    is_active = django_filters.BooleanFilter(field_name='is_active', initial=True)

    class Meta:
        model = Product
        fields = ['category', 'wood_type', 'grade', 'width', 'thickness', 'length', 'is_active']

    def filter_min_price(self, queryset, name, value):
        """Фильтр по минимальной цене - используем цену по умолчанию или первую цену"""
        if value is not None:
            # Сначала аннотируем товары их ценами по умолчанию
            default_price_subquery = ProductPrice.objects.filter(
                product=OuterRef('pk')
            ).order_by('-is_default', 'id')[:1]
            
            queryset = queryset.annotate(
                default_price=Subquery(default_price_subquery.values('price')[:1])
            )
            
            return queryset.filter(default_price__gte=value)
        return queryset

    def filter_max_price(self, queryset, name, value):
        """Фильтр по максимальной цене - используем цену по умолчанию или первую цену"""
        if value is not None:
            # Сначала аннотируем товары их ценами по умолчанию
            default_price_subquery = ProductPrice.objects.filter(
                product=OuterRef('pk')
            ).order_by('-is_default', 'id')[:1]
            
            queryset = queryset.annotate(
                default_price=Subquery(default_price_subquery.values('price')[:1])
            )
            
            return queryset.filter(default_price__lte=value)
        return queryset

    def filter_search(self, queryset, name, value):
        """Поиск по названию"""
        return queryset.filter(name__icontains=value)
    
    def get_queryset(self):
        """Переопределяем get_queryset, чтобы аннотировать все товары ценой по умолчанию"""
        queryset = super().get_queryset()
        
        # Аннотируем все товары их ценой по умолчанию
        default_price_subquery = ProductPrice.objects.filter(
            product=OuterRef('pk')
        ).order_by('-is_default', 'id')[:1]
        
        return queryset.annotate(
            default_price=Subquery(default_price_subquery.values('price')[:1])
        )

# store/views.py - замените существующий ProductViewSet на этот

# store/views.py
class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = ProductFilter
    permission_classes = [AllowAny]

    def get_queryset(self):
        """Оптимизируем запросы и добавляем аннотацию с ценой по умолчанию"""
        from django.db.models import OuterRef, Subquery
        
        # Подзапрос для получения цены по умолчанию
        default_price_subquery = ProductPrice.objects.filter(
            product=OuterRef('pk')
        ).order_by('-is_default', 'id')[:1]
        
        queryset = Product.objects.filter(is_active=True).prefetch_related(
            'prices',
            'prices__unit_type',
            'images'
        ).annotate(
            default_price=Subquery(default_price_subquery.values('price')[:1])
        )
        
        # Поддержка category__in для родительских категорий
        category_in = self.request.query_params.get('category__in')
        if category_in:
            category_ids = [int(id) for id in category_in.split(',') if id.strip().isdigit()]
            if category_ids:
                queryset = queryset.filter(category__id__in=category_ids)
        
        # Обработка сортировки по цене
        ordering = self.request.query_params.get('ordering')
        if ordering and 'price' in ordering:
            # Преобразуем 'price' в 'default_price' для сортировки
            if ordering == 'price':
                queryset = queryset.order_by('default_price')
            elif ordering == '-price':
                queryset = queryset.order_by('-default_price')
            else:
                # Для других видов сортировки
                queryset = queryset.order_by(ordering)
        
        return queryset

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
    
    @action(detail=False, methods=['get'], url_path='by-slug/(?P<slug>[^/.]+)')
    def get_by_slug(self, request, slug=None):
        """
        Получить товар по slug
        """
        try:
            product = Product.objects.get(slug=slug, is_active=True)
            serializer = self.get_serializer(product)
            return Response(serializer.data)
        except Product.DoesNotExist:
            return Response(
                {'error': 'Product not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )

class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [AllowAny]


# ========== КОРЗИНА ==========
# ОБНОВЛЕННЫЙ CartViewSet (метод add_to_cart)
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

    @action(detail=False, methods=['post'])
    def add_to_cart(self, request):
        user = request.user
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        selected_price_id = request.data.get('selected_price_id')

        if not product_id:
            return Response({'error': 'product_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not selected_price_id:
            return Response({'error': 'selected_price_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        if quantity <= 0:
            return Response({'error': 'Количество должно быть больше 0'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            product = Product.objects.get(id=product_id, is_active=True)
            selected_price = ProductPrice.objects.get(id=selected_price_id, product_id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Товар не найден'}, status=status.HTTP_404_NOT_FOUND)
        except ProductPrice.DoesNotExist:
            return Response({'error': 'Выбранный вариант цены не найден'}, status=status.HTTP_404_NOT_FOUND)

        cart, created = Cart.objects.get_or_create(user=user)

        # Ищем существующий item с таким же товаром и ценой
        cart_item = CartItem.objects.filter(
            cart=cart,
            product=product,
            selected_price=selected_price
        ).first()

        if cart_item:
            # Обновляем количество, если оно изменилось
            if cart_item.quantity != quantity:
                cart_item.quantity = quantity
                cart_item.save()
                return Response({'status': 'Количество товара обновлено'}, status=status.HTTP_200_OK)
            else:
                return Response({'status': 'Товар уже в корзине в нужном количестве'}, status=status.HTTP_200_OK)
        else:
            cart_item = CartItem(
                cart=cart,
                product=product,
                selected_price=selected_price,
                quantity=quantity
            )
            cart_item.save()
            return Response({'status': 'Товар добавлен в корзину'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['delete'])
    def clear(self, request):
        try:
            cart = Cart.objects.get(user=request.user)
            cart.items.all().delete()
            return Response({'status': 'Корзина очищена'}, status=status.HTTP_200_OK)
        except Cart.DoesNotExist:
            return Response({'error': 'Корзина не найдена'}, status=status.HTTP_404_NOT_FOUND)

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


# store/views.py - обновленная функция send_telegram_notification

def send_telegram_notification_async(order_id):
    """Отправка уведомления в Telegram в отдельном потоке"""
    try:
        from .models import Order
        order = Order.objects.prefetch_related('items__product').get(id=order_id)
        
        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        
        # Функция для получения красивого названия единицы измерения
        def get_unit_display(item):
            # Сначала проверяем selected_price_info
            if item.selected_price_info:
                unit_short = item.selected_price_info.get('unit_type_short')
                if unit_short:
                    return unit_short
            
            # Если нет, используем маппинг
            unit_map = {
                'piece': 'шт',
                'cubic': 'м³',
                'square': 'м²',
                'pack': 'уп',
                'linear': 'п.м'
            }
            return unit_map.get(item.unit_type, item.unit_type or 'шт')
        
        # Функция для форматирования количества
        def get_quantity_display(item):
            quantity = item.quantity
            unit = get_unit_display(item)
            
            # Для упаковок показываем дополнительную информацию
            if item.selected_price_info and item.selected_price_info.get('unit_type_code') == 'pack':
                quantity_per_unit = item.selected_price_info.get('quantity_per_unit')
                if quantity_per_unit:
                    total_items = quantity * quantity_per_unit
                    return f"{quantity} уп ({total_items} шт)"
            
            return f"{quantity} {unit}"
        
        items_list = ""
        for item in order.items.all():
            quantity_display = get_quantity_display(item)
            unit_display = get_unit_display(item)
            
            items_list += f"\n• {item.product.name} - {quantity_display} × {item.price_per_unit} руб. = {item.quantity * item.price_per_unit} руб."
        
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
        
        payload = {
            "chat_id": settings.TELEGRAM_ADMIN_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }
        
        # Здесь уже можно ждать, т.к. это отдельный поток
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        logger.info(f"✅ Telegram notification sent for order #{order.id}")
        
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram notification for order #{order_id}: {e}")

def send_telegram_notification(order):
    """Запускает отправку в отдельном потоке и сразу возвращает управление"""
    try:
        thread = threading.Thread(target=send_telegram_notification_async, args=(order.id,))
        thread.daemon = True  # Поток завершится при завершении основного процесса
        thread.start()
        logger.info(f"📨 Telegram notification started for order #{order.id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to start telegram thread: {e}")
        return False


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

                if request.user.is_authenticated:
                    cart = Cart.objects.select_related('user').prefetch_related('items__product', 'items__selected_price').get(user=request.user)

                    if not cart.items.exists():
                        return Response(
                            {'error': 'Ваша корзина пуста'},
                            status=status.HTTP_400_BAD_REQUEST
                        )

                    total_price = Decimal('0.00')
                    order_items_data = []

                    for cart_item in cart.items.all():
                        item_price = cart_item.selected_price.price
                        total_price += Decimal(str(item_price)) * cart_item.quantity
                        order_items_data.append({
                            'product': cart_item.product,
                            'quantity': cart_item.quantity,
                            'price_per_unit': item_price,
                            'selected_price_info': {
                                'id': cart_item.selected_price.id,
                                'price': cart_item.selected_price.price,
                                'unit_type': cart_item.selected_price.unit_type.code,
                                'unit_type_short': cart_item.selected_price.unit_type.short_name,
                                'quantity_per_unit': cart_item.selected_price.quantity_per_unit
                            }
                        })

                    order = Order.objects.create(
                        user=request.user,
                        address=request.data.get('address'),
                        phone_number=request.data.get('phone_number'),
                        comment=request.data.get('comment', ''),
                        status='in_process',
                        total_price=total_price
                    )

                else:
                    if not request.session.session_key:
                        request.session.create()

                    session_key = request.session.session_key
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

                            selected_price = ProductPrice.objects.get(id=item['selected_price_id'])
                            item_price = selected_price.price
                            total_price += Decimal(str(item_price)) * quantity

                            order_items_data.append({
                                'product': product,
                                'quantity': quantity,
                                'price_per_unit': item_price,
                                'selected_price_info': {
                                    'id': selected_price.id,
                                    'price': selected_price.price,
                                    'unit_type': selected_price.unit_type.code,
                                    'unit_type_short': selected_price.unit_type.short_name,
                                    'quantity_per_unit': selected_price.quantity_per_unit
                                }
                            })
                        except (Product.DoesNotExist, ProductPrice.DoesNotExist, ValueError, KeyError) as e:
                            return Response(
                                {'error': f'Ошибка в данных корзины: {str(e)}'},
                                status=status.HTTP_400_BAD_REQUEST
                            )

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
                        price_per_unit=item['price_per_unit'],
                        selected_price_info=item['selected_price_info'],
                        unit_type=item['selected_price_info'].get('unit_type', 'piece')
                    ) for item in order_items_data
                ])

                # Отправляем уведомление на почту вместо Telegram
                send_order_notification_to_email(order, order_items_data, request)

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

class RegisterView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")
        
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

# store/views.py - исправленный LoginView
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
            cart, created = Cart.objects.get_or_create(user=user)
            
            # Получаем сессию из запроса (для гостевых заказов)
            session_key = request.session.session_key
            
            # Привязываем гостевые заказы к пользователю
            if session_key:
                guest_orders = Order.objects.filter(session_key=session_key)
                for order in guest_orders:
                    order.user = user
                    order.session_key = None
                    order.save()
            
            return Response({
                'message': 'Успешный вход',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                },
                'user': UserSerializer(user).data,
                'session_key': session_key  # Возвращаем сессию для синхронизации
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
        

# store/views.py - добавьте в конец файла

class DebugAuthView(APIView):
    """
    Тестовый эндпоинт для проверки аутентификации
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    
    def get(self, request):
        print("\n" + "="*50)
        print("🔍 DEBUG AUTH ENDPOINT")
        print(f"User: {request.user}")
        print(f"Is authenticated: {request.user.is_authenticated}")
        print(f"Auth header: {request.headers.get('Authorization', 'Not provided')}")
        print("="*50 + "\n")
        
        return Response({
            'message': 'Аутентификация работает!',
            'user': request.user.username,
            'user_id': request.user.id,
            'is_authenticated': request.user.is_authenticated,
        })
    
class CallbackRequestView(APIView):
    """
    Эндпоинт для заказа обратного звонка
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        name = request.data.get('name', '').strip()
        phone = request.data.get('phone', '').strip()
        
        # Валидация
        if not name:
            return Response({
                'error': 'Пожалуйста, укажите ваше имя'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not phone:
            return Response({
                'error': 'Пожалуйста, укажите номер телефона'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Очистка телефона и проверка длины
        phone_clean = re.sub(r'[\s\(\)-]+', '', phone)
        if len(phone_clean) < 10:
            return Response({
                'error': 'Некорректный номер телефона'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Отправка email на prime-forest@yandex.ru
        try:
            subject = f'🔔 Заказ обратного звонка от {name}'
            message = f"""
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; }}
                    .header {{ background-color: #2b5e2b; color: white; padding: 15px; text-align: center; }}
                    .content {{ padding: 20px; }}
                    .info-row {{ margin-bottom: 10px; }}
                    .label {{ font-weight: bold; color: #2b5e2b; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h2>📞 НОВАЯ ЗАЯВКА НА ОБРАТНЫЙ ЗВОНОК</h2>
                </div>
                <div class="content">
                    <div class="info-row">
                        <span class="label">👤 Имя:</span> {name}
                    </div>
                    <div class="info-row">
                        <span class="label">📱 Телефон:</span> {phone}
                    </div>
                    <div class="info-row">
                        <span class="label">⏰ Время заявки:</span> {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
                    </div>
                </div>
            </body>
            </html>
            """
            
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['prime-forest@yandex.ru'],
                html_message=message,
                fail_silently=False,
            )
            
            logger.info(f"Callback request sent: {name}, {phone}")
            
            return Response({
                'message': 'Заявка успешно отправлена',
                'status': 'ok'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Failed to send callback email: {e}")
            return Response({
                'error': 'Не удалось отправить заявку. Пожалуйста, попробуйте позже.'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

def send_order_notification_to_email(order, order_items_data, request):
    """Отправка уведомления о новом заказе на почту prime-forest@yandex.ru"""
    try:
        # Формируем список товаров в HTML
        items_html = ""
        items_text = ""
        
        for item in order_items_data:
            unit_short = item['selected_price_info'].get('unit_type_short', 'шт')
            quantity = item['quantity']
            price = item['price_per_unit']
            total = quantity * price
            
            # Для упаковок показываем дополнительную информацию
            pack_info = ""
            if item['selected_price_info'].get('unit_type') == 'pack':
                qty_per_unit = item['selected_price_info'].get('quantity_per_unit')
                if qty_per_unit:
                    pack_info = f" ({quantity * qty_per_unit} шт)"
                    unit_short = "уп"
            
            items_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #ddd;">{item['product'].name}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: center;">{quantity} {unit_short}{pack_info}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">₽{price:,}</td>
                <td style="padding: 8px; border-bottom: 1px solid #ddd; text-align: right;">₽{total:,}</td>
            </tr>
            """
            
            items_text += f"\n• {item['product'].name} - {quantity} {unit_short} × {price} руб. = {total} руб."
        
        # Определяем имя клиента
        if order.user:
            client_name = order.user.username
            client_email = order.user.email or "не указан"
        else:
            client_name = order.guest_name or "Гость"
            client_email = order.guest_email or "не указан"
        
        # Формируем HTML письмо
        html_message = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; }}
                .header {{ background-color: #2b5e2b; color: white; padding: 15px; text-align: center; }}
                .content {{ padding: 20px; }}
                .info-section {{ background-color: #f5f5f5; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                .info-row {{ margin-bottom: 8px; }}
                .label {{ font-weight: bold; color: #2b5e2b; }}
                table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
                th {{ background-color: #2b5e2b; color: white; padding: 10px; text-align: left; }}
                .total {{ font-size: 18px; font-weight: bold; color: #2b5e2b; text-align: right; margin-top: 15px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h2>🆕 НОВЫЙ ЗАКАЗ #{order.id}</h2>
            </div>
            <div class="content">
                <div class="info-section">
                    <h3>👤 Информация о клиенте</h3>
                    <div class="info-row"><span class="label">Имя:</span> {client_name}</div>
                    <div class="info-row"><span class="label">📧 Email:</span> {client_email}</div>
                    <div class="info-row"><span class="label">📞 Телефон:</span> {order.phone_number}</div>
                    <div class="info-row"><span class="label">📍 Адрес:</span> {order.address}</div>
                    {f'<div class="info-row"><span class="label">💬 Комментарий:</span> {order.comment}</div>' if order.comment else ''}
                </div>
                
                <h3>🛒 Состав заказа</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Товар</th>
                            <th style="text-align: center">Количество</th>
                            <th style="text-align: right">Цена</th>
                            <th style="text-align: right">Сумма</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html}
                    </tbody>
                </table>
                
                <div class="total">
                    💰 ИТОГО: ₽{order.total_price:,}
                </div>
            </div>
        </body>
        </html>
        """
        
        # Текстовая версия для plain text
        text_message = f"""
        НОВЫЙ ЗАКАЗ #{order.id}
        
        Информация о клиенте:
        Имя: {client_name}
        Email: {client_email}
        Телефон: {order.phone_number}
        Адрес: {order.address}
        {f'Комментарий: {order.comment}' if order.comment else ''}
        
        Состав заказа:{items_text}
        
        ИТОГО: {order.total_price} руб.
        """
        
        # Отправляем email
        send_mail(
            subject=f'🆕 Новый заказ #{order.id} от {client_name}',
            message=text_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=['prime-forest@yandex.ru'],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"✅ Email notification sent for order #{order.id} to prime-forest@yandex.ru")
        
    except Exception as e:
        logger.error(f"❌ Failed to send email notification for order #{order.id}: {e}")