from collections import defaultdict
from decimal import Decimal, InvalidOperation

from django.core.cache import cache
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import *
from ProfessionalUser.serializers import *
from ProfessionalUser.signals import *
from ProfessionalUser.utils import *
from UserApp.models import *
from UserApp.serializers import *
from UserApp.utils import *


class AddToCartAPIView(APIView):
    permission_classes = [IsAuthenticated]
    ORDER_TYPE_MAPPING = {
        1: 'Onsite',
        2: 'Click and Collect',
        3: 'Delivery',
        4: 'Result'
    }

    def post(self, request):
        user = request.user
        product_data = request.data

        product_id = product_data.get('product_id')
        company_id = product_data.get('company_id')
        quantity = int(product_data.get('quantity', 0))
        action = product_data.get('action', 'set')
        order_type_key = product_data.get('order_type_key')  

        if order_type_key is None:
            return Response({
                'message': 'order_type_key is required.',
                'statusCode': 400,
                'status': False
            }, status=status.HTTP_200_OK)

        try:
            order_type_key = int(order_type_key)
        except ValueError:
            return Response({
                'message': 'order_type_key must be an integer.',
                'statusCode': 400,
                'status': False
            }, status=status.HTTP_200_OK)

        order_type = self.ORDER_TYPE_MAPPING.get(order_type_key)
        if not order_type:
            return Response({
                'message': f'Invalid order_type_key. Allowed keys: {list(self.ORDER_TYPE_MAPPING.keys())}',
                'statusCode': 400,
                'status': False
            }, status=status.HTTP_200_OK)

        if not all([product_id, company_id]):
            return Response({
                'message': 'product_id and company_id are required.',
                'statusCode': 400,
                'status': False
            }, status=status.HTTP_200_OK)

        try:
            company = get_object_or_404(CompanyDetails, id=company_id)
            product = Product.objects.filter(id=product_id, company=company).first()
            if product.quantity is None:
                return Response({
                    'message': 'Product stock quantity is not set.',
                    'statusCode': 400,
                    'status': False
                }, status=status.HTTP_200_OK)

            if product.quantity < quantity:
                return Response({
                    'message': f'Insufficient stock. Only {product.quantity} units available.',
                    'statusCode': 400,
                    'status': False
                }, status=status.HTTP_200_OK)

            existing_cart_qs=Cart.objects.filter(
                user=user,
                company=company,
                product__categoryId=product.categoryId  # Correct field name!
            ).exclude(order_type=order_type)

            if existing_cart_qs.exists():
                return Response({
                    'message': f'You already have products in cart for this company and category with a different order_type.',
                    'statusCode': 400,
                    'status': False
                }, status=status.HTTP_200_OK)

            cart_item, created = Cart.objects.get_or_create(
                user=user, product=product, company=company, order_type=order_type
            )

            if action == 'increment':
                cart_item.quantity += quantity
            elif action == 'decrement':
                cart_item.quantity = max(0, cart_item.quantity - quantity)
            else:
                cart_item.quantity = quantity

            if cart_item.quantity == 0:
                cart_item.delete()
            else:
                cart_item.save()

            cache_key = f"order_detail_user_{user.id}_company_{company_id}"
            cache.delete(cache_key)

            return Response({
                'message': 'Product added/updated in cart',
                'statusCode': 200,
                'status': True,
                'user': UserSerializer(user).data,
                'cart_items': CartSerializer(Cart.objects.filter(user=user), many=True).data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                'message': f'Error: {str(e)}',
                'statusCode': 500,
                'status': False
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        


class CompanyCartDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        from decimal import Decimal, InvalidOperation

        ORDER_TYPE_REVERSE_MAP = {
            'Onsite': 1,
            'Click and Collect': 2,
            'Delivery': 3,
            'Result': 4,
        }

        company = get_object_or_404(CompanyDetails, id=company_id)
        category_id = request.query_params.get('category_id')
        if not category_id:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "category_id is required"
            }, status=status.HTTP_200_OK)

        cart_items = Cart.objects.filter(
            user=request.user,
            company_id=company_id,
            product__categoryId=category_id
        ).select_related('product', 'product__categoryId')

        if not cart_items.exists():
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "No items found for this category",
                "company": company.companyName,
                "company_id": company.id,
                "cart_by_order_type": {}
            }, status=status.HTTP_200_OK)

        cart = cart_items.first()
        serialized_items = CartProductSerializer(cart_items, many=True).data

        total_price = Decimal(sum(item.get_item_total() for item in cart_items))
        subtotal = Decimal(sum(item.get_item_total() for item in cart_items))

        vat_rates = [
            item.product.vatRate or 0 for item in cart_items
            if hasattr(item.product, 'vatRate')
        ]
        avg_vat_rate = round(sum(vat_rates) / len(vat_rates), 2) if vat_rates else 0

        discount_amount = Decimal('0.00')
        promocode = cart.promo_code if cart else None

        if promocode:
            now = timezone.now()
            if (not promocode.startDateTime or promocode.startDateTime <= now) and \
               (not promocode.endDateTime or promocode.endDateTime >= now):

                try:
                    discount_amount = Decimal(promocode.specificAmount or 0)
                except (ValueError, InvalidOperation):
                    discount_amount = Decimal('0.00')

                total_price -= discount_amount
                total_price = max(total_price, Decimal('0.00'))

        key_value = ORDER_TYPE_REVERSE_MAP.get(cart.order_type) if cart else None

        grouped_data = {
            "items": serialized_items,
            "total_quantity": sum(item.quantity for item in cart_items),
            "total_price": round(total_price, 2),
            "subtotal":round(subtotal, 2),
            "vat_rate":avg_vat_rate,
            "discount_applied": discount_amount,
            "key": key_value,
            "promocode": promocode.promocode if promocode else None,
            "promocodeID": promocode.id if promocode else None,
            "note": cart.note if cart else None,
        }

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Data fetched successfully",
            "company": company.companyName,
            "company_id": company.id,
            "cart_by_order_type": grouped_data
        }, status=status.HTTP_200_OK)

    



class MyCartGroupedAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        cart_qs = Cart.objects.filter(user=user).select_related('company', 'product', 'product__categoryId')

        group_key_map = defaultdict(list)
        for item in cart_qs:
            if item.company and item.product and item.product.categoryId:
                key = (item.company.id, item.order_type, item.product.categoryId.id)
                group_key_map[key].append(item)

        grouped_data = []
        for (company_id, order_type, category_id), items in group_key_map.items():
            company = items[0].company
            total_price = 0
            for item in items:
                price = item.product.get_price_by_order_type(item.order_type)
                if price is not None:
                    total_price += price * item.quantity

            grouped_data.append({
                "company": {
                    "company_id": company.id,
                    "company_name": company.companyName,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company.manual_address else None
                },
                "category_id": category_id,
                "order_type": order_type,
                "item_count": len(items),
                "total_price": round(total_price, 2)
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "data retrieved successfully",
            "data": grouped_data        
        }, status=status.HTTP_200_OK)




ORDER_TYPE_MAP = {
    "1": "Onsite",
    "2": "Click and Collect",
    "3": "Delivery",
    "4": "onhome",
}

class UpdateCartMetaAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, company_id, order_type):
        logger.info(f"UpdateCartMeta PUT called by user {request.user.id} for company {company_id} and order_type {order_type}")
        logger.debug(f"Request data: {request.data}")

        order_type_str = ORDER_TYPE_MAP.get(str(order_type))
        if not order_type_str:
            logger.warning(f"Invalid order type provided: {order_type}")
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid order type."
            }, status=200)

        cart_items = Cart.objects.filter(
            user=request.user,
            company_id=company_id,
            order_type=order_type_str
        )

        if not cart_items.exists():
            logger.warning("No cart items found for update.")
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "No cart items found for this company and order type."
            }, status=200)

        for cart in cart_items:
            update_data = {}
            promo_code_id = request.data.get("promo_code")
            if promo_code_id:
                try:
                    promo = Promocode.objects.get(id=promo_code_id)
                    cart.promo_code = promo
                except Promocode.DoesNotExist:
                    return Response({
                        "statusCode": 400,
                        "status": False,
                        "message": "Invalid promo code ID."
                    }, status=200)

            if "note" in request.data:
                cart.note = request.data.get("note")
            if order_type_str == "Onsite":
                date = request.data.get("date")
                time = request.data.get("time")
                members = request.data.get("members")
                if any([date, time, members]):
                    if not all([date, time, members]):
                        return Response({
                            "statusCode": 400,
                            "status": False,
                            "message": "Date, time, and members are required together for onsite orders."
                        }, status=200)
                    update_data.update({
                        "date": date,
                        "time": time,
                        "members": members
                    })

            elif order_type_str == "Click and Collect":
                name = request.data.get("customer_name")
                contact = request.data.get("contact_number")
                email = request.data.get("email")
                if any([name, contact, email]):
                    if not all([name, contact, email]):
                        return Response({
                            "statusCode": 400,
                            "status": False,
                            "message": "Customer name, contact number, and email are required together for click & collect."
                        }, status=200)
                    update_data.update({
                        "customer_name": name,
                        "contact_number": contact,
                        "email": email
                    })

            elif order_type_str == "Delivery":
                address_id = request.data.get("address_id")
                if address_id:
                    try:
                        address = userAddress.objects.get(id=address_id, user=request.user)
                        update_data["address"] = address
                    except userAddress.DoesNotExist:
                        return Response({
                            "statusCode": 400,
                            "status": False,
                            "message": "Invalid or unauthorized address ID."
                        }, status=200)

            elif order_type_str == "onhome":
                manual_address = request.data.get("address")
                if manual_address:
                    update_data["manual_address"] = manual_address

            for key, value in update_data.items():
                setattr(cart, key, value)

            cart.save()

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Cart metadata updated successfully."
        }, status=200)
    

class CreateOrderAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, company_id, order_type):
        user = request.user

        order_type_str = ORDER_TYPE_MAP.get(str(order_type))
        if not order_type_str:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Invalid order type."
            }, status=status.HTTP_200_OK)

        cart_items = Cart.objects.filter(user=user, company_id=company_id, order_type=order_type_str)
        
        if not cart_items.exists():
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "No cart items found for this company and order type."
            }, status=status.HTTP_200_OK)

        company = get_object_or_404(CompanyDetails, id=company_id)
        cart_meta = cart_items.first()
        total_price = 0

        for item in cart_items:
            price = item.product.get_price_by_order_type(item.order_type)
            if price is None:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"Missing price for product: {item.product.productname}."
                }, status=status.HTTP_200_OK)
            total_price += price * item.quantity

        if cart_meta.promo_code and cart_meta.promo_code.specificAmount:
            try:
                discount = Decimal(cart_meta.promo_code.specificAmount)
                total_price = max(total_price - discount, Decimal('0'))
            except Exception:
                pass
        
       
        order_data = {
            "user": user,
            "company": company,
            "order_type": order_type_str,
            "promo_code": cart_meta.promo_code,
            "note": cart_meta.note,
            "total_price": total_price,
        }

        if order_type_str == "Onsite":
            if not all([cart_meta.date, cart_meta.time, cart_meta.members]):
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Onsite order requires date, time, and members."
                }, status=status.HTTP_200_OK)
            order_data.update({
                "date": cart_meta.date,
                "time": cart_meta.time,
                "members": cart_meta.members
            })

        elif order_type_str == "Click and Collect":
            if not all([cart_meta.customer_name, cart_meta.contact_number, cart_meta.email]):
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Click & Collect requires name, contact number, and email."
                }, status=status.HTTP_200_OK)
            order_data.update({
                "customer_name": cart_meta.customer_name,
                "contact_number": cart_meta.contact_number,
                "email": cart_meta.email
            })

        elif order_type_str == "Delivery":
            if not cart_meta.address:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Delivery order requires an address ID."
                }, status=status.HTTP_200_OK)
            order_data["user_address"] = cart_meta.address

        elif order_type_str == "onhome":
            if not cart_meta.manual_address:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Home service requires manual address."
                }, status=status.HTTP_200_OK)
            order_data["manual_address"] = cart_meta.manual_address
        order = Order.objects.create(**order_data)

        for item in cart_items:
            price = item.product.get_price_by_order_type(item.order_type)
            OrderItem.objects.create(order=order, product=item.product, quantity=item.quantity, price=price)
        professional_user = ProfessionalUser.objects.filter(company=company).first()

        receiver_user = None
        if professional_user and professional_user.email:
            receiver_user = ProfessionalUser.objects.filter(email=professional_user.email).first()
           

        try:
            if receiver_user:
                Notification.objects.create(
                    professional_user=receiver_user,
                    sender=request.user,
                    title="New Order Created",
                    message=f"{request.user.username} has created a new order: #{order.order_id}",
                    notification_type="order"
                )
                try:
                    push_message = f"{request.user.username} placed a new order: #{order.order_id}"
                    print(push_message)
                    success = get_player_ids_by_professional_id(pro_user_id=receiver_user.id, content=push_message)
                    if not success:
                        print("Push failed or no players found.")
                except Exception as push_error:
                    print(f"Push notification error: {push_error}")
            else:
                print("No matching ProfessionalUser found for push.")

            return Response({
                "statusCode": 200,
                "status": True,
                'id':order.id,
                "message": "Order create successfully.",
                "order_id": order.order_id
            }, status=status.HTTP_200_OK)
        
        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"Internal Server : {str(e)}",
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




class PromoCodeListView(APIView):
    def get(self, request, company_id):
        search = request.query_params.get('search', '')
        now = timezone.now()

        queryset = Promocode.objects.filter(company_id=company_id)

        if search:
            queryset = queryset.filter(
                Q(promocode__icontains=search) |
                Q(title__icontains=search)
            )

        serializer = PromocodeSerializer(queryset, many=True)

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Promo codes retrieved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)

class UserOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        orders = Order.objects.filter(
    user=user,
    orderStatus__in=["rejected","fulfilled" "accepted", "new order","paid", "processing"]
).prefetch_related(
    'order_items__product', 'company__manual_address'
)
       
        reviewed_product_ids = request.session.get('reviewed_products', [])

        grouped_orders = []
        now = timezone.localtime()
        current_weekday = now.strftime('%A').lower()

        for order in orders:
            company = order.company
            items = order.order_items.all()
            prep_time = None
            time_left = None
            is_open = False

            if company:
                if order.order_type == "Onsite":
                    prep_time = order.onSitePreparationTime
                elif order.order_type == "Click and Collect":
                    prep_time = order.clickCollectPreparationTime
                elif order.order_type == "Delivery":
                    prep_time = order.deliveryPreparationTime

                if prep_time:
                    ready_time = order.created_at + timedelta(
                        hours=prep_time.hour,
                        minutes=prep_time.minute,
                        seconds=prep_time.second
                    )
                    delta = ready_time - now
                    time_left = str(delta).split('.')[0] if delta.total_seconds() > 0 else "Ready"
                day_hours = company.opening_hours.get(current_weekday) if company.opening_hours else None

                if day_hours and day_hours.get("start") and day_hours.get("end"):
                    try:
                        start_time = datetime.strptime(day_hours["start"], "%H:%M").time()
                        end_time = datetime.strptime(day_hours["end"], "%H:%M").time()
                        current_time = now.time()

                        if start_time < end_time:
                            is_open = start_time <= current_time <= end_time
                        else:
                            is_open = current_time >= start_time or current_time <= end_time
                    except Exception as e:
                        print(f"Opening hours error: {e}")
                        is_open = False
            products_list = []
            for item in items:
                product = item.product
                if product:
                    is_rating_pending = product.id not in reviewed_product_ids
                    
                    products_list.append({
                        "product_id": product.id,
                        "product_name": product.productname,
                        "product_image": request.build_absolute_uri(product.ProductImage.url) if product.ProductImage else default_image_url("product_images"),
                        "quantity": item.quantity,
                        "price": round(item.price, 2),
                        "average_rating": product.average_rating,
                        "total_ratings": product.total_ratings,
                        "is_rating_pending": is_rating_pending  # Flag added here
                    })
            grouped_orders.append({
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "item_count": items.count(),
                "status": "pending" if order.orderStatus in ["new order", "processing"] else order.orderStatus,  
                "order_id": order.order_id,
                "total_price": round(order.total_price, 2),
                "order_type": order.order_type,
                "preparation_time": str(prep_time) if prep_time else None,
                "time_left": time_left,
                "order_date": order.created_at.strftime("%d-%b-%Y"),
                "products": products_list
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "User orders fetched successfully",
            "orders": grouped_orders
        }, status=status.HTTP_200_OK)


from datetime import date, datetime, timedelta
from operator import itemgetter

from django.utils import timezone

three_days_ago = timezone.now() - timedelta(days=3)

class UserOrdersAPIViewNew(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
      
        now = timezone.localtime()
        
        current_weekday = now.strftime('%A').lower()

        grouped_orders = []
        reviewed_product_ids = request.session.get('reviewed_products', [])
        orders = Order.objects.filter(
            user=user,
            is_paid=True
        ).prefetch_related('order_items__product', 'company__manual_address')
        is_open = False
        for order in orders:
            company = order.company
            items = order.order_items.all()
            prep_time = time_left = None
            is_open = False

            if company:
                if order.order_type == "Onsite":
                    prep_time = order.onSitePreparationTime
                elif order.order_type == "Click and Collect":
                    prep_time = order.clickCollectPreparationTime
                elif order.order_type == "Delivery":
                    prep_time = order.deliveryPreparationTime

                if prep_time:
                    ready_time = order.created_at + timedelta(
                        hours=prep_time.hour,
                        minutes=prep_time.minute,
                        seconds=prep_time.second
                    )
                    delta = ready_time - now
                    time_left = str(delta).split('.')[0] if delta.total_seconds() > 0 else "Ready"

                day_hours = company.opening_hours.get(current_weekday) if company.opening_hours else None
                if day_hours and day_hours.get("start") and day_hours.get("end"):
                    try:
                        start = datetime.strptime(day_hours["start"], "%H:%M").time()
                        end = datetime.strptime(day_hours["end"], "%H:%M").time()
                        current_time = now.time()
                        is_open = start <= current_time <= end if start < end else current_time >= start or current_time <= end
                    except Exception as e:
                        print("Opening hours error:", e)

            products_list = [{
                "product_id": item.product.id,
                "product_name": item.product.productname,
                "product_image": request.build_absolute_uri(item.product.ProductImage.url) if item.product.ProductImage else default_image_url("product_images"),
                "quantity": item.quantity,
                "price": round(item.price, 2),
                "average_rating": item.product.average_rating,
                "total_ratings": item.product.total_ratings,
                "is_rating_pending": item.product.id not in reviewed_product_ids
            } for item in items if item.product]

            first_product = items[0].product if items and items[0].product else None
            first_product_image_url = (
                request.build_absolute_uri(first_product.ProductImage.url)
                if first_product and first_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "orders",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": first_product_image_url,  
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "item_count": items.count(),
                # "status": order.orderStatus,
                "status": "pending" if order.orderStatus in ["new order"] else order.orderStatus,
                "order_id": order.order_id,
                "booking_id":order.order_id,
                "total_price": round(order.total_price, 2),
                "order_type": order.order_type,
                "preparation_time": str(prep_time) if prep_time else None,
                "time_left": time_left,
                "cancel_by": order.cancel_by,
                "order_date": order.created_at.strftime("%d-%b-%Y"),
                "created_at": order.created_at,
                "products": products_list
            })
        room_bookings = RoomBooking.objects.filter(user=user,is_paid=True).select_related('company', 'room', 'product')
        for rb in room_bookings:
            company = rb.company
            ticket_product = rb.product
            ticket_image_url = (
                request.build_absolute_uri(ticket_product.ProductImage.url)
                if ticket_product and ticket_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "booking",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": ticket_image_url,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "name": rb.room.product.productname if rb.room and rb.room.product else None,
                "room_quantity": rb.room_quantity,
                "adults": rb.adults,
                "order_id":rb.booking_id,
                "booking_id":rb.booking_id,
                "pets": rb.pets,
                "is_paid": rb.is_paid,
                "total_price": float(rb.total_price or 0),
                # "status": rb.booking_status,
                "status": "cancelled" if rb.booking_status in ["cancelled", "rejected"] else rb.booking_status,
                "checkin_date": rb.checkin_date.strftime("%d-%b-%Y") if rb.checkin_date else None,
                "checkout_date": rb.checkout_date.strftime("%d-%b-%Y") if rb.checkout_date else None,
                "order_date": rb.booking_date.strftime("%d-%b-%Y") if rb.booking_date else None,
                "created_at": rb.created_at,
                "cancel_by": rb.cancel_by,
                "expires_at": rb.expires_at.strftime("%d-%b-%Y") if rb.expires_at else None

            })
        event_bookings = eventBooking.objects.filter(user=user,is_paid=True).prefetch_related('ticket_items__ticket')
        for eb in event_bookings:
            company = eb.company
            ticket_product = eb.ticket_id
            ticket_image_url = (
                request.build_absolute_uri(ticket_product.ProductImage.url)
                if ticket_product and ticket_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "booking",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": ticket_image_url,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "order_type": eb.ticket_type,
                "order_id": eb.booking_id,
                "booking_id":eb.booking_id,
                "name": eb.ticket_id.productname if eb.ticket_id else None,
                "number_of_people": eb.number_of_people,
                "total_price": float(eb.price or 0),
                # "status": eb.status,
                "status": "cancelled" if eb.status in ["cancelled", "rejected"] else eb.status,
                "is_paid": eb.is_paid,
                "cancel_by": eb.cancel_by,
                "order_date": eb.booking_date.strftime("%d-%b-%Y") if eb.booking_date else None,
                "created_at": eb.created_at,
                "booking_time": eb.booking_time.strftime("%I:%M %p") if eb.booking_time else None,

            })
        experience_bookings = experienceBooking.objects.filter(user=user,is_paid=True)
        for exb in experience_bookings:
            company = exb.company
            ticket_product = exb.ticket_id
            ticket_image_url = (
                request.build_absolute_uri(ticket_product.ProductImage.url)
                if ticket_product and ticket_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "booking",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": ticket_image_url,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "order_type": exb.ticket_type,
                "name": exb.ticket_id.productname if exb.ticket_id else None,
                "total_price": float(exb.price or 0),
                # "status": exb.status,
                "status": "cancelled" if exb.status in ["cancelled", "rejected"] else exb.status,
                "order_id":exb.booking_id,
                "booking_id":exb.booking_id,
                "is_paid": exb.is_paid,
                "cancel_by": exb.cancel_by,
                "full_name": exb.full_name,
                "order_date": exb.booking_date.strftime("%d-%b-%Y") if exb.booking_date else None,
                "created_at": exb.created_at,
                "booking_time": exb.booking_time.strftime("%I:%M %p") if exb.booking_time else None,
                "end_date": exb.end_date.strftime("%d-%b-%Y") if exb.end_date else None,
                "adults": exb.adult,
                "children": exb.children,
                "number_of_people": exb.number_of_people
            })
        slot_bookings = slotBooking.objects.filter(user=user,is_paid=True)
        for exb in slot_bookings:
            company = exb.company
            ticket_product = exb.Product
            ticket_image_url = (
                request.build_absolute_uri(ticket_product.ProductImage.url)
                if ticket_product and ticket_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "booking",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": ticket_image_url,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "slot": exb.slot.strftime("%I:%M %p") if exb.slot else None,
                "name": exb.Product.productname if exb.Product else None,
                "total_price": float(exb.price or 0),
                # "status": exb.status,
                "status": "cancelled" if exb.status in ["cancelled", "rejected"] else exb.status,
                "order_id":exb.booking_id,
                "booking_id":exb.booking_id,
                "is_paid": exb.is_paid,
                "cancel_by": exb.cancel_by,
                "full_name": exb.full_name,
                "order_date": exb.booking_date.strftime("%d-%b-%Y") if exb.booking_date else None,
                "created_at": exb.created_at,
                "booking_time": exb.booking_time.strftime("%I:%M %p") if exb.booking_time else None,
                
                
                "number_of_people": exb.number_of_people
            })
        
        aesthetics_qs = aestheticsBooking.objects.filter(user=user,is_paid=True)
        for exb in aesthetics_qs:
            company = exb.company
            ticket_product = exb.Product
            ticket_image_url = (
                request.build_absolute_uri(ticket_product.ProductImage.url)
                if ticket_product and ticket_product.ProductImage else
                default_image_url("product_images")
            )
            grouped_orders.append({
                "type": "booking",
                "company": {
                    "company_id": company.id if company else None,
                    "company_name": company.companyName if company else "Unknown",
                    "product_image": ticket_image_url,
                    "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                    "company_address": company.manual_address.address1 if company and company.manual_address else None,
                    "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                    "companyratings": company.average_rating if company else 0.0,
                    "is_open": is_open
                },
                "slot": exb.slot.strftime("%I:%M %p") if exb.slot else None,
                "name": exb.Product.productname if exb.Product else None,
                "total_price": float(exb.price or 0),
                # "status": exb.status,
                "status": "cancelled" if exb.status in ["cancelled", "rejected"] else exb.status,
                "order_id":exb.booking_id,
                "booking_id":exb.booking_id,
                "is_paid": exb.is_paid,
                "cancel_by": exb.cancel_by,
                "full_name": exb.full_name,
                "order_date": exb.booking_date.strftime("%d-%b-%Y") if exb.booking_date else None,
                "created_at": exb.created_at,
                "booking_time": exb.booking_time.strftime("%I:%M %p") if exb.booking_time else None,
                
                
                "number_of_people": exb.number_of_people
            })
            relaxation_qs = relaxationBooking.objects.filter(user=user,is_paid=True)
            for exb in relaxation_qs:
                company = exb.company
                ticket_product = exb.Product
                ticket_image_url = (
                    request.build_absolute_uri(ticket_product.ProductImage.url)
                    if ticket_product and ticket_product.ProductImage else
                    default_image_url("product_images")
                )
                grouped_orders.append({
                    "type": "booking",
                    "company": {
                        "company_id": company.id if company else None,
                        "company_name": company.companyName if company else "Unknown",
                        "product_image": ticket_image_url,
                        "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                        "company_address": company.manual_address.address1 if company and company.manual_address else None,
                        "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                        "companyratings": company.average_rating if company else 0.0,
                        "is_open": is_open
                    },
                    "slot": exb.slot.strftime("%I:%M %p") if exb.slot else None,
                    "name": exb.Product.productname if exb.Product else None,
                    "total_price": float(exb.price or 0),
                    # "status": exb.status,
                    "status": "cancelled" if exb.status in ["cancelled", "rejected"] else exb.status,
                    "order_id":exb.booking_id,
                    "booking_id":exb.booking_id,
                    "is_paid": exb.is_paid,
                    "cancel_by": exb.cancel_by,
                    "full_name": exb.full_name,
                    "order_date": exb.booking_date.strftime("%d-%b-%Y") if exb.booking_date else None,
                    "created_at": exb.created_at,
                    "booking_time": exb.booking_time.strftime("%I:%M %p") if exb.booking_time else None,
                    
                    
                    "number_of_people": exb.number_of_people

                })   
            art_culture_qs = artandcultureBooking.objects.filter(user=user,is_paid=True)
            for exb in art_culture_qs:
                company = exb.company
                ticket_product = exb.Product
                ticket_image_url = (
                    request.build_absolute_uri(ticket_product.ProductImage.url)
                    if ticket_product and ticket_product.ProductImage else
                    default_image_url("product_images")
                )
                grouped_orders.append({
                    "type": "booking",
                    "company": {
                        "company_id": company.id if company else None,
                        "company_name": company.companyName if company else "Unknown",
                         "product_image": ticket_image_url,
                        "company_profile_photo": request.build_absolute_uri(company.profilePhoto.url) if company and company.profilePhoto else default_image_url("product_images"),
                        "company_address": company.manual_address.address1 if company and company.manual_address else None,
                        "company_pincode": company.manual_address.postalCode if company and company.manual_address else None,
                        "companyratings": company.average_rating if company else 0.0,
                        "is_open": is_open
                    },
                    "slot": exb.slot.strftime("%I:%M %p") if exb.slot else None,
                    "name": exb.Product.productname if exb.Product else None,
                    "total_price": float(exb.price or 0),
                    # "status": exb.status,
                    "status": "cancelled" if exb.status in ["cancelled", "rejected"] else exb.status,
                    "order_id":exb.booking_id,
                    "booking_id":exb.booking_id,
                    "is_paid": exb.is_paid,
                    "cancel_by": exb.cancel_by,
                    "full_name": exb.full_name,
                    "order_date": exb.booking_date.strftime("%d-%b-%Y") if exb.booking_date else None,
                    "created_at": exb.created_at,
                    "booking_time": exb.booking_time.strftime("%I:%M %p") if exb.booking_time else None,
                    
                    
                    "number_of_people": exb.number_of_people
                })

       
        for item in grouped_orders:
            created_at = item.get("created_at")
            if created_at:
                if isinstance(created_at, date) and not isinstance(created_at, datetime):
                    created_at = datetime.combine(created_at, datetime.min.time())
                if timezone.is_naive(created_at):
                    created_at = timezone.make_aware(created_at)
            else:
                created_at = datetime.min.replace(tzinfo=timezone.utc)

            item["created_at"] = created_at
        grouped_orders.sort(key=itemgetter("created_at"), reverse=True)
        for item in grouped_orders:
            item.pop("created_at", None)

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "All bookings and orders in unified list",
            "orders": grouped_orders
        }, status=status.HTTP_200_OK)


def safe_url(field, bucket_folder="uploads"):
    if field:
        path = str(field)
        if path.startswith("http"):
            return path
        filename = path.split("/")[-1]
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{bucket_folder}/{filename}"
    return ""


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, company_id):
        

        category_id = request.query_params.get('category_id')
        cart_items = Cart.objects.filter(user=request.user, company_id=company_id, product__categoryId_id=category_id ).select_related('product', 'product__categoryId')
        if not cart_items.exists():
            return Response({"status": False,"statusCode": 200, "message": "No cart found for this company."}, status=status.HTTP_200_OK)

        order = cart_items.first()

        items_data = []
        total_price = Decimal('0.00')
        for item in cart_items:
            product = item.product
            unit_price = product.get_price_by_order_type(item.order_type)
            subtotal = Decimal(str(unit_price or 0)) * item.quantity
            total_price += subtotal
            items_data.append({
                "product_id": product.id,
                "name": product.productname,
                "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                "unit_price": str(unit_price),
                "quantity": item.quantity,
                "subtotal": str(subtotal)
            })

        promo_code = order.promo_code
        discount_amount = Decimal('0.00')

        if promo_code:
            now = timezone.now()
            if (not promo_code.startDateTime or promo_code.startDateTime <= now) and \
               (not promo_code.endDateTime or promo_code.endDateTime >= now):

                specific_amount = promo_code.specificAmount

                if specific_amount is not None:
                    try:
                        discount_amount = Decimal(specific_amount)
                    except (ValueError, InvalidOperation):
                        discount_amount = Decimal('0.00')
                else:
                    discount_amount = Decimal('0.00')

        final_price = max(total_price - discount_amount, Decimal('0.00'))
        customerdetails =None
        delivery_address = None
        if order.order_type == 'Onsite' and order.company:
            delivery_address = {
                "address":f"{order.user.manualAddress.address1 or ''}{order.user.manualAddress.address2 or ''} {order.user.manualAddress.country or ''} {order.user.manualAddress.city or ''}  {order.user.manualAddress.postalCode or ''} ",
                "contact_name": f"{order.user.firstName} {order.user.lastName}",
                "contact_phone": order.user.phone
            }
            customerdetails={
                "name": f"{order.user.firstName} {order.user.lastName}",
                "phone":order.user.phone,
                "address":f"{order.user.manualAddress.address1 or ''}{order.user.manualAddress.address2 or ''} {order.user.manualAddress.country or ''} {order.user.manualAddress.city or ''}  {order.user.manualAddress.postalCode or ''} ",

            }
        elif order.order_type == 'Delivery' and order.address:
            user_address = order.address
            delivery_address = {
                
                 "address":f"{user_address.house_building or ''}{user_address.road_area_colony or ''} {user_address.city or ''} {user_address.state or ''}  {user_address.pincode or ''} ",
                "contact_name":  f"{user_address.first_name or ''} {user_address.last_name or ''}".strip(),
                "contact_phone": user_address.phone_number

            }
            customerdetails={
                "name":f"{user_address.first_name or ''} {user_address.last_name or ''}".strip(),
                "phone": user_address.phone_number,
                "address":f"{user_address.house_building or ''}{user_address.road_area_colony or ''} {user_address.city or ''}{user_address.state or ''} - {user_address.pincode or ''}"

            }
        elif order.order_type == 'Click and Collect' and order.company:
            delivery_address =  {
                "address":f"{order.user.manualAddress.address1 or ''}{order.user.manualAddress.address2 or ''} {order.user.manualAddress.country or ''} {order.user.manualAddress.city or ''}  {order.user.manualAddress.postalCode or ''} ",
                "contact_name": order.customer_name,
                "contact_phone": order.contact_number
            }
            customerdetails={
                "name":order.customer_name,
                "phone": order.contact_number,
                "address":f"{order.user.manualAddress.address1 or ''}{order.user.manualAddress.address2 or ''} {order.user.manualAddress.country or ''} {order.user.manualAddress.city or ''}  {order.user.manualAddress.postalCode or ''} ",
               
            }
        response_data = {
            "statusCode": 200,
            "status": True,
            "order_id": order.id,
            "order_type": order.order_type,
            "key": next((k for k, v in ORDER_TYPE_MAP.items() if v == order.order_type), None),
            "created_at": order.created_at.strftime("%a %d,%Y") if order.created_at else None,
            "customer":customerdetails,
            "items": items_data,
            "pricing": {
                "subtotal": str(total_price),
                "discount": order.promo_code.specificAmount if order.promo_code else None,
                "total_price":final_price
            },
            "delivery_details": delivery_address
        }

        return Response(response_data,status=status.HTTP_200_OK)


import logging

logger = logging.getLogger(__name__)
from decimal import Decimal


class FulfilledOrderDetailView(APIView):
    permission_classes = [IsAuthenticated]
    

    def get(self, request, order_id):
        try:
            order = Order.objects.get(order_id=order_id, user=request.user)
            return self.process_order(order, request)
        except Order.DoesNotExist:
            pass  # Continue to check booking IDs
        if order_id.startswith("ROM"):
            try:
                booking = RoomBooking.objects.get(booking_id=order_id, user=request.user)
            except RoomBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No  booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = RoomBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.product
                review = Review.objects.filter(user=request.user, product=booking.room.product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": booking.room.product.id,
                    "name": booking.room.product.productname,
                    "image": safe_url(booking.room.product.ProductImage, "product_images") if booking.room.product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.room.bookedQuantity,
                    "rated": review is not None,
                    "unit_price": booking.room.roomPrice ,
                    "subtotal": (booking.room.roomPrice or 0) * (booking.room.bookedQuantity or 0),
                    "rating": rating
                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.booking_status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.product.productname if booking.product else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": (booking.room.roomPrice or 0) * (booking.room.bookedQuantity or 0),   
                    "discount":booking.room.product.discount,
                    "total_price":booking.total_price

                
                }
            }, status=status.HTTP_200_OK)
        if order_id.startswith("EVT"):
            try:
                booking = eventBooking.objects.get(booking_id=order_id, user=request.user)
            except eventBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = eventBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.ticket_id
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.ticket_id.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.ticket_id.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.ticket_id.discount)*(subtotal)/100
            total_price =(booking.price)
            
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.ticket_id.productname if booking.ticket_id else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price

                
                }
            }, status=status.HTTP_200_OK)
        
        if order_id.startswith("RLX"):
            try:
                booking = relaxationBooking.objects.get(booking_id=order_id, user=request.user)
            except relaxationBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No relaxation booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = relaxationBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.Product
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.Product.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.Product.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.Product.discount)*(subtotal)/100
            total_price =(booking.price)

            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Relaxation booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.Product.productname if booking.Product else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price

                
                }
            }, status=status.HTTP_200_OK)

        if order_id.startswith("SLT"):
            try:
                booking = slotBooking.objects.get(booking_id=order_id, user=request.user)
            except slotBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No  booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = slotBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.Product
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.Product.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.Product.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.Product.discount)*(subtotal)/100
            total_price =(booking.price)
            
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "slot": booking.slot,
                "full_name": booking.full_name,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.Product.productname if booking.Product else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price

                
                }
            }, status=status.HTTP_200_OK)    
        
        if order_id.startswith("AST"):
            try:
                booking = aestheticsBooking.objects.get(booking_id=order_id, user=request.user)
            except aestheticsBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No  booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = aestheticsBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.Product
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.Product.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.Product.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.Product.discount)*(subtotal)/100
            total_price =(booking.price)

    
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.Product.productname if booking.Product else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price
                }
            }, status=status.HTTP_200_OK) 

        if order_id.startswith("EXP"):
            try:
                booking = experienceBooking.objects.get(booking_id=order_id, user=request.user)
            except experienceBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No  booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = experienceBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.ticket_id
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.ticket_id.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.ticket_id.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.ticket_id.discount)*(subtotal)/100
            total_price =(booking.price)
            
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.ticket_id.productname if booking.ticket_id else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price

                
                }
            }, status=status.HTTP_200_OK) 

        elif order_id.startswith("ATC"):
            try:
                booking = artandcultureBooking.objects.get(booking_id=order_id, user=request.user)
            except artandcultureBooking.DoesNotExist:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "No  booking found with this ID.",
                    "data": None
                }, status=status.HTTP_200_OK)
            try:
                booking = artandcultureBooking.objects.get(booking_id=order_id, user=request.user)

                product = booking.Product
                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data = {
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "quantity": booking.number_of_people,
                    "rated": review is not None,
                    "unit_price": booking.Product.promotionalPrice ,
                    "subtotal": (product.promotionalPrice or 0) * (booking.number_of_people or 0),
                    "rating": rating

                    
                },
            except Exception as e:
                logger.error(f"Error fetching order items for order {order_id}: {str(e)}")
                return Response({
                    "statusCode": 500,
                    "status": False,
                    "message": "Failed to process order items.",
                    "data": None
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            
            delivery_address = None
            customerdetails = None
            subtotal= (booking.Product.promotionalPrice or 0) * (booking.number_of_people or 0) 
            discount=(booking.Product.discount)*(subtotal)/100
            total_price =(booking.price)
            
            address = booking.user.manualAddress
            delivery_address = {
                "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                "contact_name": f"{booking.user.firstName} {booking.user.lastName}",
                "contact_phone": booking.user.phone
            }
            customerdetails = {
                "name": f"{booking.user.firstName} {booking.user.lastName}",
                "phone": booking.user.phone,
                "address": delivery_address["address"]
            }
        
            return Response({
                "statusCode": 200,
                "status": True,
                "message": " booking details fetched successfully.",
                
                "order_id": booking.booking_id,
                "order_type": "Onsite",
                "order_status": booking.status,
                "created_at": booking.created_at.strftime("%a %d, %Y") if booking.created_at else None,
                "room_name": booking.Product.productname if booking.Product else None,
                "booking_date": booking.booking_date.strftime("%a %d, %Y") if booking.booking_date else None,
                "is_paid": booking.is_paid,
                "customer": customerdetails,
                "delivery_details": delivery_address,
                "items": items_data,
                
                "pricing":{
                    "subtotal": subtotal,   
                    "discount":discount,
                    "total_price":total_price

                
                }
            }, status=status.HTTP_200_OK)
             
    def process_order(self, order, request):
        try:
            order_items = OrderItem.objects.filter(order=order)
            items_data = []
            total_price = Decimal('0.00')

            for item in order_items:
                product = item.product
                unit_price = product.get_price_by_order_type(order.order_type)
                subtotal = Decimal(str(unit_price or 0)) * item.quantity
                total_price += subtotal

                review = Review.objects.filter(user=request.user, product=product).first()
                rating = review.rating if review else None

                items_data.append({
                    "product_id": product.id,
                    "name": product.productname,
                    "image": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "unit_price": str(unit_price),
                    "quantity": item.quantity,
                    "subtotal": str(subtotal),
                    "rated": review is not None,
                    "rating": rating
                })

            discount_amount = Decimal('0.00')
            if order.promo_code:
                now = timezone.now()
                promo_code = order.promo_code
                if (not promo_code.startDateTime or promo_code.startDateTime <= now) and \
                   (not promo_code.endDateTime or promo_code.endDateTime >= now):
                    discount_amount = Decimal(promo_code.specificAmount or 0)

            final_price = max(total_price - discount_amount, Decimal('0.00'))

            delivery_address = None
            customerdetails = None

            if order.order_type == 'Onsite':
                address = order.user.manualAddress
                delivery_address = {
                    "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                    "contact_name": f"{order.user.firstName} {order.user.lastName}",
                    "contact_phone": order.user.phone
                }
                customerdetails = {
                    "name": f"{order.user.firstName} {order.user.lastName}",
                    "phone": order.user.phone,
                    "address": delivery_address["address"]
                }

            elif order.order_type == 'Delivery':
                user_address = order.user_address
                delivery_address = {
                    "full_name": f"{user_address.first_name or ''} {user_address.last_name or ''}".strip(),
                    "phone_number": user_address.phone_number,
                    "house_building": user_address.house_building,
                    "road_area_colony": user_address.road_area_colony,
                    "address":user_address.road_area_colony,
                    "city": user_address.city,
                    "state": user_address.state,
                    "pincode": user_address.pincode,
                    "address_type": user_address.address_type,
                }
                customerdetails = {
                    "name": delivery_address["full_name"],
                    "phone": user_address.phone_number,
                    "address": f"{user_address.house_building or ''} {user_address.road_area_colony or ''} {user_address.city or ''} {user_address.state or ''} - {user_address.pincode or ''}"
                }

            elif order.order_type == 'Click and Collect':
                address = order.user.manualAddress
                delivery_address = {
                    "address": f"{address.address1 or ''} {address.address2 or ''} {address.country or ''} {address.city or ''} {address.postalCode or ''}",
                    "contact_name": order.customer_name,
                    "contact_phone": order.contact_number
                }
                customerdetails = {
                    "name": order.customer_name,
                    "phone": order.contact_number,
                    "address": delivery_address["address"]
                }
            else:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Invalid order type.",
                    "data": None
                }, status=status.HTTP_200_OK)

            response_data = {
                "statusCode": 200,
                "status": True,
                "message": "Order tracking details fetched successfully.",
                "order_id": order.order_id,
                "order_type": order.order_type,
                "order_status": order.orderStatus,
                "created_at": order.created_at.strftime("%a %d, %Y") if order.created_at else None,
                "customer": customerdetails,
                "items": items_data,
                "pricing": {
                    "subtotal": str(total_price),
                    "discount": str(discount_amount),
                    "total_price": str(final_price)
                },
                "delivery_details": delivery_address
            }
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f"Error processing order {order.order_id}: {str(e)}")
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred while processing the order.",
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

   


class OrderTrackingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = get_object_or_404(Order, order_id=order_id, user=request.user)

            serializer = OrderTrackingSerializer(order, context={"request": request})
            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Order tracking details fetched successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": f"An error occurred while fetching order: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
