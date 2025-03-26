from django.contrib import admin
from django.urls import path
from listandcart import views

urlpatterns = [
    path('products/', views.product_list),
    path('products/create/', views.create_product, name='create_product'),
    path('cart/add/', views.add_to_cart),
    path('cart/', views.view_cart),
    path('cart/remove/<int:item_id>/', views.remove_from_cart),
    path('orders/place/', views.place_order),
    path('orders/history/', views.order_history),
]