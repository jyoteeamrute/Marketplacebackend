import calendar
import json
from collections import defaultdict
from datetime import datetime, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from geopy.distance import geodesic
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ProfessionalUser.models import *
from ProfessionalUser.serializers import *
from ProfessionalUser.utils import *
from UserApp.models import *
from UserApp.serializers import *
from UserApp.utils import *


def safe_url(field, bucket_folder="uploads"):
    if field:
        path = str(field)
        if path.startswith("http"):
            return path
        filename = path.split("/")[-1]
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{bucket_folder}/{filename}"
    return ""



DAY_MAPPING = {
    "monday": "Mon",
    "tuesday": "Tue",
    "wednesday": "Wed",
    "thursday": "Thu",
    "friday": "Fri",
    "saturday": "Sat",
    "sunday": "Sun"
}

def transform_opening_hours(opening_hours_dict):
    formatted_hours = []
    for day_key in sorted(opening_hours_dict.keys(), key=lambda d: list(DAY_MAPPING.keys()).index(d)):
        day_label = DAY_MAPPING.get(day_key.lower(), day_key.capitalize())
        times = opening_hours_dict[day_key]
        start, end = times.get("start_time"), times.get("end_time")
        if start and end:
            formatted_hours.append({"day": day_label, "hours": f"{start} - {end}"})
    return formatted_hours

def calculate_distance(user_coords, company_coords):
    try:
        return geodesic(user_coords, company_coords).km
    except Exception:
        return None

def get_company_coords(company):
    if company and hasattr(company, 'manual_address') and company.manual_address:
        try:
            return float(company.manual_address.lat), float(company.manual_address.lang)
        except (ValueError, AttributeError, TypeError):
            return None
    return None

def is_within_distance(user_coords, company_coords, max_distance):
    if not user_coords or not company_coords:
        return True
    distance = calculate_distance(user_coords, company_coords)
    return distance is not None and (not max_distance or distance <= float(max_distance))

def get_company_status(company):
    now = timezone.localtime()
    current_day = now.strftime("%A").lower()
    current_time = now.time()


    hours = getattr(company, 'opening_hours', None)
    if not hours:
        return "closed"
    if isinstance(hours, str):
        try:
            hours = json.loads(hours)
        except json.JSONDecodeError:
            return "closed"

    if not isinstance(hours, dict):
        return "closed"

    day_hours = hours.get(current_day)
    if not day_hours:
        return "closed"

    start_str = day_hours.get("start_time")
    end_str = day_hours.get("end_time")

    if not start_str or not end_str:
        return "closed"

    try:
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
    except ValueError:
        return "closed"

    today = now.date()
    start_dt = datetime.combine(today, start_time)
    end_dt = datetime.combine(today, end_time)
    current_dt = datetime.combine(today, current_time)

    one_hour = timedelta(hours=1)

    if start_dt <= current_dt < end_dt:
        if end_dt - current_dt <= one_hour:
            return "closing soon"
        return "open"
    elif start_dt - current_dt <= one_hour and current_dt < start_dt:
        return "opening soon"
    elif current_dt >= end_dt:
        return "closed"
    
    return "closed"


def safe_search_tab_company_url(field, bucket_folder="company_images"):
    if field:
        path = str(field)
        if path.startswith("http"):
            return path
        filename = path.split("/")[-1]
       
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{bucket_folder}/{filename}"
    return ""
def safe_search_tab_videos_url(field, bucket_folder="videos"):
    if field:
        path = str(field)
        if path.startswith("http"):
            return path
        filename = path.split("/")[-1]
        reelpath="reels"
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{reelpath}/{bucket_folder}/{filename}"
    return ""
def safe_search_tab_thumbnails_url(field, bucket_folder="thumbnails"):
    if field:
        path = str(field)
        if path.startswith("http"):
            return path
        filename = path.split("/")[-1]
        reelpath="reels"
        return f"https://markerplacemobileapp.s3.us-east-1.amazonaws.com/{reelpath}/{bucket_folder}/{filename}"
    return ""    



class SearchView(APIView):
    permission_classes = [AllowAny]
    def group_by_subcategory(self, products):
        grouped = defaultdict(lambda: {"subcategory_name": "", "subcategory_Id": None, "items": []})
        for p in products:
            sub_id = p["subcategory_id"]
            grouped[sub_id]["subcategory_name"] = p["subcategory_name"]
            grouped[sub_id]["subcategory_Id"] = sub_id
            grouped[sub_id]["items"].append(p)
        return list(grouped.values())
    def post(self, request):
        data = request.data
        category = data.get("category")
        subcategories = data.get("subcategories", [])
        content_type = data.get("content_type")
        search_name = data.get("search_name", "").strip()
        max_price = data.get("max_price")
        latitude, longitude = data.get("latitude"), data.get("longitude")
        max_distance = data.get("max_distance")
        checkbox_filters = [f.lower().strip() for f in data.get("checkbox_filters", []) if f.strip()]
        onsite_filter = data.get("onsite", None)
        clickcollect_filter = data.get("clickcollect", None)
        Delivery_filter = data.get("delivery", None)
        min_rating = request.data.get("min_rating",None)

        user = request.user if request.user.is_authenticated else None
    
        user_coords = (float(latitude), float(longitude)) if latitude and longitude else None
        results = {}
        if content_type == "product" and not request.user.is_authenticated:
            return Response({  "statusCode":400,
                             "status":False,
                "message": "Authentication required for product search."}, status=200)

        user = request.user
        user_coords = (float(latitude), float(longitude)) if latitude and longitude else None
        results = {}

        if content_type == "product":
            products = Product.objects.all()

            if category:
                products = products.filter(categoryId=category)
               

            if subcategories:
                products = products.filter(subCategoryId__in=subcategories)
                

            if search_name:
                search_words = search_name.lower().split()
                query_filter = Q()
                for word in search_words:
                    query_filter |= (
                        Q(productname__icontains=word) |
                        Q(description__icontains=word) |
                        Q(keywords__icontains=word)
                    )
                filtered_products_qs = products.filter(query_filter).distinct()
                if not filtered_products_qs.exists():
                    filtered_products_qs = products
                products = filtered_products_qs
            user_cart = {}
            if user:
                user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=request.user)if  c.product is not None } if user else {}
                

            filtered_products = []
            for product in products:
                promo = product.promotionalPrice
                base_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
                final_price = promo if promo is not None else base_price

                if max_price:
                    try:
                        if final_price > float(max_price):
                            continue
                    except (ValueError, TypeError):
                        pass

                company = product.company
                if onsite_filter and not product.onsite:
                    continue
                if clickcollect_filter and not product.clickandCollect:
                    continue
                if Delivery_filter and not product.onDelivery:
                    continue

                rating = company.average_rating or 0
                if min_rating:
                    try:
                        if float(rating) < float(min_rating):
                            continue
                    except (ValueError, TypeError):
                        pass

                company_coords = get_company_coords(company)
                if not is_within_distance(user_coords, company_coords, max_distance):
                    continue

                if checkbox_filters:
                    company_facilities = [f.name.lower().strip() for f in company.facilities.all()]
                    if not all(f in company_facilities for f in checkbox_filters):
                        continue

                discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0
                distance_km = round(calculate_distance(user_coords, company_coords), 2) if user_coords and company_coords else None
               
                filtered_products.append({
                    "item_id": product.id,
                    "item_name": product.productname,
                    "description": product.description,
                    "price": final_price,
                    "discount_percentage": discount,
                    "quantity": product.quantity,
                    "current_quantity": user_cart.get(product.id, 0), 
                    "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "company": {
                        **CompanyDetailsSerializer(company).data,
                        "opening_hours": transform_opening_hours(company.opening_hours or {}),
                        "opening_status": get_company_status(company),
                        "distance_km": distance_km
                    },
                    "subcategory_name": product.subCategoryId.name if product.subCategoryId else None,
                    "subcategory_id": product.subCategoryId.id if product.subCategoryId else None,
                })

            productstatus = []

            grouped_categories = {
                1: {"label_map": {
                        "Onsite": lambda p: p.onsite,
                        "Click and Collect": lambda p: p.clickandCollect,
                        "Delivery": lambda p: p.onDelivery
                    }},
                2: {"categories": [3, 4], "label_map": {
                                "Onsite": lambda p: p.onsite,
                        "Home Visit": lambda p: p.onhome
                    }},
                3: {"categories": [8], "label_map": {
                        "Click and Collect": lambda p: p.clickandCollect,
                        "Delivery": lambda p: p.onDelivery
                    }},
                4: {"categories": [2, 5, 6, 7]} 
            }

            category_int = int(category) if category else None
            category_type = None
            for k, v in grouped_categories.items():
                if k == category_int or (isinstance(v.get("categories"), list) and category_int in v["categories"]):
                    category_type = k
                    break

            if category_type == 4 or not subcategories:
                if filtered_products:
                    productstatus.append({
                        "label": "Results",
                        "products": self.group_by_subcategory(filtered_products)
                    })
            else:
                label_map = grouped_categories[category_type].get("label_map", {})
                label_data_map = {label: [] for label in label_map}

                product_obj_map = {p.id: p for p in Product.objects.filter(id__in=[fp["item_id"] for fp in filtered_products])}

                unmatched_products = []

                for p in filtered_products:
                    prod_obj = product_obj_map.get(p["item_id"])
                    matched = False
                    for label, condition in label_map.items():
                        try:
                            result = condition(prod_obj)
                        except Exception as e:
                            
                            result = False
                        
                        if result:
                            label_data_map[label].append(p)
                            matched = True
                    if not matched:
                        unmatched_products.append(p)
                if not any(label_data_map.values()) and unmatched_products:
                    productstatus.append({
                        "label": "Results",
                        "products": self.group_by_subcategory(unmatched_products)
                    })
                else:
                    for label, items in label_data_map.items():
                        if items:
                            productstatus.append({
                                "label": label,
                                "products": self.group_by_subcategory(items)
                            })
            results["mapid"] = category_type
            results["productStatus"] = productstatus

        elif content_type == "service":
                try:
                    user_lat = float(latitude or 0)
                    user_lon = float(longitude or 0)
                except ValueError:
                    user_lat, user_lon = 0.0, 0.0

                if category:
                    companies = CompanyDetails.objects.filter(categories=category)
                else:
                    companies = CompanyDetails.objects.all()
                if search_name:
                    company_reels = company_reels.filter(title__icontains=search_name)

                if checkbox_filters:
                    for checkbox in checkbox_filters:
                        companies = companies.filter(facilities__name__icontains=checkbox).distinct()
                        
                if onsite_filter is True:
                    companies = companies.filter(onsite=True)

                if clickcollect_filter is True:
                    companies = companies.filter(clickcollect=True)
                
                company_data = []
                for company in companies:
                    rating = company.average_rating or 0
                    if min_rating:
                        try:
                            if float(rating) < float(min_rating):
                                continue
                        except (ValueError, TypeError):
                            pass
                    coords = get_company_coords(company)
                    if not is_within_distance((user_lat, user_lon), coords, max_distance):
                        continue

                    distance_km = calculate_distance((user_lat, user_lon), coords) if coords else None
                    serialized = CompanyDetailsSerializer(company).data
                    serialized["opening_hours"] = transform_opening_hours(company.opening_hours or {})
                    serialized["opening_status"] = get_company_status(company)
                    serialized["distance_km"] = distance_km
                    company_data.append(serialized)

                results["companies"] = company_data
        

        elif content_type == "reel":
            company_reels = StoreReel.objects.all()
            if category:
                company_reels = company_reels.filter(category_id=category)
            if subcategories:
                company_reels = company_reels.filter(subcategory_id__in=subcategories)

            if search_name:
                company_reels = company_reels.filter(title__icontains=search_name)

            
            if checkbox_filters:
                for checkbox in checkbox_filters:
                    company_reels = company_reels.filter(company_id__facilities__name__icontains=checkbox).distinct()

            response_data = []
            for reel in company_reels:
                company = reel.company_id
                if not company:
                    continue
                if onsite_filter is True and not company.onsite:
                    continue
                if clickcollect_filter is True and not company.clickcollect:
                    continue
                rating = company.average_rating or 0
                if min_rating:
                    try:
                        if float(rating) < float(min_rating):
                            continue
                    except (ValueError, TypeError):
                        pass
                company_coords = get_company_coords(company)
                if not is_within_distance(user_coords, company_coords, max_distance):
                    continue

                distance_km = round(calculate_distance(user_coords, company_coords), 2) if user_coords and company_coords else None

                response_data.append({
                    "company_data": {
                        **CompanyDetailsSerializer(company).data,
                        "distance_km": distance_km,
                        "opening_hours": transform_opening_hours(company.opening_hours or {}),
                        "opening_status": get_company_status(company),
                        "store_reels": {
                            "id": reel.id,
                            "title": reel.title,
                            "companyName": company.companyName,
                            "profilePhoto": safe_search_tab_company_url(company.profilePhoto),
                            "category": reel.category.name if reel.category else None,
                            "categoryId": reel.category.id if reel.category else None,
                            "video": safe_search_tab_videos_url(reel.video),
                            "thumbnail": safe_search_tab_thumbnails_url(reel.thumbnail),
                            "likes": reel.likes,
                            "shares": reel.shares,
                            "comments": reel.comments,
                            "views": reel.views
                        }
                    }
                })

            results["reels"] = response_data

        elif content_type == "image":
            try:
                user_lat = float(latitude or 0)
                user_lon = float(longitude or 0)
            except ValueError:
                user_lat, user_lon = 0.0, 0.0

            companies = CompanyDetails.objects.all()

            if category:
                companies = companies.filter(categories=category)

            if subcategories:
                companies = companies.filter(subcategories__id__in=subcategories).distinct()

            if search_name:
                companies = companies.filter(companyName__icontains=search_name)
                
            if checkbox_filters:
                for checkbox in checkbox_filters:
                    companies = companies.filter(facilities__name__icontains=checkbox).distinct()
            if onsite_filter is True:
                companies = companies.filter(onsite=True)

            if clickcollect_filter is True:
                companies = companies.filter(clickcollect=True)
            
            company_data = []
            for company in companies:
                rating = company.average_rating or 0
                if min_rating:
                    try:
                        if float(rating) < float(min_rating):
                            continue
                    except (ValueError, TypeError):
                        pass
                coords = get_company_coords(company)
                if not is_within_distance((user_lat, user_lon), coords, max_distance):
                    continue

                distance_km = calculate_distance((user_lat, user_lon), coords) if coords else None
                serialized = CompanyDetailsSerializer(company).data
                serialized["opening_hours"] = transform_opening_hours(company.opening_hours or {})
                serialized["opening_status"] = get_company_status(company)
                serialized["distance_km"] = distance_km
                company_data.append(serialized)

            results["companies"] = company_data
        
        elif content_type == "photos":
            filters = {}

            if category:
                filters['category_id'] = category  

            if subcategories:
                if isinstance(subcategories, list):
                    filters['subcategory_id__in'] = subcategories  
                else:
                    filters['subcategory_id'] = subcategories

            images = StoreImage.objects.filter(**filters).select_related('category', 'subcategory', 'company_id')
          

            grouped_data = defaultdict(list)

            for image in images:
                if not image.subcategory:
                    continue

                subcategory_id = image.subcategory.id
                subcategory_name = image.subcategory.name

                grouped_data[(subcategory_id, subcategory_name)].append({
                    "item_id": image.id,
                    "item_name": image.title,
                    "image_url": image.image.url if image.image else "",
                    "company": CompanyDetailsSerializer(image.company_id).data if image.company_id else None,
                    "subcategory_name": subcategory_name,
                    "subcategory_id": subcategory_id
                })

            final_response = []

            for (subcat_id, subcat_name), items in grouped_data.items():
                final_response.append({
                    "subcategory_id": subcat_id,
                    "subcategory_name": subcat_name,
                    "items": items
                })


            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Filtered content fetched successfully.",
                "data": final_response
            }, status=status.HTTP_200_OK)
        
        elif content_type == "products":
            products = Product.objects.all()

            if category:
                products = products.filter(categoryId=category)
               

            if subcategories:
                products = products.filter(subCategoryId__in=subcategories)
                

            if search_name:
                search_words = search_name.lower().split()
                query_filter = Q()
                for word in search_words:
                    query_filter |= (
                        Q(productname__icontains=word) |
                        Q(description__icontains=word) |
                        Q(keywords__icontains=word)
                    )
                filtered_products_qs = products.filter(query_filter).distinct()
                if not filtered_products_qs.exists():
                    filtered_products_qs = products
                products = filtered_products_qs
            user_cart = {}
            if user:
                user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=request.user)if  c.product is not None } if user else {}
                

            filtered_products = []
            for product in products:
                promo = product.promotionalPrice
                base_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
                final_price = promo if promo is not None else base_price

                if max_price:
                    try:
                        if final_price > float(max_price):
                            continue
                    except (ValueError, TypeError):
                        pass

                company = product.company
                if onsite_filter and not product.onsite:
                    continue
                if clickcollect_filter and not product.clickandCollect:
                    continue
                if Delivery_filter and not product.onDelivery:
                    continue

                rating = company.average_rating or 0
                if min_rating:
                    try:
                        if float(rating) < float(min_rating):
                            continue
                    except (ValueError, TypeError):
                        pass

                company_coords = get_company_coords(company)
                if not is_within_distance(user_coords, company_coords, max_distance):
                    continue

                if checkbox_filters:
                    company_facilities = [f.name.lower().strip() for f in company.facilities.all()]
                    if not all(f in company_facilities for f in checkbox_filters):
                        continue

                discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0
                distance_km = round(calculate_distance(user_coords, company_coords), 2) if user_coords and company_coords else None
               
                filtered_products.append({
                    "item_id": product.id,
                    "item_name": product.productname,
                    "description": product.description,
                    "price": final_price,
                    "discount_percentage": discount,
                    "quantity": product.quantity,
                    "current_quantity": user_cart.get(product.id, 0), 
                    "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "company": {
                        **CompanyDetailsSerializer(company).data,
                        "opening_hours": transform_opening_hours(company.opening_hours or {}),
                        "opening_status": get_company_status(company),
                        "distance_km": distance_km
                    },
                    "subcategory_name": product.subCategoryId.name if product.subCategoryId else None,
                    "subcategory_id": product.subCategoryId.id if product.subCategoryId else None,
                })

            productstatus = []

            grouped_categories = {
                1: {"label_map": {
                        "Onsite": lambda p: p.onsite,
                        "Click and Collect": lambda p: p.clickandCollect,
                        "Delivery": lambda p: p.onDelivery
                    }},
                2: {"categories": [3, 4], "label_map": {
                                "Onsite": lambda p: p.onsite,
                        "Home Visit": lambda p: p.onhome
                    }},
                3: {"categories": [8], "label_map": {
                        "Click and Collect": lambda p: p.clickandCollect,
                        "Delivery": lambda p: p.onDelivery
                    }},
                4: {"categories": [2, 5, 6, 7]} 
            }

            category_int = int(category) if category else None
            category_type = None
            for k, v in grouped_categories.items():
                if k == category_int or (isinstance(v.get("categories"), list) and category_int in v["categories"]):
                    category_type = k
                    break

            if category_type == 4 or not subcategories:
                if filtered_products:
                    default_label_map = {
                        "Onsite": lambda p: p.onsite,
                        "Click and Collect": lambda p: p.clickandCollect,
                        "Delivery": lambda p: p.onDelivery
                    }

                    label_data_map = {label: [] for label in default_label_map}
                    product_obj_map = {p.id: p for p in Product.objects.filter(id__in=[fp["item_id"] for fp in filtered_products])}

                    for p in filtered_products:
                        prod_obj = product_obj_map.get(p["item_id"])
                        matched = False
                        for label, condition in default_label_map.items():
                            try:
                                if condition(prod_obj):
                                    label_data_map[label].append(p)
                                    matched = True
                            except Exception:
                                continue
                        

                    for label, items in label_data_map.items():
                        if items:
                            productstatus.append({
                                "label": label,
                                "products": self.group_by_subcategory(items)
                            })

            else:
                label_map = grouped_categories[category_type].get("label_map", {})
                label_data_map = {label: [] for label in label_map}

                product_obj_map = {p.id: p for p in Product.objects.filter(id__in=[fp["item_id"] for fp in filtered_products])}

                unmatched_products = []

                for p in filtered_products:
                    prod_obj = product_obj_map.get(p["item_id"])
                    matched = False
                    for label, condition in label_map.items():
                        try:
                            result = condition(prod_obj)
                        except Exception as e:
                            
                            result = False
                        
                        if result:
                            label_data_map[label].append(p)
                            matched = True
                    if not matched:
                        unmatched_products.append(p)
                if not any(label_data_map.values()) and unmatched_products:
                    productstatus.append({
                        "label": "Results",
                        "products": self.group_by_subcategory(unmatched_products)
                    })
                else:
                    for label, items in label_data_map.items():
                        if items:
                            productstatus.append({
                                "label": label,
                                "products": self.group_by_subcategory(items)
                            })
            results["mapid"] = category_type
            results["productStatus"] = productstatus
        else:
            return Response({"status": False, "message": f"Invalid content type: {content_type}."}, status=status.HTTP_200_OK)

        return Response({"statusCode":200,"status": True, "message": "Filtered content fetched successfully.", "data": results}, status=status.HTTP_200_OK)



class LabelBasedProductSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data.get("key")
        category_id = request.data.get("category_id")
        subcategory_ids = request.data.get("subcategory_ids", [])
        search_name = request.data.get("search_name", "").strip()
        user_lat = request.data.get("latitude")
        user_lng = request.data.get("longitude")

        if key is None or category_id is None:
            return Response({"statusCode": 400,"status": False, "message": "key and category_id are required"}, status=200)

        key_field_map = {
            1: "onsite",
            2: "clickandCollect",
            3: "onDelivery",
            4: "result"
        }

        field_name = key_field_map.get(int(key))
        if not field_name:
            return Response({"statusCode": 400,"status": False, "message": f"Unsupported key: {key}"}, status=200)

        if field_name == "result" and int(category_id) in [2, 5, 6, 7]:
            products = Product.objects.filter(categoryId__in=[2, 5, 6, 7])
        else:
            products = Product.objects.filter(categoryId=category_id, **{field_name: True})
        
        if subcategory_ids:
                products = products.filter(subCategoryId__in=subcategory_ids)
        if search_name:
            search_words = search_name.lower().split()
            query_filter = Q()
            for word in search_words:
                query_filter |= (
                    Q(productname__icontains=word) |
                    Q(description__icontains=word) |
                    Q(keywords__icontains=word)
                )
            products = products.filter(query_filter).distinct()
        user_cart = {
            c.product.id: c.quantity
            for c in Cart.objects.filter(user=request.user)
        } if request.user.is_authenticated else {}
        grouped_data = {}
        for product in products:
            subcategory = product.subCategoryId
            subcat_id = subcategory.id if subcategory else None
            subcat_name = subcategory.name if subcategory else "Others"

            if subcat_id not in grouped_data:
                grouped_data[subcat_id] = {
                    "subcategory_name": subcat_name,
                    "subcategory_Id": subcat_id,
                    "items": []
                }

            promo = product.promotionalPrice
            base_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
            final_price = promo if promo is not None else base_price
            discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0

            company = product.company
            distance = None
            if company and user_lat and user_lng and company.manual_address.lat and company.manual_address.lang:
                distance = haversine_distance(
                    user_lat,
                    user_lng,
                    company.manual_address.lat,
                    company.manual_address.lang
                )

            grouped_data[subcat_id]["items"].append({
                "item_id": product.id,
                "item_name": product.productname,
                "description": product.description,
                "price": final_price,
                "discount_percentage": discount,
                "quantity": product.quantity,
                "current_quantity": user_cart.get(product.id, 0),
                "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                "subcategory_name": subcat_name,
                "subcategory_id": subcat_id,
                "category_slug":product.categoryId.slug,
                "subcategory_slug":product.subCategoryId.slug,
                "company": {
                    **CompanyDetailsSerializer(company).data,
                    "opening_hours": transform_opening_hours(company.opening_hours or {}),
                    "opening_status": get_company_status(company),
                    "distance_km": distance
                }
            })

        return Response({
            "statusCode": 200,
            "status": True,
            "data": {
                "products": list(grouped_data.values())
            }
        })




class SubCategoryProductListView(generics.ListAPIView):
    permission_classes=[IsAuthenticated]

    serializer_class = ProductSerializer

    def get_queryset(self):
        subcategory_id = self.kwargs.get('id')
        return Product.objects.filter(subCategoryId=subcategory_id)

    def list(self, request, *args, **kwargs):
        subcategory_id = self.kwargs.get('id')

        try:
            subcategory = Subcategory.objects.get(id=subcategory_id)
        except Subcategory.DoesNotExist:
            return Response({
                "status": False,
                "message": "Subcategory not found.",
                "data": {
                    "products": []
                }
            }, status=status.HTTP_200_OK)

        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)

        user_lat = request.query_params.get('latitude')
        user_lon = request.query_params.get('longitude')
        try:
            user_lat = float(user_lat)
            user_lon = float(user_lon)
        except (TypeError, ValueError):
            user_lat = user_lon = None  
        
        user_cart = {}
        if request.user.is_authenticated:
                    user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=request.user)if  c.product is not None }
        items_data = []
        for idx, product in enumerate(queryset):
            product_data = serializer.data[idx]
            company = product.company
            company_data = None
            distance = None

            if (
                company and
                company.manual_address and
                user_lat is not None and
                user_lon is not None and
                company.manual_address.lat is not None and
                company.manual_address.lang is not None
            ):
                distance = haversine_distance(
                    user_lat,
                    user_lon,
                    float(company.manual_address.lat),
                    float(company.manual_address.lang)
                )

            if company:
                try:
                    company_data = CompanyDetailsSerializer(company).data
                    if distance is not None:
                        company_data["distance"] = distance  # add distance here
                except:
                    company_data = None
            base_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
            final_price = product.promotionalPrice if product.promotionalPrice is not None else base_price

            if product.promotionalPrice is not None and base_price:
                discount = int(((base_price - product.promotionalPrice) / base_price) * 100)
            else:
                discount = 0
            image_url = product_data.get("ProductImage")
            if isinstance(image_url, list):
                image_url = image_url[0]  

            items_data.append({
                "item_id": product.id,
                "item_name": product.productname,
                "description": product.description,
                "price": str(product.promotionalPrice or product.priceOnsite or "0.00"),
                "discount_percentage": discount or 0,
                "quantity": product.quantity,
                "current_quantity": user_cart.get(product.id, 0),
                "image_url": image_url,
                "subcategory_name": subcategory.name,
                "subcategory_id": subcategory.id,
                "category_slug":product.categoryId.slug,
                "subcategory_slug":product.subCategoryId.slug,
                "company": company_data,
                
            })

        response_data = {
            "statusCode": 200,
            "status": True,
            "message": "Data fetched successfully.",
            "data": {
                "products": [
                    {
                        "subcategory_name": subcategory.name,
                        "subcategory_Id": subcategory.id,
                        "items": items_data
                    }
                ]
            }
        }

        return Response(response_data, status=status.HTTP_200_OK)
    

class RestaurantDetailsView(APIView):
    def post(self, request):
        try:
            lat = request.data.get("lat")
            lang = request.data.get("lang")
            category = request.data.get("category", "All").lower()
           


            if not lat or not lang:
                return Response(
                    { "statusCode":400 , "status": False, "message": "Latitude and longitude are required."},
                    status=status.HTTP_200_OK
                )

            lat = float(lat)
            long = float(lang)

            companies = CompanyDetails.objects.filter(isActive=True)

            all_category_data = []
            category_wise_data = defaultdict(list) 
            for company in companies:
                address = company.manual_address or company.automatic_address
                if address and address.lat and address.lang:
                    distance = haversine_distance(lat, long, float(address.lat), float(address.lang))

                    if distance <= 20: 
                        categories = company.categories.all()
                        category_list = [
                            {"id": cat.id, "name": cat.name, "slug": cat.slug, "icon": cat.icon} for cat in categories
                        ]

                        serialized_data = CompanyDetailsSerializer(company).data

                        reels = StoreReel.objects.filter(company_id=company.id, isActive=True)
                        serialized_reels = StoreReelSerializer(reels, many=True).data

                        location_image = (
                            f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{category_list[0]['icon']}"
                            if category_list else "https://markerplacemobileapp.s3.us-east-1.amazonaws.com/uploads/Experience.png"
                        )

                        open_status = "Closed"
                        if serialized_data.get("end_time"):
                            try:
                                end_time = datetime.strptime(serialized_data["end_time"], "%H:%M:%S").time()
                                if end_time > now().time():
                                    open_status = "Open"
                            except ValueError:
                                open_status = "Closed"

                        restaurant_data = {
                            "coordinate": {
                                "latitude": float(address.lat),
                                "longitude": float(address.lang),
                            },
                            "title": company.companyName,
                            "address": address.address1 if address.address1 else None,
                            "image": f"https://{settings.AWS_STORAGE_BUCKET_NAME}.s3.{settings.AWS_S3_REGION_NAME}.amazonaws.com/{company.profilePhoto}",
                            "categories": [
                                {"id": cat["id"], "name": cat["name"], "slug": cat["slug"]} for cat in category_list
                            ],
                            "location_image": location_image,
                            "distance_km": distance,
                            "companyDetails": {
                                "id": serialized_data["id"],
                                "companyName": serialized_data["companyName"],
                                "profilePhoto": serialized_data["profilePhoto"],
                                "average_ratings": serialized_data["average_rating"],
                                "total_ratings": serialized_data["total_ratings"],
                                "address": serialized_data["manual_address"].get("address1") if isinstance(serialized_data["manual_address"], dict) else None,
                                "postalCode": serialized_data["manual_address"].get("postalCode") if isinstance(serialized_data["manual_address"], dict) else None,
                                "city": serialized_data["manual_address"].get("city") if isinstance(serialized_data["manual_address"], dict) else None,
                                "opening_hours": format_opening_hours(serialized_data.get("opening_hours", {})),
                                "end_time": serialized_data["end_time"] if serialized_data["end_time"] else None,
                                "open_status": open_status
                            },
                            "reels": serialized_reels
                        }

                        all_category_data.append(restaurant_data)

                        for cat in category_list:
                            category_wise_data[cat["name"]].append(restaurant_data)

            response_data = [
                {
                    "category": "All",
                    "categoryID": "all",
                    "categoryData": all_category_data
                }
            ]

            for cat_name, data in category_wise_data.items():
                category_obj = Category.objects.filter(name=cat_name).first()  
                category_id = category_obj.id if category_obj else None  

                response_data.append({
                    "category": cat_name,
                    "categoryId": category_id, 
                    "categoryData": data
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Restaurants retrieved successfully.",
                "data": response_data
            }, status=status.HTTP_200_OK)

        except Exception as e:

            return Response({"status": False, "message": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class FilterByLabelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        data = request.data
        category_id = int(data.get("category_id", 0))
        key = data.get("key")
        keys = [int(k) for k in key] if isinstance(key, list) else [int(key)]
        max_price = data.get("max_price")
        latitude, longitude = data.get("latitude"), data.get("longitude")
        user_coords = (float(latitude), float(longitude)) if latitude and longitude else None
        max_distance = data.get("max_distance")
        checkbox_filters = [f.lower().strip() for f in data.get("checkbox_filters", []) if f.strip()]
        onsite_filter = data.get("onsite")
        clickcollect_filter = data.get("clickcollect")
        Delivery_filter = data.get("delivery")
        min_rating = data.get("min_rating")
        subcategory_ids = data.get("subcategory_ids", [])
        if isinstance(subcategory_ids, list):
            subcategory_ids = [int(i) for i in subcategory_ids if isinstance(i, (int, str)) and str(i).isdigit()]
        else:
            subcategory_ids = []
        label_map = {
            1: {
                1: lambda p: p.onsite,
                2: lambda p: p.clickandCollect,
                3: lambda p: p.onDelivery
            },
            3: {
                1: lambda p: p.onsite,
                3: lambda p: p.onhome
            },
            4: {
                1: lambda p: p.onsite,
                3: lambda p: p.onhome
            },
            8: {
                2: lambda p: p.clickandCollect,
                3: lambda p: p.onDelivery
            }
        }

        matched_products = []
        all_products = Product.objects.filter(categoryId__id=category_id)
        if subcategory_ids:
            all_products = all_products.filter(subCategoryId__id__in=subcategory_ids)


        for product in all_products:
            try:
                if category_id in [2, 5, 6, 7] and 4 in keys:
                    pass
                elif category_id in label_map:
                    if not any(k in label_map[category_id] and label_map[category_id][k](product) for k in keys):
                        continue
                else:
                    continue

                promo = product.promotionalPrice
                base_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
                final_price = promo if promo is not None else base_price

                if max_price:
                    try:
                        if final_price > float(max_price):
                            continue
                    except:
                        continue

                company = product.company

                if onsite_filter and not product.onsite:
                    continue
                if clickcollect_filter and not product.clickandCollect:
                    continue
                if Delivery_filter and not product.onDelivery:
                    continue

                rating = company.average_rating or 0
                if min_rating:
                    try:
                        if float(rating) < float(min_rating):
                            continue
                    except:
                        continue

                user_cart = {}
                if request.user.is_authenticated:
                    user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=request.user)if  c.product is not None }
                company_coords = get_company_coords(company)
                if not is_within_distance(user_coords, company_coords, max_distance):
                    continue

                if checkbox_filters:
                    company_facilities = [f.name.lower().strip() for f in company.facilities.all()]
                    if not all(f in company_facilities for f in checkbox_filters):
                        continue

                distance_km = round(calculate_distance(user_coords, company_coords), 2) if user_coords and company_coords else None
                discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0

                matched_products.append({
                    "item_id": product.id,
                    "item_name": product.productname,
                    "description": product.description,
                    "price": final_price,
                    "discount_percentage": discount,
                    "quantity": product.quantity,
                    "current_quantity": user_cart.get(product.id, 0),
                    "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "company": {
                        **CompanyDetailsSerializer(company).data,
                        "opening_hours": transform_opening_hours(company.opening_hours or {}),
                        "opening_status": get_company_status(company),
                        "distance_km": distance_km
                    },
                    "subcategory_name": product.subCategoryId.name if product.subCategoryId else None,
                    "subcategory_id": product.subCategoryId.id if product.subCategoryId else None,
                    "category_id":product.categoryId.id if product.categoryId else None,
                    "subcategory_slug": product.subCategoryId.slug if product.subCategoryId else None,
                    "category_slug":product.categoryId.slug if product.categoryId else None,
                })
            except Exception as e:
                continue

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Filtered data fetched successfully",    
            "products": self.group_by_subcategory(matched_products)
        })

    def group_by_subcategory(self, products):
        grouped = {}
        for p in products:
            sub_id = p["subcategory_id"] or 0
            if sub_id not in grouped:
                grouped[sub_id] = {
                    "subcategory_Id": sub_id,
                    "subcategory_name": p["subcategory_name"],
                    "items": []
                }
            grouped[sub_id]["items"].append(p)
        sorted_groups = sorted(grouped.values(), key=lambda x: x["subcategory_Id"])
        return list(sorted_groups)





class ProductDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, product_id):
        try:
            user = request.user if request.user.is_authenticated else None
            product = get_object_or_404(Product, id=product_id)
            product_data = ProductSerializer(product).data
            
            key = request.query_params.get('key')
            try:
                key = int(key)
            except (ValueError, TypeError):
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Invalid key. Key must be an integer between 1 and 4."
                }, status=status.HTTP_200_OK)

            key_map = {
                1: ('onsite', product.onsite, product.priceOnsite),
                2: ('clickcollect', product.clickandCollect, product.priceClickAndCollect),
                3: ('delivery', product.onDelivery, product.priceDelivery),
                4: ('result', not any([product.onsite, product.clickandCollect, product.onDelivery, product.onhome]), product.promotionalPrice or product.basePrice),
            }

            if key not in key_map:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": "Invalid key. Valid keys: 1 (onsite), 2 (click and collect), 3 (delivery), 4 (result)"
                }, status=status.HTTP_200_OK)

            label, is_available, base_price = key_map[key]

            if not is_available:
                return Response({
                    "statusCode": 400,
                    "status": False,
                    "message": f"The product is not available for the selected option (key: {key})."
                }, status=status.HTTP_200_OK)

            if user:
                in_cart = Cart.objects.filter(user=user, product=product).exists()
                product_data["is_in_cart"] = in_cart
            else:
                product_data["is_in_cart"] = False

            company = product.company
            company_data = CompanyDetailsSerializer(company).data if company else None

            user_lat = request.query_params.get("lat")
            user_lon = request.query_params.get("lon")
           
            company_lat = None
            company_lon = None
            if company:
                if company.manual_address:
                    company_lat = company.manual_address.lat
                    company_lon = company.manual_address.lang
                elif company.automatic_address:
                    company_lat = company.automatic_address.lat
                    company_lon = company.automatic_address.lang

            distance_km = None
            if user_lat and user_lon and company_lat and company_lon:
                distance_km = haversine_distance(user_lat, user_lon, company_lat, company_lon)

            promo = product.promotionalPrice
            fallback_price = product.priceOnsite or product.priceDelivery or product.priceClickAndCollect
            final_price = promo if promo is not None else base_price or fallback_price

            user_cart = {}
            if user:
                user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=request.user) if c.product is not None}

            discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Product details retrieved successfully",
                "data": {
                    "item_id": product.id,
                    "item_name": product.productname,
                    "description": product.description,
                    "price": final_price,
                    "discount_percentage": discount,
                    "order_type": label,
                    "key": key,
                    "quantity": product.quantity,
                    "current_quantity": user_cart.get(product.id, 0),
                    "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "company": {
                        **company_data,
                        "distance_km": distance_km
                    }
                }
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": "An error occurred",
                "error": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        



class OnsiteBookingOptionsAPIView(APIView):
    def get(self, request, company_id):
        try:
            company = CompanyDetails.objects.get(id=company_id)

            opening_hours = company.opening_hours or {}
            timezone = pytz.timezone("Asia/Kolkata")

            today = datetime.now(timezone).date()
            now = datetime.now(timezone)
            booking_days = []
            time_slots_by_day = []

            for i in range(5):  # Next 5 days
                current_day = today + timedelta(days=i)
                day_name = calendar.day_name[current_day.weekday()].lower()
                formatted_date = current_day.strftime("%a, %d %B")
                date_value = current_day.isoformat()
                booking_days.append({
                    "date": formatted_date,
                    "date_value": date_value
                })

                slots = []

                if day_name in opening_hours:
                    start_str = opening_hours[day_name].get("start_time")
                    end_str = opening_hours[day_name].get("end_time")

                    if start_str and end_str:
                        try:
                            start_time = datetime.strptime(start_str, "%H:%M:%S").time()
                        except ValueError:
                            start_time = datetime.strptime(start_str, "%H:%M").time()
                        try:
                            end_time = datetime.strptime(end_str, "%H:%M:%S").time()
                        except ValueError:
                            end_time = datetime.strptime(end_str, "%H:%M").time()
                        current_datetime = timezone.localize(datetime.combine(current_day, start_time))
                        end_datetime = timezone.localize(datetime.combine(current_day, end_time))

                        while current_datetime < end_datetime:
                            if current_day > today or current_datetime > now:
                                slots.append({
                                    "time": current_datetime.strftime("%I:%M %p")
                                })
                            current_datetime += timedelta(minutes=30)

                time_slots_by_day.append({
                    "date": formatted_date,
                    "slots": slots
                })

            return Response({
                "statusCode": 200,
                "status": True,
                "message": "Booking options fetched successfully",
                "data": {
                    "days": booking_days,
                    "timeSlots": time_slots_by_day,
                    "members": [1, 2, 3, 4, 5, 6, 7, 8]
                }
            }, status=status.HTTP_200_OK)

        except CompanyDetails.DoesNotExist:
            return Response({
                "statusCode": 404,
                "status": False,
                "message": "Company not found"
            }, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({
                "statusCode": 500,
                "status": False,
                "message": str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        





class ProductSearchView(APIView):
    permission_classes = [AllowAny]

    def get_labels_for_category(self, category_id):
        category_id = int(category_id)
        if category_id == 1:
            return [
                {"label": "Onsite", "key": 1},
                {"label": "Click and Collect", "key": 2},
                {"label": "Home", "key": 3}
            ]
        elif category_id in [3, 4]:
            return [
                {"label": "Onsite", "key": 1},
                {"label": "Home", "key": 3}
            ]
        elif category_id == 8:
            return [
                {"label": "Click and Collect", "key": 2},
                {"label": "Home", "key": 3}
            ]
        elif category_id in [2, 5, 6, 7]:
            return [
                {"label": "Results", "key": 4}
            ]
        elif category_id == 0:
            return [
                {"label": "Onsite", "key": 1},
                {"label": "Click and Collect", "key": 2},
                {"label": "Home", "key": 3}
            ]
        return []

    def post(self, request):
        category = request.data.get("category")
        if category is None:
            return Response({
                "statusCode": 400,
                "status": False,
                "message": "Category is required.",
                "Data": []
            })

        labels = self.get_labels_for_category(category)

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Data fetched successfully.",
            "Data": labels
        })



class ProductListByKeyAndCategoryView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        key = request.data.get("key")
        category_id = request.data.get("category")
        subcategory_ids = request.data.get("subcategory", [])
        latitude, longitude = request.data.get("latitude"), request.data.get("longitude")
        search_term = request.data.get("search", "").strip()

        if key is None or category_id is None:
            return Response({
                "statusCode": 400,
            "status": False, 
            "message": "Key and category are required."}, status=200)

        key = str(key)
        user = request.user
        user_coords = (float(latitude), float(longitude)) if latitude and longitude else None
        response_data = []

        if isinstance(subcategory_ids, int):
            subcategory_ids = [subcategory_ids]
        if str(category_id) == "0" and (not subcategory_ids or subcategory_ids == [0]):
            subcategories = Subcategory.objects.all()

        elif subcategory_ids:
            if not isinstance(subcategory_ids, list):
                return Response({ "statusCode": 400,
            "status": False, "message": "Subcategory must be a list of IDs."}, status=200)
            subcategories = Subcategory.objects.filter(id__in=subcategory_ids)

        elif str(category_id) == "0":
                if key == "1":
                    category_ids = [1, 2, 3, 4, 5, 6, 7, 8]
                elif key == "2":
                    category_ids = [1, 8]
                elif key == "3":
                    category_ids = [1, 3, 4, 8]
                elif key == "0":
                    category_ids = Subcategory.objects.values_list("parentCategoryId", flat=True).distinct()
                else:
                    return Response({"statusCode": 400,
            "status": False,  "message": "Invalid key provided."}, status=200)
                subcategories = Subcategory.objects.filter(parentCategoryId__in=category_ids)
        
        else:
            subcategories = Subcategory.objects.filter(parentCategoryId=category_id)


        for subcat in subcategories:
            product_filter = {"subCategoryId": subcat}
            if key == "1":
                product_filter["onsite"] = True
            elif key == "2":
                product_filter["clickandCollect"] = True
            elif key == "3":
                product_filter["onDelivery"] = True

            items = Product.objects.filter(**product_filter)
            if search_term:
                items = items.filter(productname__icontains=search_term)

            user_cart = {c.product.id: c.quantity for c in Cart.objects.filter(user=user) if  c.product is not None } if user else {}

            serialized_items = []
            for product in items:
                company = product.company
                company_coords = get_company_coords(company)
                promo = product.promotionalPrice
                base_price = promo or product.priceDelivery or product.priceClickAndCollect
                final_price = promo if promo is not None else base_price
                discount = int(((base_price - promo) / base_price) * 100) if promo and base_price else 0
                distance_km = round(calculate_distance(user_coords, company_coords), 2) if user_coords and company_coords else None

                serialized_items.append({
                    "item_id": product.id,
                    "item_name": product.productname,
                    "description": product.description,
                    "price": final_price,
                    "discount_percentage": discount,
                    "quantity": product.quantity,
                    "current_quantity": user_cart.get(product.id, 0),
                    "image_url": safe_url(product.ProductImage, "product_images") if product.ProductImage else default_image_url("product_images"),
                    "company": {
                        **CompanyDetailsSerializer(company).data,
                        "opening_hours": transform_opening_hours(company.opening_hours or {}),
                        "opening_status": get_company_status(company),
                        "distance_km": distance_km
                    },
                    "subcategory_name": product.subCategoryId.name if product.subCategoryId else None,
                    "subcategory_id": product.subCategoryId.id if product.subCategoryId else None,
                    "category_slug":product.categoryId.slug  if product.categoryId else None,
                    "subcategory_slug":product.subCategoryId.slug if product.subCategoryId else None,


                })

            if serialized_items:
                response_data.append({
                    "subcategory_name": subcat.name,
                    "subcategory_Id": subcat.id,
                    "items": serialized_items
                })

        return Response({
            "statusCode": 200,
            "status": True,
            "message": "Data fetched successfully.",
            "label": key.replace("_", " ").title(),
            "Data": response_data
        })
