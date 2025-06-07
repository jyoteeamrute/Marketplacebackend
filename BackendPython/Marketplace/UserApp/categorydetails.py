from datetime import datetime, timedelta

from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import *
from ProfessionalUser.serializers import *
from UserApp.serializers import *
from UserApp.utils import *


class cruiseDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            if product.categoryId.slug.lower() != "travel" or product.subCategoryId.slug.lower().strip()  != "cruises_pleasure_boats":

                return Response({
                    "message": "This product is not a Cruise under the Travel category",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)
            

            start_address = AddressSerializer(product.startAddress).data if product.startAddress else None
            end_address = AddressSerializer(product.endAddress).data if product.endAddress else None

            cruise_rooms = CruiseRoom.objects.filter(product=product)
            cruise_rooms_data = CruiseRoomSerializer(cruise_rooms, many=True).data
            

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "discount":product.discount,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime":format_time(product.availabilityDateTime),
                "availabilityTime":format_time(product.availabilityDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "start_address": start_address,
                "end_address": end_address,
                "pet_allowed": product.petAllowed,
                "pet_type": [
    {"pet_id": str(i+1), "pet_name": pet} for i, pet in enumerate(product.petType)
] if product.petType else [],
                "cruise_name": product.cruiseName,
                "rooms": cruise_rooms_data,
                "facility": list(product.cruiseFacility.values('id', 'name')) if product.cruiseFacility.exists() else []
                

            }

            return Response({
                "message": "Cruise details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 404,
                "status": False,
                "data": None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class hotelDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"hotels","guest_houses","camping","inns_lodges","chalets_cabins","unusual_accommodation"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "travel" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the travel category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)


            start_address = AddressSerializer(product.startAddress).data if product.startAddress else None
            end_address = AddressSerializer(product.endAddress).data if product.endAddress else None

            cruise_rooms = CruiseRoom.objects.filter(product=product)

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime":format_time(product.availabilityDateTime),
                "availabilityTime":format_time(product.availabilityDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "start_address": start_address,
                "end_address": end_address,
                "pet_allowed": product.petAllowed,
                "smoking":product.smokingAllowed,
                "pet_type": [
    {"pet_id": str(i+1), "pet_name": pet} for i, pet in enumerate(product.petType)
] if product.petType else [],
                "cruise_name": product.cruiseName,
                "facility": list(product.roomFacility.values('id', 'name')) if product.roomFacility.exists() else [],
                "view":product.roomview,
                "member":product.noofMembers,
                "roomQuantity":product.quantity


            }

            return Response({
                "message": "Cruise details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 404,
                "status": False,
                "data": None
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)








class MusicDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"concerts","music_festivals","nightclubs"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "music" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the Music category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)

            
            if subcategory_slug == "nightclubs":
                tickets_qs = NightClubTicket.objects.filter(product=product)
                Tickets = NightClubTicketSerializer(tickets_qs, many=True).data
            else:
                tickets_qs = TicketsConcert.objects.filter(product=product)
                Tickets = TicketsConcertSerializer(tickets_qs, many=True).data
            
            
            for ticket in Tickets:
                ticket["current_quantity"] = 0
            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
              "duration": str(product.duration) + " hr",
                "ticket":Tickets,
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
                
            }

            return Response({
                "message": "Music product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class nightclubsDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"nightclubs"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "music" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the Music category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)
        
            Ticketer = NightClubTicket.objects.filter(product=product)
            Tickets = NightClubTicketSerializer(Ticketer, many=True).data
            for ticket in Tickets:
                 ticket["current_quantity"] = 0
                 

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration": str(product.duration) + " hr",
                "ticket":Tickets
            }

            return Response({
                "message": "Music product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        





class experienceDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"amusement_parks","activities_for_children","animal_encounters","experiences"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "experiences" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)
        
            Ticketer = TicketsAmusementPark.objects.filter(product=product)
            Tickets = TicketsAmusementParkSerializer(Ticketer, many=True).data

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "on_delivery": product.onDelivery,
                "members":product.noofMembers,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":str(product.duration) + " hr",
                "ticket":Tickets,
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




class eventDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"events","workshops"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "experiences" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)
            
            Ticketer = TicketsConcert.objects.filter(product=product)
            Tickets = TicketsConcertSerializer(Ticketer, many=True).data
            for ticket in Tickets:
                ticket["current_quantity"] = 0


            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "members":product.noofMembers,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":product.duration,
                "ticket":Tickets,
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime),
                
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class guidedDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"guided_tours","personalized_course"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "experiences" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "members":product.noofMembers,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "time_slots": get_slot_start_times(product.startTime, product.endTime, product.duration),
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":str(product.duration) + " hr",
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class sportsDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"sport", "nautical_activity"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "experiences" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)
            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "duration": product.duration,
                "time_slots": get_slot_start_times(product.startTime, product.endTime, product.duration),
                "start_address": {
                    "address1": product.startAddress.address1 if product.startAddress else "",
                    "address2": product.startAddress.address2 if product.startAddress else "",
                    "city": product.startAddress.city if product.startAddress else "",
                    "state": product.startAddress.country if product.startAddress else "",
                },
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "categorySlug": product.categoryId.slug,
                "subcategorySlug": product.subCategoryId.slug,
                "duration":str(product.duration) + " hr",
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)




class aestheticsDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"hairsalons","barbers","tattoos_piercings","manicure_pedicure_salons","makeup","hair_removal","tanning_services","facial_body_hair_treatments"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "aesthetics" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "members":product.noofMembers,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "time_slots": get_slot_start_times(product.startTime, product.endTime, product.duration),
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":str(product.duration) + " hr",
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        



class relaxationDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"spa_swimming_pool","massage_well_being","meditation_relaxation","alternative_therapies"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "relaxation" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the experiences category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "members":product.noofMembers,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "time_slots": get_slot_start_times(product.startTime, product.endTime, product.duration),
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":str(product.duration) + " hr",
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        




class artandcultureDetailView(APIView):
    def get(self, request, product_id):
        try:
            product = get_object_or_404(Product, id=product_id)

            valid_subcategories = {"museums_art_galleries","theaters_operas","cinema_videos","libraries","history_heritage","cultural_festivals"}
            category_slug = product.categoryId.slug.lower()
            subcategory_slug = product.subCategoryId.slug.lower().strip()

            if category_slug != "art_and_culture" or subcategory_slug not in valid_subcategories:
                return Response({
                    "message": "This product is not under the artandculture category with a valid subcategory.",
                    "statusCode": 400,
                    "status": False,
                    "data": None
                }, status=status.HTTP_200_OK)

            product_data = {
                "id": product.id,
                "product_name": product.productname,
                "description": product.description,
                "product_type": product.productType,
                "price_onsite": product.priceOnsite,
                "price_click_and_collect": product.priceClickAndCollect,
                "price_delivery": product.priceDelivery,
                "promotional_price": product.promotionalPrice,
                "vat_rate": product.vatRate,
                "delivery_method": product.deliveryMethod,
                "preparationDate": format_date(product.preparationDateTime),
                "availabilityDate": format_date(product.availabilityDateTime),
                "preparationTime": format_time(product.preparationDateTime),
                "availabilityTime": format_time(product.availabilityDateTime),
                "date_range": get_date_range(product.availabilityDateTime, product.preparationDateTime),
                "on_delivery": product.onDelivery,
                "onsite": product.onsite,
                "click_and_collect": product.clickandCollect,
                "service_time": product.serviceTime,
                "base_price": product.basePrice,
                "non_restaurant": product.nonRestaurant,
                "delivery": product.delivery,
                "keywords": product.keywords,
                "start_address": {
    "address1": product.startAddress.address1 if product.startAddress else "",
    "address2": product.startAddress.address2 if product.startAddress else "",
    "city": product.startAddress.city if product.startAddress else "",
    "state": product.startAddress.country if product.startAddress else "",
},              
                "time_slots": get_slot_start_times(product.startTime, product.endTime, product.duration),
                "image": product.ProductImage.url if product.ProductImage else None,
                "gallery_images": product.galleryImage,
                "average_rating": product.average_rating,
                "total_ratings": product.total_ratings,
                "duration":str(product.duration) + " hr",
                "categorySlug":product.categoryId.slug,
                "subcategorySlug":product.subCategoryId.slug,
                "start_time":format_time(product.startTime),
                "end_time":format_time(product.endTime)
              
             
            }

            return Response({
                "message": "experiences product details fetched successfully",
                "statusCode": 200,
                "status": True,
                "data": product_data
            }, status=status.HTTP_200_OK)

        except Product.DoesNotExist:
            return Response({
                "message": "Product not found",
                "statusCode": 400,
                "status": False,
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "message": str(e),
                "statusCode": 500,
                "status": False,
                "data": None
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        






class TicketAvailabilityAPIView(APIView):
    def get(self, request):
        ticket_id = request.query_params.get('ticket_id')
        booking_date = request.query_params.get('booking_date')

        if not ticket_id or not booking_date:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'ticket_id and booking_date are required.'
            }, status=status.HTTP_200_OK)

        try:
            ticket = TicketsConcert.objects.get(id=ticket_id)
        except TicketsConcert.DoesNotExist:
            return Response({
                'statusCode': 404,
                'status': False,
                'message': 'Ticket not found.'
            }, status=status.HTTP_404_NOT_FOUND)

        booked_quantity = BookingTicketItem.objects.filter(
            ticket=ticket,
            booking__booking_date=booking_date,
            booking__is_paid=True,
            booking__status='confirmed'
        ).aggregate(total=Sum('quantity'))['total'] or 0

        available_quantity = ticket.quantity - booked_quantity

        return Response({
            'statusCode': 200,
            'status': True,
            "message":"data fetched successfully ",
            'ticket_id': ticket.id,
            'ticket_name': ticket.name,
            'booking_date': booking_date,
            'available_quantity': max(0, available_quantity)
        }, status=status.HTTP_200_OK)
    





class AvailableSlotsAPIView(APIView):

    def get(self, request):
        product_id = request.query_params.get('product_id')
        date_str = request.query_params.get('date')  

        if not product_id or not date_str:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'product_id and date are required.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Invalid date format. Use YYYY-MM-DD.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
        except:
            return Response({
                'statusCode': 404,
                'status': False,
                'message': 'Product not found.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        start_time = product.startTime
        end_time = product.endTime
        duration = product.duration or 1

        if not start_time or not end_time:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Product startTime or endTime not set.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        slots = self.generate_time_slots(start_time, end_time, duration)

        booked_slots_qs = slotBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            status__in=['pending', 'confirmed']
        ).values_list('slot', flat=True)

        booked_slots = set(bs.strftime("%H:%M") for bs in booked_slots_qs if bs)

        available_slots = [slot for slot in slots if slot['time_24'] not in booked_slots]
        formatted_slots = [slot['time_ampm'] for slot in available_slots]

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Available slots fetched successfully.',
            'product_id': product_id,
            'date': date_str,
            'available_slots': formatted_slots
        }, status=status.HTTP_200_OK)

    def generate_time_slots(self, start_time, end_time, duration_hours):
        slots = []
        current = datetime.combine(datetime.today(), start_time)
        end = datetime.combine(datetime.today(), end_time)
        delta = timedelta(hours=duration_hours)

        while current + delta <= end:
            slots.append({
                'time_24': current.strftime("%H:%M"),
                'time_ampm': current.strftime("%I:%M %p")
            })
            current += delta

        return slots
    



class AvailableAestheticsSlotAPIView(APIView):

    def get(self, request):
        product_id = request.query_params.get('product_id')
        date_str = request.query_params.get('date')  # Format: YYYY-MM-DD

        if not product_id or not date_str:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'product_id and date are required.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Invalid date format. Use YYYY-MM-DD.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        product = get_object_or_404(Product, id=product_id)

        start_time = product.startTime
        end_time = product.endTime
        duration = product.duration or 1
        number_of_employees = product.totalEmployees or 1

        if not start_time or not end_time:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Product startTime or endTime not set.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        slots = self.generate_time_slots(start_time, end_time, duration)
        bookings_per_slot = aestheticsBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            status__in=['pending', 'confirmed']
        ).values('slot').annotate(count=Count('id'))

        slot_count_map = {
            b['slot'].strftime('%H:%M'): b['count'] for b in bookings_per_slot if b['slot']
        }

        available_slots = [
            {
                'slot': slot['time_ampm'],
                'remaining_slots': number_of_employees - slot_count_map.get(slot['time_24'], 0)
            }
            for slot in slots
            if slot_count_map.get(slot['time_24'], 0) < number_of_employees
        ]

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Available slots fetched successfully.',
            'product_id': product_id,
            'date': date_str,
            'available_slots': available_slots
        }, status=status.HTTP_200_OK)

    def generate_time_slots(self, start_time, end_time, duration_hours):
        slots = []
        current = datetime.combine(datetime.today(), start_time)
        end = datetime.combine(datetime.today(), end_time)
        delta = timedelta(hours=duration_hours)

        while current + delta <= end:
            slots.append({
                'time_24': current.strftime("%H:%M"),
                'time_ampm': current.strftime("%I:%M %p")
            })
            current += delta

        return slots

    
class AvailableRelaxaionSlotsAPIView(APIView):

    def get(self, request):
        product_id = request.query_params.get('product_id')
        date_str = request.query_params.get('date')  

        if not product_id or not date_str:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'product_id and date are required.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Invalid date format. Use YYYY-MM-DD.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        product = get_object_or_404(Product, id=product_id)

        start_time = product.startTime
        end_time = product.endTime
        duration = product.duration or 1
        number_of_employees = product.totalEmployees or 1

        if not start_time or not end_time:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Product startTime or endTime not set.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        slots = self.generate_time_slots(start_time, end_time, duration)
        bookings_per_slot = relaxationBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            status__in=['pending', 'confirmed']
        ).values('slot').annotate(total_members=Sum('number_of_people'))

        slot_member_map = {
            b['slot'].strftime('%H:%M'): b['total_members'] or 0 for b in bookings_per_slot if b['slot']
        }

        available_slots = []
        for slot in slots:
            time_24 = slot['time_24']
            booked_members = slot_member_map.get(time_24, 0)

            if booked_members < number_of_employees:
                remaining = number_of_employees - booked_members
                available_slots.append({
                    'slot': slot['time_ampm'],
                    'remaining_slots': remaining
                })

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Available slots fetched successfully.',
            'product_id': product_id,
            'date': date_str,
            'available_slots': available_slots
        }, status=status.HTTP_200_OK)

    def generate_time_slots(self, start_time, end_time, duration_hours):
        slots = []
        current = datetime.combine(datetime.today(), start_time)
        end = datetime.combine(datetime.today(), end_time)
        delta = timedelta(hours=duration_hours)

        while current + delta <= end:
            slots.append({
                'time_24': current.strftime("%H:%M"),
                'time_ampm': current.strftime("%I:%M %p")
            })
            current += delta

        return slots    


class AvailableArtandcultureSlotsAPIView(APIView):

    def get(self, request):
        product_id = request.query_params.get('product_id')
        date_str = request.query_params.get('date')  

        if not product_id or not date_str:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'product_id and date are required.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            booking_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Invalid date format. Use YYYY-MM-DD.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        try:
            product = get_object_or_404(Product, id=product_id)
        except:
            return Response({
                'statusCode': 404,
                'status': False,
                'message': 'Product not found.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        start_time = product.startTime
        end_time = product.endTime
        duration = product.duration or 1

        if not start_time or not end_time:
            return Response({
                'statusCode': 400,
                'status': False,
                'message': 'Product startTime or endTime not set.',
                'available_slots': []
            }, status=status.HTTP_200_OK)

        slots = self.generate_time_slots(start_time, end_time, duration)

        booked_slots_qs = artandcultureBooking.objects.filter(
            Product=product,
            booking_date=booking_date,
            status__in=['pending', 'confirmed']
        ).values_list('slot', flat=True)

        booked_slots = set(bs.strftime("%H:%M") for bs in booked_slots_qs if bs)

        available_slots = [slot for slot in slots if slot['time_24'] not in booked_slots]
        formatted_slots = [slot['time_ampm'] for slot in available_slots]

        return Response({
            'statusCode': 200,
            'status': True,
            'message': 'Available slots fetched successfully.',
            'product_id': product_id,
            'date': date_str,
            'available_slots': formatted_slots
        }, status=status.HTTP_200_OK)

    def generate_time_slots(self, start_time, end_time, duration_hours):
        slots = []
        current = datetime.combine(datetime.today(), start_time)
        end = datetime.combine(datetime.today(), end_time)
        delta = timedelta(hours=duration_hours)

        while current + delta <= end:
            slots.append({
                'time_24': current.strftime("%H:%M"),
                'time_ampm': current.strftime("%I:%M %p")
            })
            current += delta

        return slots
    
