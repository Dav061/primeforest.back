from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, ProductViewSet, ProductImageViewSet, 
    WoodTypeViewSet, GradeViewSet, CartViewSet, CartItemViewSet, 
    OrderViewSet, OrderItemViewSet,
    TelegramNotificationView, UnitTypeViewSet, ProductPriceViewSet, DebugAuthView    # Импортируем КЛАСС
)

router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'woodtypes', WoodTypeViewSet)
router.register(r'grades', GradeViewSet)
router.register(r'products', ProductViewSet)
router.register(r'productimages', ProductImageViewSet)
router.register(r'carts', CartViewSet)
router.register(r'cartitems', CartItemViewSet)
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'orderitems', OrderItemViewSet)
router.register(r'unit-types', UnitTypeViewSet)  # Новый
router.register(r'product-prices', ProductPriceViewSet)  # Новый

urlpatterns = [
    path('', include(router.urls)), 

    # store/urls.py - добавьте этот путь
    path('api/debug-auth/', DebugAuthView.as_view(), name='debug-auth'),

    # ИСПРАВЛЕНО: используем as_view() для класса
    path('telegram-notification/', TelegramNotificationView.as_view(), name='telegram-notification'),
]