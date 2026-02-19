from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CategoryViewSet, ProductViewSet, ProductImageViewSet, WoodTypeViewSet, GradeViewSet, CartViewSet, CartItemViewSet, OrderViewSet, OrderItemViewSet, RecommendationView

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
# router.register(r'recommendations', RecommendationViewSet)

urlpatterns = [
    path('', include(router.urls)), 
    path('recommendations/', RecommendationView.as_view(), name='recommendations'),
]