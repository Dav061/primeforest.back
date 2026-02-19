from decimal import Decimal
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator


# Модель пользователя
class User(AbstractUser):
    phone_number = models.CharField(max_length=15, blank=True, null=True, verbose_name="Номер телефона")

    def __str__(self):
        return self.username

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


# Модель категории
class Category(models.Model):
    name = models.CharField(max_length=100)
    image_url = models.URLField(blank=True, null=True)  # Поле для изображения
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"


# Модель породы дерева
class WoodType(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название породы")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Порода дерева"
        verbose_name_plural = "Породы дерева"


# Модель сорта
class Grade(models.Model):
    name = models.CharField(max_length=100, verbose_name="Название сорта")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Сорт"
        verbose_name_plural = "Сорта"


# Модель товара
class Product(models.Model):
    name = models.CharField(max_length=255, db_index=True, verbose_name="Название товара")
    description = models.TextField(db_index=True, verbose_name="Описание")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], db_index=True, verbose_name="Цена")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Категория")
    wood_type = models.ForeignKey(WoodType, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Порода дерева")
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Сорт")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    is_active = models.BooleanField(default=True, verbose_name="Активный")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        # Добавляем фильтр по умолчанию, чтобы неактивные товары не показывались
        default_manager_name = 'objects'
    
    # Добавляем менеджер, который по умолчанию показывает только активные товары
    objects = models.Manager()
    all_objects = models.Manager()  # Для доступа ко всем товарам, включая неактивные


# Модель изображения товара
class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="Товар")
    image_url = models.URLField(verbose_name="Ссылка на изображение")

    def __str__(self):
        return f"Изображение для {self.product.name}"

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"


# Модель корзины
class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', verbose_name="Пользователь")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"Корзина {self.id} для {self.user.username}"

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"


# Модель элемента корзины
class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Корзина")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Количество")

    def __str__(self):
        return f"{self.quantity} x {self.product.name} в корзине {self.cart.id}"

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"


# Модель заказа
class Order(models.Model):
    STATUS_CHOICES = [
        ('in_process', 'В процессе'),
        ('completed', 'Завершен'),
        ('canceled', 'Отменен'),
    ]
    
    TIME_INTERVAL_CHOICES = [
        ('9-12', '9:00 - 12:00'),
        ('12-15', '12:00 - 15:00'),
        ('15-18', '15:00 - 18:00'),
        ('18-21', '18:00 - 21:00'),
    ]
    
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Наличными при получении'),
        ('transfer', 'Переводом при получении'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Пользователь")
    total_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        null=False,  # Важно: поле не может быть NULL
        blank=False
    )
    address = models.TextField(verbose_name="Адрес доставки")
    phone_number = models.CharField(max_length=20, verbose_name="Номер телефона", blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='in_process', verbose_name="Статус заказа")
    delivery_date = models.DateField(verbose_name="Дата доставки", null=True, blank=True)
    delivery_time_interval = models.CharField(
        max_length=20, 
        choices=TIME_INTERVAL_CHOICES, 
        verbose_name="Временной интервал доставки",
        null=True,
        blank=True
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
        verbose_name="Способ оплаты"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")

    def __str__(self):
        return f"Заказ {self.id} от {self.user.username}"

    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"

# Модель элемента заказа
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items', verbose_name="Заказ")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Товар")
    quantity = models.PositiveIntegerField(verbose_name="Количество")
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)], verbose_name="Цена")

    def __str__(self):
        return f"{self.quantity} x {self.product.name} в заказе {self.order.id}"

    class Meta:
        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"


# Модель рекомендации
class Recommendation(models.Model):
    question = models.CharField(max_length=255, verbose_name="Вопрос")
    answer = models.TextField(verbose_name="Ответ")

    def __str__(self):
        return self.question

    class Meta:
        verbose_name = "Рекомендация"
        verbose_name_plural = "Рекомендации"