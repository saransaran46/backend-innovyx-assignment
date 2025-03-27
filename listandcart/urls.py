from django.contrib import admin
from django.urls import path
from listandcart import views

urlpatterns = [
    path('auth/register/', views.register_user),
    path('auth/login/', views.login_user),
    path('products/', views.product_list),
    path('products/create/', views.create_product, name='create_product'),
    path('cart/add/', views.add_to_cart, name='add_to_cart'),
    path('cart/', views.view_cart),
    path('cart/remove/<int:item_id>/', views.remove_from_cart),
    path('cart/update/<int:product_id>/', views.update_cart_item,name = 'update_cart_item'),
    path('orders/place/', views.place_order),
    path('orders/history/', views.order_history),
]