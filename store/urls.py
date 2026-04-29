# store/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, ProductViewSet, ProductImageViewSet, 
    WoodTypeViewSet, GradeViewSet, CartViewSet, CartItemViewSet, 
    OrderViewSet, OrderItemViewSet, UnitTypeViewSet, ProductPriceViewSet,
    DebugAuthView, CallbackRequestView
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
router.register(r'unit-types', UnitTypeViewSet)
router.register(r'product-prices', ProductPriceViewSet)

urlpatterns = [
    path('', include(router.urls)),  # все router пути уже с api/ из главного urls
    path('callback/', CallbackRequestView.as_view(), name='callback'),  # Убрали api/
    path('debug-auth/', DebugAuthView.as_view(), name='debug-auth'),  # Убрали api/
]