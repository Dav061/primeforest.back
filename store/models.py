# store/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.utils.text import slugify


# Модель пользователя (без изменений)
class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Номер телефона")

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


# Модель категории (без изменений)
class Category(models.Model):
    name = models.CharField(max_length=100)
    image_url = models.URLField(blank=True, null=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=100)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


# Модель породы дерева (без изменений)
class WoodType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название породы")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Порода дерева"
        verbose_name_plural = "Породы дерева"


# Модель сорта (без изменений)
class Grade(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название сорта")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Сорт"
        verbose_name_plural = "Сорта"


# НОВАЯ МОДЕЛЬ: Тип единицы измерения
class UnitType(models.Model):
    """
    Тип единицы измерения (штуки, кубы, квадраты, упаковки)
    """
    name = models.CharField(max_length=50, verbose_name="Название", unique=True)
    code = models.CharField(max_length=20, verbose_name="Код", unique=True, 
                           help_text="Например: piece, cubic, square, pack")
    short_name = models.CharField(max_length=10, verbose_name="Краткое название", 
                                 help_text="Например: шт, м³, м², уп")
    
    def __str__(self):
        return f"{self.name} ({self.short_name})"
    
    class Meta:
        verbose_name = "Тип единицы измерения"
        verbose_name_plural = "Типы единиц измерения"


# НОВАЯ МОДЕЛЬ: Вариант цены для товара
class ProductPrice(models.Model):
    """
    Вариант цены для товара с указанием единицы измерения
    Цена - целое число (IntegerField) без копеек
    """
    product = models.ForeignKey('Product', on_delete=models.CASCADE, 
                               related_name='prices', verbose_name="Товар")
    unit_type = models.ForeignKey(UnitType, on_delete=models.PROTECT, 
                                 verbose_name="Тип единицы измерения")
    
    # Цена - целое число (рубли без копеек)
    price = models.IntegerField(
        validators=[MinValueValidator(0)], 
        verbose_name="Цена (руб)",
        help_text="Целое число, без копеек"
    )
    
    # Опционально: количество в единице (для упаковок)
    quantity_per_unit = models.PositiveIntegerField(
        null=True, 
        blank=True, 
        verbose_name="Количество в единице",
        help_text="Например: 6 досок в упаковке"
    )
    
    is_default = models.BooleanField(default=False, verbose_name="По умолчанию")
    
    class Meta:
        verbose_name = "Вариант цены"
        verbose_name_plural = "Варианты цен"
        # Один товар может иметь только одну цену каждого типа
        unique_together = ['product', 'unit_type']
    
    def __str__(self):
        return f"{self.product.name} - {self.unit_type.short_name}: {self.price} руб."
    
    def clean(self):
        """Валидация для разных типов единиц"""
        if self.unit_type.code in ['pack'] and not self.quantity_per_unit:
            raise ValidationError({
                'quantity_per_unit': 'Для упаковок необходимо указать количество в упаковке'
            })


# Модель товара (ОБНОВЛЕННАЯ)
class Product(models.Model):
    name = models.CharField(max_length=255, db_index=True, verbose_name="Название товара")
    description = models.TextField(db_index=True, verbose_name="Описание")
    slug = models.SlugField(unique=True, blank=True, null=True, max_length=255)
    
    # Удаляем старое поле price - теперь цены в ProductPrice
    
    category = models.ForeignKey(Category, on_delete=models.CASCADE, 
                                related_name='products', verbose_name="Категория")
    wood_type = models.ForeignKey(WoodType, on_delete=models.SET_NULL, 
                                 null=True, blank=True, verbose_name="Порода дерева")
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, 
                             null=True, blank=True, verbose_name="Сорт")
    
    # Размеры (для информации)
    width = models.IntegerField(null=True, blank=True, verbose_name="Ширина (мм)")
    thickness = models.IntegerField(null=True, blank=True, verbose_name="Толщина (мм)")
    length = models.IntegerField(null=True, blank=True, verbose_name="Длина (мм)")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField(default=True, verbose_name="Активный")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
    
    objects = models.Manager()
    all_objects = models.Manager()
    
    def get_default_price(self):
        """Возвращает цену по умолчанию"""
        default = self.prices.filter(is_default=True).first()
        if default:
            return default
        return self.prices.first()
    
    def get_price_display(self):
        """Возвращает строку с ценами для отображения"""
        prices = []
        for price in self.prices.all():
            if price.unit_type.code == 'pack' and price.quantity_per_unit:
                prices.append(f"{price.price} руб./{price.unit_type.short_name} ({price.quantity_per_unit} шт)")
            else:
                prices.append(f"{price.price} руб./{price.unit_type.short_name}")
        return " | ".join(prices)


# Модель изображения товара (без изменений)
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, 
                               related_name='images', verbose_name="Товар")
    image_url = models.URLField(verbose_name="Ссылка на изображение")

    def __str__(self):
        return f"Изображение для {self.product.name}"

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"


# Модель корзины (ОБНОВЛЕННАЯ)
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                               related_name='cart', verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"Корзина {self.id} для {self.user.username}"

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"


# Модель элемента корзины (ОБНОВЛЕННАЯ)
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, 
                            related_name='items', verbose_name="Корзина")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    
    # ВАЖНО: Это поле должно быть обязательным и правильно именованным
    selected_price = models.ForeignKey(
        ProductPrice, 
        on_delete=models.PROTECT, 
        verbose_name="Выбранный вариант цены",
        related_name='cart_items'
    )
    
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")

    def __str__(self):
        unit = self.selected_price.unit_type.short_name if self.selected_price else "шт"
        return f"{self.quantity} {unit} x {self.product.name}"

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
    
    @property
    def total_price(self):
        """Общая стоимость позиции"""
        return self.selected_price.price * self.quantity


# Модель заказа (ОБНОВЛЕННАЯ)
class Order(models.Model):
    STATUS_CHOICES = [
        ('in_process', 'В обработке'),
        ('in_working', 'В работе'),
        ('completed', 'Завершен'),
        ('canceled', 'Отменен'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='orders', 
        verbose_name="Пользователь",
        null=True,
        blank=True
    )
    
    total_price = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Общая сумма (руб)"
    )
    address = models.TextField(verbose_name="Адрес доставки")
    phone_number = models.CharField(max_length=15, blank=True, null=True, 
                                   verbose_name="Номер телефона")
    comment = models.TextField(verbose_name="Комментарий к заказу", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, 
                             default='in_process', verbose_name="Статус заказа")
    
    # Поля для гостей
    guest_email = models.EmailField(verbose_name="Email гостя", max_length=254, blank=True, null=True)
    guest_name = models.CharField(verbose_name="Имя гостя", max_length=150, blank=True, null=True)
    session_key = models.CharField(max_length=40, blank=True, null=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        if self.user:
            return f"Заказ {self.id} от {self.user.username}"
        return f"Заказ {self.id} (гость: {self.guest_name or 'неизвестный'})"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"


# Модель элемента заказа (ОБНОВЛЕННАЯ)
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, 
                             related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    
    # НОВОЕ: Сохраняем информацию о выбранной цене
    selected_price_info = models.JSONField(
        verbose_name="Информация о цене",
        help_text="Сохраненная информация о цене на момент заказа",
        default=dict
    )
    
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    
    # Цена за единицу на момент заказа (целое число)
    price_per_unit = models.IntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="Цена за единицу"
    )
    
    unit_type = models.CharField(max_length=20, verbose_name="Тип единицы", default='piece')

    def __str__(self):
        return f"{self.quantity} x {self.product.name} в заказе {self.order.id}"

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"
    
    @property
    def total_price(self):
        """Общая стоимость позиции"""
        return self.price_per_unit * self.quantity