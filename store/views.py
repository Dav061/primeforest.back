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
    search = django_filters.CharFilter(method='filter_search')  # Добавлен поиск
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

class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.none()  # По умолчанию — пустой список
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
            instance.status = request.data['status']
            instance.save()
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

    # Остальные методы остаются без изменений
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

                cart.items.all().delete()
                serializer = self.get_serializer(order)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Cart.DoesNotExist:
            return Response(
                {'error': 'Корзина не найдена'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Ошибка при создании заказа: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

class OrderItemViewSet(viewsets.ModelViewSet):
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer

# class RecommendationView(APIView):
#     def post(self, request):
#         answers = request.data.get('answers', [])
        
#         # Формируем Q-объекты для фильтрации
#         q_objects = Q()
#         price_min = Decimal('0.00')
#         price_max = None  # Будем использовать None вместо float('inf')
        
#         for answer in answers:
#             # Обработка тегов
#             if 'tags' in answer:
#                 for tag in answer['tags']:
#                     q_objects |= Q(name__icontains=tag) | Q(description__icontains=tag)
            
#             # Обработка ценового диапазона
#             if 'minPrice' in answer or 'maxPrice' in answer:
#                 min_price = answer.get('minPrice')
#                 max_price = answer.get('maxPrice')
                
#                 if min_price is not None:
#                     price_min = max(price_min, Decimal(str(min_price)))
#                 if max_price is not None:
#                     if price_max is None:
#                         price_max = Decimal(str(max_price))
#                     else:
#                         price_max = min(price_max, Decimal(str(max_price)))
        
#         # Строим фильтр для цены
#         price_filter = Q(price__gte=price_min)
#         if price_max is not None:
#             price_filter &= Q(price__lte=price_max)
        
#         # Применяем фильтры
#         products = Product.objects.filter(
#             q_objects & price_filter
#         ).order_by('price')[:6]  # Лимит 6 товаров
        
#         serializer = ProductSerializer(products, many=True)
#         return Response(serializer.data, status=status.HTTP_200_OK)


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
            
            if match_percent > 0:  # Показываем только товары с >40% соответствия
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

        # Добавьте этот блок для возврата токенов
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