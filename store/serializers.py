# store/serializers.py
from rest_framework import serializers
from .models import (
    Category, Product, ProductImage, WoodType, Grade, 
    Cart, CartItem, Order, OrderItem,
    UnitType, ProductPrice
)
from django.contrib.auth import get_user_model

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'image_url', 'parent']

class WoodTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WoodType
        fields = ['id', 'name']

class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'name']

class UnitTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnitType
        fields = ['id', 'name', 'code', 'short_name']

# НОВЫЙ СЕРИАЛИЗАТОР: для вариантов цен
class ProductPriceSerializer(serializers.ModelSerializer):
    unit_type_name = serializers.CharField(source='unit_type.name', read_only=True)
    unit_type_code = serializers.CharField(source='unit_type.code', read_only=True)
    unit_type_short = serializers.CharField(source='unit_type.short_name', read_only=True)
    
    class Meta:
        model = ProductPrice
        fields = [
            'id', 'unit_type', 'unit_type_name', 'unit_type_code', 
            'unit_type_short', 'price', 'quantity_per_unit', 'is_default'
        ]

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image_url']

# ОБНОВЛЕННЫЙ СЕРИАЛИЗАТОР: ProductSerializer
class ProductSerializer(serializers.ModelSerializer):
    # Цены теперь через related manager
    prices = ProductPriceSerializer(many=True, read_only=True)
    
    # Для обратной совместимости (опционально)
    display_prices = serializers.SerializerMethodField()
    
    category = serializers.CharField(source='category.name', read_only=True)
    wood_type = serializers.CharField(source='wood_type.name', read_only=True)
    grade = serializers.CharField(source='grade.name', read_only=True)
    main_image = serializers.SerializerMethodField()
    
    # Поля для записи
    category_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    wood_type_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    grade_name = serializers.CharField(write_only=True, required=False, allow_blank=True)
    image_url = serializers.CharField(write_only=True, required=False, allow_blank=True)
    
    # НОВОЕ: для создания цен при создании товара
    prices_data = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False,
        help_text="""
        Пример: 
        [
            {"unit_type_code": "piece", "price": 1500, "is_default": true},
            {"unit_type_code": "cubic", "price": 25000, "is_default": false}
        ]
        """
    )

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'is_active',
            'category', 'wood_type', 'grade',
            'width', 'thickness', 'length',
            'prices', 'display_prices', 'prices_data',
            'category_name', 'wood_type_name', 'grade_name',
            'main_image', 'image_url'
        ]

    def get_main_image(self, obj):
        first_image = obj.images.first()
        return first_image.image_url if first_image else None

    def get_display_prices(self, obj):
        """Форматирует цены для отображения"""
        prices = []
        for price in obj.prices.all():
            if price.unit_type.code == 'pack' and price.quantity_per_unit:
                prices.append(f"{price.price}₽/{price.unit_type.short_name} ({price.quantity_per_unit} шт)")
            else:
                prices.append(f"{price.price}₽/{price.unit_type.short_name}")
        return " | ".join(prices)

    def validate(self, data):
        # Обработка категории
        if 'category_name' in data and data['category_name']:
            try:
                data['category'] = Category.objects.get(name=data.pop('category_name'))
            except Category.DoesNotExist:
                raise serializers.ValidationError({"category_name": "Категория не найдена"})
        
        # Обработка породы дерева
        if 'wood_type_name' in data and data['wood_type_name']:
            try:
                data['wood_type'] = WoodType.objects.get(name=data.pop('wood_type_name'))
            except WoodType.DoesNotExist:
                raise serializers.ValidationError({"wood_type_name": "Порода дерева не найдена"})
        
        # Обработка сорта
        if 'grade_name' in data and data['grade_name']:
            try:
                data['grade'] = Grade.objects.get(name=data.pop('grade_name'))
            except Grade.DoesNotExist:
                raise serializers.ValidationError({"grade_name": "Сорт не найден"})
        
        # Валидация ценовых данных
        prices_data = data.get('prices_data', [])
        if prices_data:
            unit_type_codes = [p.get('unit_type_code') for p in prices_data]
            if len(unit_type_codes) != len(set(unit_type_codes)):
                raise serializers.ValidationError(
                    {"prices_data": "Не может быть двух цен с одинаковым типом единицы"}
                )
        
        return data

    def create(self, validated_data):
        prices_data = validated_data.pop('prices_data', [])
        image_url = validated_data.pop('image_url', None)
        
        # Создаем товар
        product = Product.objects.create(**validated_data)
        
        # Создаем цены
        for price_data in prices_data:
            unit_type_code = price_data.pop('unit_type_code')
            try:
                unit_type = UnitType.objects.get(code=unit_type_code)
                ProductPrice.objects.create(
                    product=product,
                    unit_type=unit_type,
                    **price_data
                )
            except UnitType.DoesNotExist:
                raise serializers.ValidationError(
                    {"prices_data": f"Тип единицы с кодом '{unit_type_code}' не найден"}
                )
        
        # Создаем изображение
        if image_url:
            ProductImage.objects.create(product=product, image_url=image_url)
        
        return product

    def update(self, instance, validated_data):
        prices_data = validated_data.pop('prices_data', None)
        image_url = validated_data.pop('image_url', None)
        
        # Обновляем товар
        instance = super().update(instance, validated_data)
        
        # Обновляем цены если переданы
        if prices_data is not None:
            # Удаляем старые цены
            instance.prices.all().delete()
            
            # Создаем новые
            for price_data in prices_data:
                unit_type_code = price_data.pop('unit_type_code')
                try:
                    unit_type = UnitType.objects.get(code=unit_type_code)
                    ProductPrice.objects.create(
                        product=instance,
                        unit_type=unit_type,
                        **price_data
                    )
                except UnitType.DoesNotExist:
                    raise serializers.ValidationError(
                        {"prices_data": f"Тип единицы с кодом '{unit_type_code}' не найден"}
                    )
        
        # Обновляем изображение
        if image_url:
            instance.images.all().delete()
            ProductImage.objects.create(product=instance, image_url=image_url)
        
        return instance

# ОБНОВЛЕННЫЙ СЕРИАЛИЗАТОР: CartItemSerializer
class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )
    
    selected_price = ProductPriceSerializer(read_only=True)  # Для чтения - полный объект
    # НОВОЕ: для выбора цены
    selected_price_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductPrice.objects.all(),
        source='selected_price',
        write_only=True
    )
    
    selected_price_info = serializers.SerializerMethodField()
    total = serializers.IntegerField(source='total_price', read_only=True)

    class Meta:
        model = CartItem
        fields = [
            'id', 'product', 'product_id', 'quantity', 
            'selected_price', 'selected_price_id', 'selected_price_info', 'total'
        ]

    def get_selected_price_info(self, obj):
        if obj.selected_price:
            return {
                'id': obj.selected_price.id,
                'price': obj.selected_price.price,
                'unit_type': obj.selected_price.unit_type.code,
                'unit_type_short': obj.selected_price.unit_type.short_name,
                'unit_type_name': obj.selected_price.unit_type.name,
                'quantity_per_unit': obj.selected_price.quantity_per_unit
            }
        return None

    def validate(self, data):
        # Проверяем, что выбранная цена принадлежит товару
        if 'selected_price' in data and 'product' in data:
            selected_price = data['selected_price']
            product = data['product']
            
            if selected_price.product_id != product.id:
                raise serializers.ValidationError(
                    {"selected_price_id": "Выбранная цена не принадлежит этому товару"}
                )
        
        return data

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items', 'total_price']

    def get_total_price(self, obj):
        total = 0
        for item in obj.items.all():
            total += item.total_price
        return total

# ОБНОВЛЕННЫЙ СЕРИАЛИЗАТОР: OrderItemSerializer
class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    
    # Добавляем метод для получения отображаемой цены
    display_price = serializers.SerializerMethodField()
    display_quantity = serializers.SerializerMethodField()
    
    class Meta:
        model = OrderItem
        fields = [
            'id', 'product', 'quantity', 'price_per_unit', 
            'unit_type', 'selected_price_info', 'display_price',
            'display_quantity'
        ]
    
    def get_display_price(self, obj):
        """Возвращает цену с единицей измерения"""
        price = obj.price_per_unit
        formatted_price = f"{price:,}".replace(",", " ")
        
        # Определяем символ единицы измерения
        unit_symbol = self._get_unit_symbol(obj)
        
        return f"{formatted_price} ₽/{unit_symbol}"
    
    def get_display_quantity(self, obj):
        """Возвращает количество с единицей измерения"""
        if obj.selected_price_info:
            unit_type_code = obj.selected_price_info.get('unit_type_code')
            unit_short = obj.selected_price_info.get('unit_type_short', '')
            quantity_per_unit = obj.selected_price_info.get('quantity_per_unit')
            
            if unit_type_code == 'pack' and quantity_per_unit:
                total_items = obj.quantity * quantity_per_unit
                return f"{obj.quantity} уп ({total_items} шт)"
            
            return f"{obj.quantity} {unit_short}"
        
        # Если нет информации, используем unit_type
        unit_symbol = self._get_unit_symbol(obj)
        return f"{obj.quantity} {unit_symbol}"
    
    def _get_unit_symbol(self, obj):
        """Определяет символ единицы измерения"""
        if obj.selected_price_info:
            return obj.selected_price_info.get('unit_type_short', 'шт')
        
        # Маппинг кодов в символы
        unit_map = {
            'piece': 'шт',
            'cubic': 'м³',
            'square': 'м²',
            'pack': 'уп',
            'linear': 'п.м'
        }
        return unit_map.get(obj.unit_type, obj.unit_type or 'шт')


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    
    # Добавляем форматированную общую сумму
    display_total = serializers.SerializerMethodField()
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'total_price', 'display_total', 'address', 'phone_number',
            'status', 'created_at', 'updated_at', 'items',
            'guest_email', 'guest_name', 'comment'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at', 'total_price']
        extra_kwargs = {
            'address': {'required': True},
            'phone_number': {'required': True},
            'guest_name': {'required': False},
            'guest_email': {'required': False},
            'comment': {'required': False}
        }
    
    def get_display_total(self, obj):
        """Возвращает отформатированную общую сумму"""
        return f"{obj.total_price:,} руб.".replace(",", " ")