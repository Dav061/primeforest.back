from django.contrib import admin
from .models import (
    User, Category, WoodType, Grade, Product, 
    ProductImage, Cart, CartItem, Order, OrderItem,
    UnitType, ProductPrice  # Добавляем новые модели
)

# Регистрация моделей
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'phone_number', 'is_staff')
    search_fields = ('username', 'email', 'phone_number')

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent')
    list_filter = ('parent',)
    search_fields = ('name',)

@admin.register(WoodType)
class WoodTypeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(UnitType)  # НОВОЕ
class UnitTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'short_name')
    search_fields = ('name', 'code')

class ProductPriceInline(admin.TabularInline):  # НОВОЕ (для отображения цен внутри товара)
    model = ProductPrice
    extra = 1
    fields = ('unit_type', 'price', 'quantity_per_unit', 'is_default')

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_prices_display', 'category', 'wood_type', 'grade', 'is_active')
    list_filter = ('category', 'wood_type', 'grade', 'is_active')
    search_fields = ('name', 'description')
    inlines = [ProductPriceInline, ProductImageInline]  # Добавляем цены и фото
    
    def get_prices_display(self, obj):
        """Отображение цен в списке товаров"""
        prices = obj.prices.all()
        if not prices:
            return "Цены не указаны"
        return " | ".join([f"{p.price}₽/{p.unit_type.short_name}" for p in prices])
    get_prices_display.short_description = "Цены"

@admin.register(ProductPrice)  # НОВОЕ
class ProductPriceAdmin(admin.ModelAdmin):
    list_display = ('product', 'unit_type', 'price', 'quantity_per_unit', 'is_default')
    list_filter = ('unit_type', 'is_default')
    search_fields = ('product__name',)

@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image_url')
    search_fields = ('product__name',)

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at', 'updated_at')
    search_fields = ('user__username',)

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'selected_price', 'quantity', 'total_price')
    list_filter = ('selected_price__unit_type',)
    search_fields = ('cart__user__username', 'product__name')
    
    def total_price(self, obj):
        return f"{obj.total_price} ₽"
    total_price.short_description = "Сумма"

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'guest_name', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'guest_name', 'guest_email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        ('Информация о заказе', {
            'fields': ('status', 'total_price', 'address', 'phone_number', 'comment')
        }),
        ('Клиент', {
            'fields': ('user', 'guest_name', 'guest_email', 'session_key')
        }),
        ('Даты', {
            'fields': ('created_at', 'updated_at')
        }),
    )

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price_per_unit', 'unit_type', 'total_price')
    list_filter = ('unit_type',)
    search_fields = ('order__user__username', 'product__name')
    
    def total_price(self, obj):
        return f"{obj.total_price} ₽"
    total_price.short_description = "Сумма"