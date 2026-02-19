from decimal import Decimal
from rest_framework import serializers
from .models import Category, Product, ProductImage, WoodType, Grade, Cart, CartItem, Order, OrderItem, Recommendation
from django.contrib.auth.models import User
from store.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_staff']

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'image_url', 'parent']

class WoodTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = WoodType
        fields = ['id', 'name']

class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['id', 'name']

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image_url']

class ProductSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        coerce_to_string=False
    )
    category = serializers.CharField(source='category.name', read_only=True)
    wood_type = serializers.CharField(source='wood_type.name', read_only=True)
    grade = serializers.CharField(source='grade.name', read_only=True)
    main_image = serializers.SerializerMethodField()
    
    # Поля для записи - принимаем строковые значения
    category_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    wood_type_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    grade_name = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )
    image_url = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True
    )

    is_active = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'is_active',
            'category', 'wood_type', 'grade',
            'category_name', 'wood_type_name', 'grade_name',
            'main_image', 'image_url'
        ]

    def get_main_image(self, obj):
        first_image = obj.images.first()
        return first_image.image_url if first_image else None

    def validate(self, data):
        """Валидация и преобразование строковых значений в объекты"""
        if 'category_name' in data and data['category_name']:
            try:
                data['category'] = Category.objects.get(name=data.pop('category_name'))
            except Category.DoesNotExist:
                raise serializers.ValidationError({"category_name": "Категория не найдена"})
        
        if 'wood_type_name' in data and data['wood_type_name']:
            try:
                data['wood_type'] = WoodType.objects.get(name=data.pop('wood_type_name'))
            except WoodType.DoesNotExist:
                raise serializers.ValidationError({"wood_type_name": "Порода дерева не найдена"})
        
        if 'grade_name' in data and data['grade_name']:
            try:
                data['grade'] = Grade.objects.get(name=data.pop('grade_name'))
            except Grade.DoesNotExist:
                raise serializers.ValidationError({"grade_name": "Сорт не найден"})
        
        return data

    def create(self, validated_data):
        image_url = validated_data.pop('image_url', None)
        product = Product.objects.create(**validated_data)
        
        if image_url:
            ProductImage.objects.create(product=product, image_url=image_url)
        
        return product

    def update(self, instance, validated_data):
        image_url = validated_data.pop('image_url', None)
        instance = super().update(instance, validated_data)
        
        if image_url:
            instance.images.all().delete()
            ProductImage.objects.create(product=instance, image_url=image_url)
        
        return instance

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        source='product',
        write_only=True
    )

    class Meta:
        model = CartItem
        fields = ['id', 'product', 'product_id', 'quantity']

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)

    class Meta:
        model = Cart
        fields = ['id', 'user', 'items']

class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = ['id', 'product', 'quantity', 'price']
        read_only_fields = ['id', 'price']

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    user = UserSerializer(read_only=True)
    # user = serializers.PrimaryKeyRelatedField(read_only=True)
    
    class Meta:
        model = Order
        fields = [
            'id', 'user', 'total_price', 'address', 'phone_number',
            'status', 'delivery_date', 'delivery_time_interval',
            'payment_method', 'created_at', 'updated_at', 'items'
        ]
        read_only_fields = fields  # Все поля только для чтения

class RecommendationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Recommendation
        fields = ['id', 'question', 'answer']