from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from .models import Product, Cart, Order, OrderItem
import json
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from datetime import datetime
from django.db import transaction

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
                    price=float(price),  # Convert to float
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
                    price=float(data['price']),  # Convert to float
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

from django.contrib.auth import authenticate
from rest_framework.authtoken.models import Token
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
import json

@csrf_exempt
def add_to_cart(request):
    if request.method == 'POST':
        try:
            # Extract token from headers
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]  # Extract the token key
            try:
                token = Token.objects.get(key=token_key)
                user = token.user  # Get the authenticated user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            # Process the request data
            data = json.loads(request.body)
            product_id = data.get('product_id')
            quantity = data.get('quantity', 1)
            
            if not product_id:
                return JsonResponse({'error': 'product_id is required'}, status=400)
            
            product = get_object_or_404(Product, id=product_id)
            
            cart_item, created = Cart.objects.get_or_create(
                user=user,  # Use the authenticated user
                product=product,
                defaults={'quantity': quantity}
            )
            
            if not created:
                cart_item.quantity += int(quantity)
                cart_item.save()
                
            return JsonResponse({'success': True})
        
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)




@csrf_exempt
def view_cart(request):
    if request.method == 'GET':
        try:
            # Token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                user = token.user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            # Get cart items for the authenticated user
            cart_items = Cart.objects.filter(user=user)
            data = []
            total = 0
            
            for item in cart_items:
                try:
                    item_total = item.product.price * item.quantity
                    total += item_total
                    
                    # Handle product image URL safely
                    image_url = None
                    if item.product.image:
                        image_url = request.build_absolute_uri(item.product.image.url)
                    
                    data.append({
                        'id': item.id,
                        'product_id': item.product.id,
                        'product_name': item.product.name,
                        'price': str(item.product.price),
                        'quantity': item.quantity,
                        'item_total': str(item_total),
                        'image': image_url
                    })
                except Exception as e:
                    # Skip problematic items but continue processing others
                    continue
            
            return JsonResponse({
                'success': True,
                'items': data,
                'total': str(total),
                'count': len(data)
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'error': 'Only GET method is allowed'
    }, status=405)





@csrf_exempt
def remove_from_cart(request, item_id):
    if request.method == 'DELETE':
        try:
            # Token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                user = token.user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            # Verify the item belongs to the authenticated user
            cart_item = get_object_or_404(Cart, id=item_id, user=user)
            
            # Delete the item
            cart_item.delete()
            
            return JsonResponse({
                'success': True,
                'message': 'Item removed from cart successfully',
                'removed_item_id': item_id
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
    
    return JsonResponse({
        'error': 'Only DELETE method is allowed'
    }, status=405)





@csrf_exempt
def update_cart_item(request, product_id):
    if request.method == 'PUT':
        try:
            # Token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                user = token.user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            # Process request data
            data = json.loads(request.body)
            quantity = data.get('quantity')
            
            if quantity is None:
                return JsonResponse({'error': 'Quantity is required'}, status=400)
            
            quantity = int(quantity)
            cart_item = get_object_or_404(Cart, product_id=product_id, user=user)
            
            if quantity <= 0:
                cart_item.delete()
                return JsonResponse({'success': True, 'message': 'Item removed from cart'})
                
            cart_item.quantity = quantity
            cart_item.save()
            
            product = cart_item.product
            item_total = product.price * quantity
            
            return JsonResponse({
                'success': True,
                'product_id': product_id,
                'quantity': quantity,
                'item_total': str(item_total),
                'product_name': product.name,
                'unit_price': str(product.price)
            })
                
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except ValueError:
            return JsonResponse({'error': 'Quantity must be a number'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Only PUT method is allowed'}, status=405)







@csrf_exempt
def place_order(request):
    if request.method == 'POST':
        try:
            # Token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                user = token.user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            # Process order
            cart_items = Cart.objects.filter(user=user)
            if not cart_items.exists():
                return JsonResponse({'error': 'Cart is empty'}, status=400)
                
            total_amount = sum(item.product.price * item.quantity for item in cart_items)
            
            with transaction.atomic():
                order = Order.objects.create(
                    user=user,
                    total_amount=total_amount  # No status field
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
                'total_amount': str(total_amount),
                'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Only POST method is allowed'}, status=405)



@csrf_exempt
def order_history(request):
    if request.method == 'GET':
        try:
            # Token authentication
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Token '):
                return JsonResponse({'error': 'Token authentication required'}, status=401)
            
            token_key = auth_header.split(' ')[1]
            try:
                token = Token.objects.get(key=token_key)
                user = token.user
            except Token.DoesNotExist:
                return JsonResponse({'error': 'Invalid token'}, status=401)

            orders = Order.objects.filter(user=user).order_by('-created_at')
            data = []
            
            for order in orders:
                items = []
                # USE THE DEFINED RELATED NAME 'items' INSTEAD OF 'orderitem_set'
                for item in order.items.all():  # This matches your related_name
                    items.append({
                        'product_id': item.product.id,
                        'product_name': item.product.name,
                        'quantity': item.quantity,
                        'price': str(item.price),
                        'item_total': str(item.price * item.quantity)
                    })
                    
                order_data = {
                    'order_id': order.id,
                    'total_amount': str(order.total_amount),
                    'created_at': order.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'items': items
                }
                
                data.append(order_data)
                
            return JsonResponse({
                'success': True,
                'orders': data,
                'count': len(data)
            }, safe=False)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Only GET method is allowed'}, status=405)



from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from rest_framework.authtoken.models import Token



@csrf_exempt
def register_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            email = data.get('email')
            username = data.get('username')
            password = data.get('password')

            if not all([email, username, password]):
                return JsonResponse(
                    {'error': 'Email, username and password are required'},
                    status=400
                )

            if User.objects.filter(email=email).exists():
                return JsonResponse(
                    {'error': 'Email already exists'},
                    status=400
                )

            if User.objects.filter(username=username).exists():
                return JsonResponse(
                    {'error': 'Username already exists'},
                    status=400
                )

            user = User.objects.create_user(
                username=username,
                email=email,
                password=password
            )

            # Create a token for the new user
            token = Token.objects.create(user=user)

            return JsonResponse({
                'success': True,
                'message': 'User registered successfully',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email
                },
                'token': token.key
            }, status=201)

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse(
        {'error': 'Only POST method is allowed'},
        status=405
    )

@csrf_exempt
def login_user(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')
            password = data.get('password')

            if not all([username, password]):
                return JsonResponse(
                    {'error': 'Username and password are required'},
                    status=400
                )

            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                # Get or create token for the user
                token, created = Token.objects.get_or_create(user=user)
                return JsonResponse({
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email
                    },
                    'token': token.key
                })
            else:
                return JsonResponse(
                    {'error': 'Invalid credentials'},
                    status=401
                )

        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse(
        {'error': 'Only POST method is allowed'},
        status=405
    )

@csrf_exempt
def logout_user(request):
    if request.method == 'POST':
        try:
            # Delete the token if using TokenAuthentication
            if hasattr(request, 'auth'):
                request.auth.delete()
            logout(request)
            return JsonResponse({'success': True, 'message': 'Logout successful'})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Only POST method is allowed'}, status=405)