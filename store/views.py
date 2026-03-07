from decimal import Decimal
from django.db import transaction
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.contrib.auth.hashers import make_password
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
from django_filters import rest_framework as django_filters
from .models import Category, Product, ProductImage, WoodType, Grade, Cart, CartItem, Order, OrderItem, Recommendation
from .serializers import CategorySerializer, ProductSerializer, ProductImageSerializer, WoodTypeSerializer, GradeSerializer, CartSerializer, CartItemSerializer, OrderSerializer, OrderItemSerializer, RecommendationSerializer, UserSerializer
from django.contrib.auth.models import User
from store.models import User
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Q
from .models import Product
import telegram
from django.conf import settings
import logging


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

class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer

class ProductFilter(django_filters.FilterSet):
    min_price = django_filters.NumberFilter(field_name="price", lookup_expr='gte')
    max_price = django_filters.NumberFilter(field_name="price", lookup_expr='lte')
    category = django_filters.NumberFilter(field_name="category__id")
    wood_type = django_filters.CharFilter(field_name="wood_type__name")
    grade = django_filters.CharFilter(field_name="grade__name")
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
        fields = ['category', 'wood_type', 'grade', 'min_price', 'max_price', 'is_active']

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
        
        # Проверяем, есть ли этот товар в активных заказах (статус 'in_process')
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
        
        # Если товар есть только в завершенных/отмененных заказах, помечаем его как неактивный вместо удаления
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
        user = request.user
        try:
            cart = Cart.objects.get(user=user)
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

        try:
            product = Product.objects.get(id=product_id)
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

class OrderFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name='status')
    user = django_filters.NumberFilter(field_name='user__id')
    search = django_filters.CharFilter(method='filter_search')
    
    class Meta:
        model = Order
        fields = ['status', 'user']
    
    def filter_search(self, queryset, name, value):
        # Поиск по ID заказа или имени пользователя
        return queryset.filter(
            Q(id__icontains=value) | 
            Q(user__username__icontains=value) |
            Q(phone_number__icontains=value)
        )

def send_telegram_notification(order):
    """Отправка уведомления о заказе в Telegram"""
    try:
        bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        
        # Формируем список товаров
        items_list = ""
        for item in order.items.all():
            items_list += f"\n• {item.product.name} - {item.quantity} шт. x {item.price} руб. = {item.quantity * item.price} руб."
        
        # Словарь для преобразования payment_method в читаемый вид
        PAYMENT_METHODS_DISPLAY = {
            'cash': 'Наличными',
            'transfer': 'Переводом',
            # добавьте другие методы оплаты, если есть
        }
        
        payment_method_display = PAYMENT_METHODS_DISPLAY.get(
            order.payment_method, 
            order.payment_method
        )
        
        # Формируем сообщение
        message = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order.id}</b>

👤 <b>Клиент:</b>
👤 Логин: {order.user.username}
📞 Телефон: {order.phone_number}
📍 Адрес: {order.address}

📦 <b>Доставка:</b>
📅 Дата: {order.delivery_date.strftime('%d.%m.%Y')}
⏰ Время: {order.delivery_time_interval}
💳 Оплата: {payment_method_display}

💰 <b>ИТОГО: {order.total_price} руб.</b>

🛒 <b>Товары:</b>{items_list}
"""
        
        # Отправляем сообщение
        result = bot.send_message(
            chat_id=settings.TELEGRAM_ADMIN_CHAT_ID,
            text=message,
            parse_mode='HTML'
        )
        
        logger.info(f"✅ Telegram notification sent for order #{order.id}, message ID: {result.message_id}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram notification: {e}")
        print(f"❌ Ошибка отправки в Telegram: {e}")  # Для отладки
        return False

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.none()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [django_filters.DjangoFilterBackend]
    filterset_class = OrderFilter

    def get_queryset(self):
        user = self.request.user
        queryset = Order.objects.all().select_related('user').prefetch_related(
            'items',
            'items__product',
            'items__product__images'
        ).order_by('-created_at')
        
        # Применяем фильтры из URL-параметров
        status = self.request.query_params.get('status', None)
        user_id = self.request.query_params.get('user', None)
        
        if status:
            queryset = queryset.filter(status=status)
        if user_id:
            queryset = queryset.filter(user__id=user_id)
        
        if not user.is_staff:
            queryset = queryset.filter(user=user)
            
        return queryset

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # Разрешаем обновлять только статус для PATCH запросов
        if request.method == 'PATCH' and 'status' in request.data:
            old_status = instance.status
            instance.status = request.data['status']
            instance.save()
            
            # Отправляем уведомление об изменении статуса
            if old_status != instance.status:
                try:
                    bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
                    message = f"""
ℹ️ <b>Статус заказа #{instance.id} изменен</b>

Старый статус: {old_status}
Новый статус: {instance.status}

👤 Клиент: {instance.user.username}
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

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
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

                order = Order.objects.create(
                    user=request.user,
                    address=request.data.get('address'),
                    phone_number=request.data.get('phone_number'),
                    delivery_date=request.data.get('delivery_date'),
                    delivery_time_interval=request.data.get('delivery_time_interval'),
                    payment_method=request.data.get('payment_method', 'cash'),
                    status='in_process',
                    total_price=total_price
                )

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
                    # Обновляем order с prefetch_related для items
                    order = Order.objects.prefetch_related(
                        'items__product'
                    ).get(id=order.id)
                    send_telegram_notification(order)
                except Exception as e:
                    logger.error(f"Failed to send Telegram notification for order #{order.id}: {e}")

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

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

class TelegramNotificationView(APIView):
    """Отдельный view для отправки уведомлений в Telegram"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            order_id = request.data.get('order_id')
            order = Order.objects.prefetch_related(
                'items__product'
            ).get(id=order_id)
            
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

class RecommendationView(APIView):
    def post(self, request):
        answers = request.data.get('answers', [])
        
        # Веса для разных типов вопросов (сумма = 100)
        WEIGHTS = {
            'application': 33,    # Область применения (самый важный)
            'price': 26,          # Цена (высокий приоритет)
            'wood_type': 18,      # Тип древесины
            'processing': 12,      # Уровень обработки
            'color': 11           # Цвет (наименее важный)
        }
        
        # Собираем критерии с учетом весов
        criteria = {
            'application_tags': set(),
            'wood_type_tags': set(),
            'processing_tags': set(),
            'color_tags': set(),
            'price_min': Decimal('0.00'),
            'price_max': None,
            'total_weight': 0
        }
        
        # Анализируем ответы пользователя
        for answer in answers:
            if 'tags' in answer:
                # Определяем тип вопроса по содержанию тегов
                if any(tag in ['крыша', 'кровля', 'пол', 'напольное', 'стены', 'обшивка', 'мебель', 'мебельный', 'декор', 'отделка', 'сад', 'ландшафт'] for tag in answer['tags']):
                    criteria['application_tags'].update(answer['tags'])
                    criteria['total_weight'] += WEIGHTS['application']
                elif any(tag in ['сосна', 'ель', 'кедр', 'лиственница', 'дуб', 'ясень', 'берёза', 'бук', 'красное', 'тик', 'венге', 'мехагон', ''] for tag in answer['tags']):
                    criteria['wood_type_tags'].update(answer['tags'])
                    criteria['total_weight'] += WEIGHTS['wood_type']
                elif any(tag in ['черновая', 'необработанная', 'шлифованная', 'стандарт', 'полированная', 'тонированная'] for tag in answer['tags']):
                    criteria['processing_tags'].update(answer['tags'])
                    criteria['total_weight'] += WEIGHTS['processing']
                elif any(tag in ['светлый', 'белый', 'белёный', 'натуральный', 'древесный', 'тёмный', 'венге', 'орех', 'цветной', 'тонированный'] for tag in answer['tags']):
                    criteria['color_tags'].update(answer['tags'])
                    criteria['total_weight'] += WEIGHTS['color']
            
            # Обработка цены
            if 'minPrice' in answer or 'maxPrice' in answer:
                if 'minPrice' in answer and answer['minPrice'] is not None:
                    criteria['price_min'] = max(
                        criteria['price_min'],
                        Decimal(str(answer['minPrice']))
                    )
                if 'maxPrice' in answer and answer['maxPrice'] is not None:
                    if criteria['price_max'] is None:
                        criteria['price_max'] = Decimal(str(answer['maxPrice']))
                    else:
                        criteria['price_max'] = min(
                            criteria['price_max'],
                            Decimal(str(answer['maxPrice']))
                        )
                criteria['total_weight'] += WEIGHTS['price']
        
        # Поиск и оценка товаров
        products = Product.objects.all()
        results = []
        
        for product in products:
            score = 0
            product_text = f"{product.name} {product.description or ''}".lower()
            
            # Проверка области применения (макс 30%)
            if criteria['application_tags']:
                if any(tag.lower() in product_text for tag in criteria['application_tags']):
                    score += WEIGHTS['application']
            
            # Проверка цены (макс 25%)
            price_passed = True
            if product.price < criteria['price_min']:
                price_passed = False
            if criteria['price_max'] and product.price > criteria['price_max']:
                price_passed = False
            
            if price_passed:
                score += WEIGHTS['price']
            
            # Проверка типа древесины (макс 20%)
            if criteria['wood_type_tags']:
                if any(tag.lower() in product_text for tag in criteria['wood_type_tags']):
                    score += WEIGHTS['wood_type']
            
            # Проверка обработки (макс 15%)
            if criteria['processing_tags']:
                if any(tag.lower() in product_text for tag in criteria['processing_tags']):
                    score += WEIGHTS['processing']
            
            # Проверка цвета (макс 10%)
            if criteria['color_tags']:
                if any(tag.lower() in product_text for tag in criteria['color_tags']):
                    score += WEIGHTS['color']
            
            # Расчет процента соответствия
            if criteria['total_weight'] > 0:
                match_percent = min(100, int((score / criteria['total_weight']) * 100))
            else:
                match_percent = 0
            
            if match_percent > 0:
                results.append({
                    'product': product,
                    'match_percent': match_percent,
                    'score_details': {
                        'application': any(tag.lower() in product_text for tag in criteria['application_tags']),
                        'price': price_passed,
                        'wood_type': any(tag.lower() in product_text for tag in criteria['wood_type_tags']),
                        'processing': any(tag.lower() in product_text for tag in criteria['processing_tags']),
                        'color': any(tag.lower() in product_text for tag in criteria['color_tags'])
                    }
                })
        
        # Сортировка по убыванию соответствия
        results.sort(key=lambda x: (-x['match_percent'], x['product'].price))
        
        # Формирование ответа
        serialized_products = ProductSerializer(
            [item['product'] for item in results[:6]],
            many=True
        ).data
        
        for i, item in enumerate(results[:6]):
            serialized_products[i].update({
                'match_percent': item['match_percent'],
                'score_details': item['score_details']
            })
        
        return Response(serialized_products, status=status.HTTP_200_OK)

class RegisterView(APIView):
    def post(self, request):
        username = request.data.get("username")
        password = request.data.get("password")
        email = request.data.get("email", "")

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

        user = User.objects.create(
            username=username,
            password=make_password(password),
            email=email,
        )

        refresh = RefreshToken.for_user(user)
        return Response({
            'message': 'Пользователь успешно зарегистрирован',
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
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
            return Response({
                'message': 'Успешный вход',
                'tokens': {
                    'refresh': str(refresh),
                    'access': str(refresh.access_token),
                }
            }, status=status.HTTP_200_OK)
        return Response(
            {'error': 'Неверный логин или пароль'},
            status=status.HTTP_400_BAD_REQUEST
        )