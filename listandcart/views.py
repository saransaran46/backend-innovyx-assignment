from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import Product, Cart, Order, OrderItem
import json
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime

@csrf_exempt
def create_product(request):
    if request.method == 'POST':
        try:
            # Handle form data (including file upload)
            if request.content_type.startswith('multipart/form-data'):
                name = request.POST.get('name')
                price = request.POST.get('price')
                description = request.POST.get('description')
                image_file = request.FILES.get('image')

                # Validate required fields
                if not all([name, price, description]):
                    return JsonResponse(
                        {'error': 'Name, price, and description are required'},
                        status=400
                    )

                # Create product
                product = Product(
                    name=name,
                    price=price,
                    description=description
                )

                # Handle image upload
                if image_file:
                    file_name = default_storage.save(
                        f'products/{datetime.now().timestamp()}_{image_file.name}',
                        ContentFile(image_file.read())
                    )
                    product.image = file_name

                product.save()

                return JsonResponse({
                    'id': product.id,
                    'name': product.name,
                    'price': str(product.price),
                    'description': product.description,
                    'image': request.build_absolute_uri(product.image.url) if product.image else None,
                }, status=201)

            # Handle JSON data
            elif request.content_type == 'application/json':
                data = json.loads(request.body)
                
                # Validate required fields
                if not all([data.get('name'), data.get('price'), data.get('description')]):
                    return JsonResponse(
                        {'error': 'Name, price, and description are required'},
                        status=400
                    )

                # Create product
                product = Product.objects.create(
                    name=data['name'],
                    price=data['price'],
                    description=data['description']
                )

                return JsonResponse({
                    'id': product.id,
                    'name': product.name,
                    'price': str(product.price),
                    'description': product.description,
                    'image': None,  # Images can't be uploaded via JSON
                    'created_at': product.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }, status=201)

            else:
                return JsonResponse(
                    {'error': 'Unsupported content type'},
                    status=400
                )

        except Exception as e:
            return JsonResponse(
                {'error': str(e)},
                status=500
            )

    return JsonResponse(
        {'error': 'Only POST method is allowed'},
        status=405
    )



@csrf_exempt
def product_list(request):
    if request.method == 'GET':
        products = Product.objects.all()
        data = []
        for product in products:
            data.append({
                'id': product.id,
                'name': product.name,
                'price': str(product.price),
                'description': product.description,
                'image': request.build_absolute_uri(product.image.url) if product.image else None
            })
        return JsonResponse(data, safe=False)






@csrf_exempt
def add_to_cart(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        product_id = data.get('product_id')
        quantity = data.get('quantity', 1)
        
        product = get_object_or_404(Product, id=product_id)
        cart_item, created = Cart.objects.get_or_create(
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            cart_item.quantity += quantity
            cart_item.save()
            
        return JsonResponse({'success': True})



def view_cart(request):
    if request.method == 'GET':
        cart_items = Cart.objects.filter(user=request.user)
        data = []
        total = 0
        
        for item in cart_items:
            item_total = item.product.price * item.quantity
            total += item_total
            data.append({
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'price': str(item.product.price),
                'quantity': item.quantity,
                'item_total': str(item_total),
                'image': request.build_absolute_uri(item.product.image.url) if item.product.image else None
            })
            
        return JsonResponse({
            'items': data,
            'total': str(total)
        })


@csrf_exempt
def remove_from_cart(request, item_id):
    if request.method == 'DELETE':
        cart_item = get_object_or_404(Cart, id=item_id, user=request.user)
        cart_item.delete()
        return JsonResponse({'success': True})






@csrf_exempt
def update_cart_item(request, product_id):
    if request.method == 'PUT':
        try:
            data = json.loads(request.body)
            quantity = data.get('quantity')
            
            if quantity is None:
                return JsonResponse({'error': 'Quantity is required'}, status=400)
            
            if int(quantity) <= 0:
                return remove_from_cart(request, product_id)
                
            cart = request.session.get('cart', {})
            
            if str(product_id) in cart:
                cart[str(product_id)] = int(quantity)
                request.session.modified = True
                
                product = get_object_or_404(Product, id=product_id)
                item_total = product.price * int(quantity)
                
                return JsonResponse({
                    'success': True,
                    'product_id': product_id,
                    'quantity': quantity,
                    'item_total': str(item_total)
                })
            else:
                return JsonResponse({
                    'error': 'Product not in cart'
                }, status=404)
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def place_order(request):
    if request.method == 'POST':
        cart_items = Cart.objects.filter(user=request.user)
        if not cart_items.exists():
            return JsonResponse({'error': 'Cart is empty'}, status=400)
            
        total_amount = sum(item.product.price * item.quantity for item in cart_items)
        order = Order.objects.create(
            user=request.user,
            total_amount=total_amount
        )
        
        for item in cart_items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price=item.product.price
            )
            item.delete()
            
        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'total_amount': str(total_amount)
        })


def order_history(request):
    if request.method == 'GET':
        orders = Order.objects.filter(user=request.user).order_by('-created_at')
        data = []
        
        for order in orders:
            items = []
            for item in order.items.all():
                items.append({
                    'product_name': item.product.name,
                    'quantity': item.quantity,
                    'price': str(item.price),
                    'item_total': str(item.price * item.quantity)
                })
                
            data.append({
                'order_id': order.id,
                'total_amount': str(order.total_amount),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'items': items
            })
            
        return JsonResponse(data, safe=False)