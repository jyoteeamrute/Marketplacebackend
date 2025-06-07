import logging

from django.core.cache import cache
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from ProfessionalUser.models import *
from ProfessionalUser.serializers import *

logger = logging.getLogger(__name__)


class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

class GetAllUserOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            status_filter = request.query_params.get('status', '').lower()
            user_id_param = request.query_params.get('user_id')
           
            
            paid_filter = status_filter == "paid"
            professional_user = get_object_or_404(ProfessionalUser, email=user.email)
            company = professional_user.company

            company_products = Product.objects.filter(company=company.id)
   
            product_ids = company_products.values_list('id', flat=True)

            order_items = OrderItem.objects.filter(product_id__in=product_ids)
            if user_id_param:
                order_items = order_items.filter(order__user_id=user_id_param)
            order_ids = order_items.values_list('order_id', flat=True).distinct()

            all_orders = Order.objects.filter(id__in=order_ids,is_paid=True).select_related('user')
            status_counter = {
                "accepted": all_orders.filter(orderStatus__iexact="accepted").count(),
                "fulfilled": all_orders.filter(orderStatus__iexact="fulfilled").count(),
                "new_order": all_orders.filter(orderStatus__iexact="new order").count(),
                "cancelled": all_orders.filter(orderStatus__iexact="cancelled").count(),
                "processing": all_orders.filter(orderStatus__iexact="processing").count(),
                "paid": all_orders.filter(is_paid=True).count()
            }

            if status_filter:
                if paid_filter:
                    all_orders = all_orders.filter(is_paid=True)
                else:
                    all_orders = all_orders.filter(orderStatus__iexact=status_filter)

            user_order_map = {}
            total_products = 0

            for order in all_orders:
                customer = order.user
                items = OrderItem.objects.filter(order=order, product__in=company_products).select_related(
                    'product', 'product__categoryId', 'product__subCategoryId'
                )

                if not items.exists():
                    continue

                order_key = f"{customer.id}_{order.id}"


                address = None
                if customer.manualAddress:
                    address = f"{customer.manualAddress.address1}, {customer.manualAddress.city}, {customer.manualAddress.country}, {customer.manualAddress.postalCode}"
                elif customer.automatic_address:
                    address = f"{customer.automatic_address.address1}, {customer.automatic_address.city}, {customer.automatic_address.country}, {customer.automatic_address.postalCode}"

                user_order_map[order_key] = {
                    "id": customer.id,
                    "order_id": order.order_id,
                    "email": customer.email,
                    "customer_name": f"{customer.firstName} {customer.lastName}",
                    "phone": customer.phone,
                    "address": address,
                    "status": order.orderStatus,
                    "ordered_at": order.created_at,
                    "order_type": order.order_type,
                    "bookingDate": order.date,
                    "bookingSlot": order.time,
                    "members": order.members,
                    "customerName": order.customer_name,
                    "customerPhone": order.contact_number,
                    "customerEmail": order.email,
                    "company": {
                        "id": company.id,
                        "name": company.companyName
                    },
                    "productType": None,
                    "is_paid": order.is_paid,
                    "products": [],
                    "total_products_ordered": 0,
                    "subtotal": 0.0,
                    "discount": 0.0,
                    "total_price": 0.0
                }

                for item in items:
                    product = item.product
                    quantity = item.quantity

                    if order.order_type == 'Delivery':
                        price = float(product.priceDelivery or 0)
                    elif order.order_type == 'Click and Collect':
                        price = float(product.priceClickAndCollect or 0)
                    elif order.order_type == 'Onsite':
                        price = float(product.priceOnsite or 0)
                    else:
                        price = float(product.basePrice or 0)

                    line_total = price * quantity
                    promo_total = float(product.promotionalPrice or 0) * quantity

                    user_order_map[order_key]["products"].append({
                        "price": str(line_total),
                        "product": {
                            "id": product.id,
                            "productType": product.productType,
                            "quantity": quantity,
                            "productname": product.productname,
                            "description": product.description,
                            "basePrice": str(product.basePrice),
                            "promotionalPrice": str(product.promotionalPrice),
                            "priceDelivery": str(product.priceDelivery),
                            "priceClickAndCollect": str(product.priceClickAndCollect),
                            "priceOnsite": str(product.priceOnsite),
                            "category": {
                                "id": product.categoryId.id if product.categoryId else None,
                                "name": product.categoryId.name if product.categoryId else None
                            },
                            "subcategory": {
                                "id": product.subCategoryId.id if product.subCategoryId else None,
                                "name": product.subCategoryId.name if product.subCategoryId else None
                            },
                            "ProductImage": request.build_absolute_uri(product.ProductImage.url) if product.ProductImage else None
                        }
                    })

                    user_order_map[order_key]["total_products_ordered"] += quantity
                    user_order_map[order_key]["subtotal"] += line_total
                    user_order_map[order_key]["discount"] += round(line_total - promo_total, 2)
                    user_order_map[order_key]["discount"] = round(user_order_map[order_key]["discount"], 2)

                    user_order_map[order_key]["total_price"] = round(
                        user_order_map[order_key]["subtotal"] - user_order_map[order_key]["discount"], 2
                    )

                    user_order_map[order_key]["productType"] = product.productType
                    total_products += quantity

            sorted_orders = sorted(
                user_order_map.values(),
                key=lambda x: x["ordered_at"],
                reverse=True
            )

            paginator = CustomPagination()
            paginated_data = paginator.paginate_queryset(sorted_orders, request)

            response_data = {
                "status": True,
                "statusCode": 200,
                "message": "All user orders retrieved successfully",
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "total_products_ordered": total_products,
                **status_counter,
                "Orders": len(user_order_map),
                "data": paginated_data
            }


            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error while retrieving orders for user {user.email}: {str(e)}")
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LiveSearchThrottle(UserRateThrottle):
    rate = '20/second'  


class GetUniqueUserOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [LiveSearchThrottle]  

    def get(self, request):
        user = request.user
        professional_user = ProfessionalUser.objects.filter(email=user.email).first()
        if not professional_user:
            return Response({
                "status": False,
                "statusCode": 403,
                "message": "Access denied: Only professional users can view their order data."
            }, status=status.HTTP_200_OK)

        try:
            username_filter = request.query_params.get('username', '').strip().lower()

            cache_key = f"{username_filter or 'all'}"
            cached_response = cache.get(cache_key)
            if cached_response:
                return Response(cached_response, status=status.HTTP_200_OK)

            company = professional_user.company
            company_products = Product.objects.filter(company=company)
            product_ids = company_products.values_list('id', flat=True)

            order_items = OrderItem.objects.filter(product_id__in=product_ids).select_related('order__user', 'product')

            all_orders = Order.objects.filter(id__in=order_items.values_list('order_id', flat=True).distinct()).select_related('user')

            unique_users_map = {}

            for item in order_items.order_by('-order__created_at'):
                order = item.order
                customer = order.user

                full_name = f"{customer.firstName} {customer.lastName}".strip().lower()
                if username_filter and username_filter not in full_name:
                    continue

                if customer.id not in unique_users_map:
                    loyalty_status = random.choice(["Good", "Bad", "Excellent"])  # Optional field
                    unique_users_map[customer.id] = {
                        "user_id": customer.id,
                        "username": f"{customer.firstName} {customer.lastName}",
                        "email": customer.email,
                        "profile_img": customer.profileImage.url if customer.profileImage and hasattr(customer.profileImage, 'url') else None,
                        "order_id": order.id,
                        "last_purchase_date": order.created_at,
                        "last_productname": item.product.productname if item.product else None,
                        "loyalty_status": loyalty_status
                    }

            sorted_data = sorted(unique_users_map.values(), key=lambda x: x["last_purchase_date"], reverse=True)

            paginator = CustomPagination()
            paginated_data = paginator.paginate_queryset(sorted_data, request)

            response_data = {
                "status": True,
                "statusCode": 200,
                "message": "Unique users with orders retrieved successfully",
                "total_pages": paginator.page.paginator.num_pages,
                "total_items": paginator.page.paginator.count,
                "next": paginator.get_next_link(),
                "previous": paginator.get_previous_link(),
                "total_users": len(sorted_data),
                "data": paginated_data
            }

            cache.set(cache_key, response_data, timeout=60 * 5)
            return Response(response_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error while retrieving orders for user {user.email}: {str(e)}")
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
      
          
class OrderUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def put(self, request):
        try:
            order_id = request.query_params.get('order_id')
            
            if not order_id:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "order_id parameter is required"
                }, status=status.HTTP_200_OK)
                
            try:
                order = get_object_or_404(Order, order_id=order_id)
            except Http404:
                return Response({
                    "statusCode": 404,
                    "status": False,
                    "message": "Order not found."
                }, status=status.HTTP_200_OK)

            user = request.user
            
            professional_user = ProfessionalUser.objects.filter(email=user.email).first()
            
            if not professional_user or not order.company or order.company != professional_user.company:
                logger.warning(f"Unauthorized access - Order Professional User: {order.professional_user}")
                logger.warning(f"Unauthorized access - Current User: {professional_user}")
                logger.warning(f"Unauthorized access attempt by {user.email} to update order {order_id}.")
                return Response({
                    "status": False,
                    "statusCode": 403,
                    "message": "You are not authorized to update this order."
                }, status=status.HTTP_200_OK)

            serializer = OrderUpdateSerializer(order, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({
                    "status": True, 
                    "statusCode": 200,
                    "message": "Order updated successfully.",
                    "data": serializer.data
                }, status=status.HTTP_200_OK)
            else:
                logger.error(f"Validation failed for Order {order_id}: {serializer.errors}")
                return Response({
                    "status": False,
                    "statusCode": 400,
                    "message": "Validation failed.",
                    "errors": serializer.errors
                }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error while updating order {order_id}: {str(e)}")
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
class GetCountAllUserOrdersAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            professional_user = get_object_or_404(ProfessionalUser, email=user.email)
            company = professional_user.company

           
            

            orders = Order.objects.filter(company_id=company.id,is_paid=True)
            new_orders_count = orders.filter(orderStatus="new order").count()
            table_reservation_count = 0  
            all_orders_count = orders.count()
            accepted_orders_count = orders.filter(orderStatus="accepted").count()
            paid_orders_count = orders.filter(is_paid=True).count()
            fulfilled_orders_count = orders.filter(orderStatus="fulfilled").count()
            cancelled_orders_count = orders.filter(orderStatus="cancelled").count()
            processing_orders_count = orders.filter(orderStatus="processing").count()

            summary_data = [
                {
                    "id": 1,
                    "name": "New Orders",
                    "status": "Check latest orders",
                    "label": "Go to New Order List",
                    "quantity": new_orders_count,
                    "iconName": "briefcase",
                    "iconType": "Feather"
                },
                {
                    "id": 2,
                    "name": "Table Reservation",
                    "status": "Check latest Reservation",
                    "label": "Go to Reservation List",
                    "quantity": table_reservation_count,
                    "iconName": "table",
                    "iconType": "Octicons"
                },
                {
                    "id": 3,
                    "name": "All Orders",
                    "status": "Check All orders",
                    "label": "Go to All Order List",
                    "quantity": all_orders_count,
                    "iconName": "calendar-minus",
                    "iconType": "MaterialCommunityIcons"
                },
                {
                    "id": 4,
                    "name": "Accepted orders",
                    "status": "Check Accepted orders",
                    "label": "Go to Accepted List",
                    "quantity": accepted_orders_count,
                    "iconName": "checklist",
                    "iconType": "Octicons"
                },
                {
                    "id": 5,
                    "name": "Paid orders",
                    "status": "Check Paid orders",
                    "label": "Go to Paid List",
                    "quantity": paid_orders_count,
                    "iconName": "calendar-check-o",
                    "iconType": "FontAwesome"
                },
                {
                    "id": 6,
                    "name": "Fulfilled orders",
                    "status": "Check Fulfilled orders",
                    "label": "Go to Fulfilled List",
                    "quantity": fulfilled_orders_count,
                    "iconName": "cart-check",
                    "iconType": "MaterialCommunityIcons"
                },
                {
                    "id": 7,
                    "name": "Cancelled orders",
                    "status": "Check Cancelled orders",
                    "label": "Go to Cancelled List",
                    "quantity": cancelled_orders_count,
                    "iconName": "truck-remove-outline",
                    "iconType": "MaterialCommunityIcons"
                },
                {
                    "id": 8,
                    "name": "Processing orders",
                    "status": "Check Processing orders",
                    "label": "Go to Processing Order List",
                    "quantity": processing_orders_count,
                    "iconName": "gear",
                    "iconType": "FontAwesome"
                },
            ]
          

            return Response({
                "status": True,
                "statusCode": 200,
                "message": "Order summary retrieved successfully",
                "data": summary_data
            }, status=status.HTTP_200_OK)

        except Exception as e:
            logger.exception(f"Error while retrieving order summary for user {user.email}: {str(e)}")
            return Response({
                "status": False,
                "statusCode": 500,
                "message": f"Error: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


