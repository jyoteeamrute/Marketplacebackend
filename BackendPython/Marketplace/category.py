import os

import django
from django.conf import settings

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Marketplace.settings") 
django.setup()

from django.utils.text import slugify

from Admin.models import Category, Subcategory

categories_data = [
        {
            "name": "Food & Drink",
            "machine_name": "Food & Drink",
            "description": "test",
            "categoriesImage": "1 Food & Drink.jpg",
            "type": "Dining",  # Ensure type is included
            "distance": None,
            "onSite": False,
            "clickCollect": False,
            "halal": False,
            "handicapped": False,
            "rooftop": False,
            "freeCancellation": False,
            "is_active": True,
            "status": True,
            "order_by": 1,
            "subcategories": [
                {"name": "Fast Food", "description": "Default description", "order_by": 1, "machine_name": "Fast Food", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/01 Fast Food.jpeg", "type": "Quick Bites"},
                {"name": "Gourmet Restaurants", "description": "Default description", "order_by": 2, "machine_name": "Gourmet Restaurants", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/02 Gourmet Restaurants.jpeg", "type": "Fine Dining"},
                {"name": "Themed Dining", "description": "Default description", "order_by": 3, "machine_name": "Themed Dining", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/03 Themed Dining.jpeg", "type": "Casual"},
                {"name": "Hotel Dining", "description": "Default description", "order_by": 4, "machine_name": "Hotel Dining", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/04 Hotel Dining.jpeg", "type": "Luxury"},
                {"name": "Brunches", "description": "Default description", "order_by": 5, "machine_name": "Brunches", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/05 Brunches.jpeg", "type": "Breakfast"},
                {"name": "Bakeries & Pastries", "description": "Default description", "order_by": 6, "machine_name": "Bakeries & Pastries", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/06 Bakeries & Pastries.jpeg", "type": "Bakery"},
                {"name": "Themed Bars", "description": "Default description", "order_by": 7, "machine_name": "Themed Bars", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/07 Themed Bars.jpeg", "type": "Bars"},
                {"name": "Rooftop", "description": "Default description", "order_by": 8, "machine_name": "Rooftop", "subcategoriesImage": "staticfiles/subcategoryimg/01restauration/08 Rooftop.jpeg", "type": "Outdoor"},
            ]
        },
        
    {
        "name": "Travel",
        "machine_name": "Travel",
        "description": "test",
        "categoriesImage": "/2 Travel.jpg",
        "type": "Accommodation",
        "distance": None,
        "onSite": False,
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,
        "status": True,
        "order_by": 2,
        "subcategories": [
            {"name": "Hotels", "description": "Default description", "order_by": 1, "machine_name": "Hotels", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/01 Hotels.jpeg", "type": "Luxury Stay"},
            {"name": "Guest houses", "description": "Default description", "order_by": 2, "machine_name": "Guest houses", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/02 Guest houses.jpeg", "type": "Budget Stay"},
            {"name": "Camping", "description": "Default description", "order_by": 3, "machine_name": "Camping", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/03 Camping.jpeg", "type": "Outdoor Adventure"},
            {"name": "Inns & lodges", "description": "Default description", "order_by": 4, "machine_name": "Inns & lodges", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/04 Inns & lodges.jpeg", "type": "Cozy Stay"},
            {"name": "Chalets & Cabins", "description": "Default description", "order_by": 5, "machine_name": "Chalets & Cabins", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/05 Chalets & Cabins .jpeg", "type": "Mountain Retreat"},
            {"name": "Unusual accommodation", "description": "Default description", "order_by": 6, "machine_name": "Unusual accommodation", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/06 Unusual accommodation.jpeg", "type": "Unique Stay"},
            {"name": "Cruises & pleasure boats", "description": "Default description", "order_by": 7, "machine_name": "Cruises & pleasure boats", "subcategoriesImage": "staticfiles/subcategoryimg/02travel/07 Cruises & pleasure boats.jpeg", "type": "Luxury Cruise"}
        ]
    },
    {
        "name": "Aesthetics",
        "machine_name": "Aesthetics",
        "description": "test",
        "categoriesImage": "3 Esthetique.jpg",
        "type": "Beauty & Wellness",
        "distance": None,
        "onSite": False,
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,
        "status": True,
        "order_by": 3,
        "subcategories": [
            {"name": "Hairsalons", "description": "Default description", "order_by": 1, "machine_name": "Hairsalons", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/01Hairsalons.jpeg", "type": "Hair Care"},
            {"name": "Barbers", "description": "Default description", "order_by": 2, "machine_name": "Barbers", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/02 Barbers.jpeg", "type": "Men's Grooming"},
            {"name": "Tattoos & piercings", "description": "Default description", "order_by": 3, "machine_name": "Tattoos & piercings", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/03 Tattoos & piercings.jpeg", "type": "Body Art"},
            {"name": "Manicure & pedicure salons", "description": "Default description", "order_by": 4, "machine_name": "Manicure & pedicure salons", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/04 Manicure & pedicure salons.jpeg", "type": "Nail Care"},
            {"name": "Makeup", "description": "Default description", "order_by": 5, "machine_name": "Makeup", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/05 Makeup.jpeg", "type": "Cosmetics"},
            {"name": "Hair removal", "description": "Default description", "order_by": 6, "machine_name": "Hair removal", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/06 Hair removal.jpeg", "type": "Skin Care"},
            {"name": "Facial & body hair treatments", "description": "Default description", "order_by": 7, "machine_name": "Facial_body_hair_treatments", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/07_Facial_body_hair_treatments.jpeg", "type": "Aesthetic Treatments"},
            {"name": "Tanning Services", "description": "Default description", "order_by": 8, "machine_name": "Tanning Services", "subcategoriesImage": "staticfiles/subcategoryimg/03Aesthetic/08 Tanning Services .jpeg", "type": "Sunless Tanning"}
        ]
    },
    {
        "name": "Relaxation",
        "machine_name": "Relaxation",
        "description": "test",
        "categoriesImage": "4 Relexation.jpg",
        "type": "Wellness & Leisure",
        "distance": None,
        "onSite": False,
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,
        "status": True,
        "order_by": 4,
        "subcategories": [
            {"name": "Spa & swimming pool", "description": "Relaxation through massage", "order_by": 1, "machine_name": "Spa & swimming pool", "subcategoriesImage": "staticfiles/subcategoryimg/04relaxation/01Spa & swimming pool.jpeg", "type": "Hydrotherapy"},
            {"name": "Massage & well-being", "description": "Spa treatments and pool activities", "order_by": 2, "machine_name": "Massage & well-being", "subcategoriesImage": "staticfiles/subcategoryimg/04relaxation/02 Massage & well-being.jpeg", "type": "Therapeutic Treatments"},
            {"name": "Meditation & relaxation", "description": "Peaceful meditation sessions", "order_by": 3, "machine_name": "Meditation & relaxation", "subcategoriesImage": "staticfiles/subcategoryimg/04relaxation/03 Meditation & relaxation.jpeg", "type": "Mindfulness"},
            {"name": "Alternative therapies", "description": "Activities involving water", "order_by": 4, "machine_name": "Alternative therapies", "subcategoriesImage": "staticfiles/subcategoryimg/04relaxation/04 Alternative therapies.jpeg", "type": "Holistic Healing"}
        ]
    },
    
    {
        "name": "Art and Culture",
        "machine_name": "Art and Culture",
        "description": "test",
        "categoriesImage": "staticfiles/adminimag/5 Art & Culture.jpg",
        "type": "Entertainment & Heritage",
        "distance": None,
        "onSite": False,
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,
        "status": True,
        "order_by": 5,
        "subcategories": [
            {"name": "Museums & art galleries", "description": "Explore museums and galleries", "order_by": 1, "machine_name": "Museums & art galleries", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/01 Museums & art galleries.jpeg", "type": "Exhibitions"},
            {"name": "Theaters & operas", "description": "Watch films and documentaries", "order_by": 2, "machine_name": "Theaters & operas", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/02 Theaters & operas.jpeg", "type": "Performing Arts"},
            {"name": "Cinema & videos", "description": "Theater and live performances", "order_by": 3, "machine_name": "Cinema & videos", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/03 Cinema & videos.jpeg", "type": "Film & Media"},
            {"name": "Libraries", "description": "Learn about history and cultural heritage", "order_by": 4, "machine_name": "Libraries", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/04 Libraries.jpeg", "type": "Education & Literature"},
            {"name": "History & heritage", "description": "Explore historical sites and traditions", "order_by": 5, "machine_name": "History & heritage", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/05 History & heritage.jpeg", "type": "Historical Attractions"},
            {"name": "Cultural Festivals", "description": "Experience diverse cultural events", "order_by": 6, "machine_name": "Cultural Festivals", "subcategoriesImage": "staticfiles/subcategoryimg/05Art&Culture/06 Cultural Festivals.jpeg", "type": "Festivals & Events"}
        ]
    },
    {
        "name": "Music",
        "machine_name": "Music",
        "description": "test",
        "categoriesImage": "staticfiles/adminimag/6 Music.jpg",
        "type": "Entertainment",
        "distance": None,
        "onSite": False,
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,
        "status": True,
        "order_by": 6,
        "subcategories": [
            {"name": "Concerts", "description": "Live music performances", "order_by": 1, "machine_name": "Concerts", "subcategoriesImage": "staticfiles/subcategoryimg/06Music/01 Concerts.jpeg", "type": "Live Events"},
            {"name": "Music Festivals", "description": "Experience large-scale music events", "order_by": 2, "machine_name": "Music Festivals", "subcategoriesImage": "staticfiles/subcategoryimg/06Music/02 Music Festivals.jpeg", "type": "Festivals"},
            {"name": "Nightclubs", "description": "Dance and party at nightclubs", "order_by": 3, "machine_name": "Nightclubs", "subcategoriesImage": "staticfiles/subcategoryimg/06Music/03 Nightclubs.jpeg", "type": "Clubbing"}
        ]
    },
        
    {
        "name": "Experiences",
        "machine_name": "Experiences",
        "description": "test",
        "categoriesImage": "staticfiles/adminimag/7 Experiences.jpg",
        "type": "Activities",
        "distance": None,
        "onSite": False,  
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,  
        "status": True,
        "order_by": 7,
        "subcategories": [
            {"name": "Amusement parks", "description": "Exciting rides and attractions", "order_by": 1, "machine_name": "Amusement parks", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/01 Amusement parks.jpeg", "type": "Entertainment"},
            {"name": "Sport", "description": "Various physical activities and games", "order_by": 2, "machine_name": "Sport", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/02 Sport.jpeg", "type": "Recreation"},
            {"name": "Events", "description": "Sporting events and social gatherings", "order_by": 3, "machine_name": "Events", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/03 Events.jpeg", "type": "Entertainment"},
            {"name": "Workshops", "description": "Creative and educational workshops", "order_by": 4, "machine_name": "Workshops", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/04 Workshops.jpeg", "type": "Learning"},
            {"name": "Activities for children", "description": "Fun and engaging activities for kids", "order_by": 5, "machine_name": "Activities for children", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/05 Activities for children.jpeg", "type": "Kids"},
            {"name": "Guided tours", "description": "Explore sites with expert guides", "order_by": 6, "machine_name": "Guided tours", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/06 Guided tours.jpeg", "type": "Travel"},
            {"name": "Experiences", "description": "Unique and immersive activities", "order_by": 7, "machine_name": "Experiences", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/07 Experiences.jpeg", "type": "Adventure"},
            {"name": "Animal Encounters", "description": "Interact with various animals", "order_by": 8, "machine_name": "Animal Encounters", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/08 Animal Encounters.jpeg", "type": "Wildlife"},
            {"name": "Personalized course", "description": "Tailor-made learning experiences", "order_by": 9, "machine_name": "Personalized course", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/09 Personalized course.jpeg", "type": "Education"},
            {"name": "Nautical activity", "description": "Water-based sports and adventures", "order_by": 10, "machine_name": "Nautical activity", "subcategoriesImage": "staticfiles/subcategoryimg/07experiences/10 Nautical activity.jpeg", "type": "Water Sports"}
        ]
    },
    {
        "name": "Product Purchase",
        "machine_name": "Product Purchase",
        "description": "test",
        "categoriesImage": "staticfiles/adminimag/8 Product Purchase.jpg",
        "type": "Shopping",
        "distance": None,
        "onSite": False,  
        "clickCollect": False,
        "halal": False,
        "handicapped": False,
        "rooftop": False,
        "freeCancellation": False,
        "is_active": True,  
        "status": True,
        "order_by": 8,
        "subcategories": [
            {"name": "Decoration Shops", "description": "Home decor, furniture, and interior accessories", "order_by": 1, "machine_name": "Decoration Shops", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/01 Decoration shops.jpeg", "type": "Home & Living"},
            {"name": "Local Product Shops", "description": "Locally sourced and handmade goods", "order_by": 2, "machine_name": "Local Product Shops", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/02 Local product shops.jpeg", "type": "Handmade & Local"},
            {"name": "Artisan Stores", "description": "Handcrafted art, jewelry, and unique crafts", "order_by": 3, "machine_name": "Artisan Stores", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/03 Artisan stores.jpeg", "type": "Art & Crafts"},
            {"name": "Organic Store", "description": "Organic food, cosmetics, and sustainable products", "order_by": 4, "machine_name": "Organic Store", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/04 Organic store.jpeg", "type": "Sustainable Living"},
            {"name": "Supermarket", "description": "Everyday groceries and household essentials", "order_by": 5, "machine_name": "Supermarket", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/05 Supermarket.jpeg", "type": "Groceries"},
            {"name": "Bookstores", "description": "Books, educational materials, and media", "order_by": 6, "machine_name": "Bookstores", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/06 Bookstores.jpeg", "type": "Books & Media"},
            {"name": "Clothing Stores", "description": "Fashion, accessories, and footwear", "order_by": 7, "machine_name": "Clothing Stores", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/07 Clothing Stores.jpeg", "type": "Fashion"},
            {"name": "Grocery Stores", "description": "Fresh produce, beverages, and packaged goods", "order_by": 8, "machine_name": "Grocery Stores", "subcategoriesImage": "staticfiles/subcategoryimg/08ProductPurchase/08 Grocery stores.jpeg", "type": "Food & Drinks"}
        ]
    }
]



for category_data in categories_data:
    category_data["slug"] = slugify(category_data["name"])  # Ensure slug exists
    category_data.setdefault("type", "General")  # Default type if missing

    category, created = Category.objects.update_or_create(
        machine_name=category_data["machine_name"],
        defaults={
            "name": category_data["name"],
            "slug": category_data["slug"],
            "type": category_data["type"],
            "description": category_data.get("description", ""),
            "categoriesImage": category_data.get("categoriesImage", ""),
            "distance": category_data.get("distance"),
            "onSite": category_data.get("onSite", False),
            "clickCollect": category_data.get("clickCollect", False),
            "halal": category_data.get("halal", False),
            "handicapped": category_data.get("handicapped", False),
            "rooftop": category_data.get("rooftop", False),
            "freeCancellation": category_data.get("freeCancellation", False),
            "is_active": category_data["is_active"],
            "is_deleted": False,
            "status": category_data["status"],
            "order_by": category_data["order_by"],
        }
    )

    action = "Created" if created else "Updated"
    # print(f"{action} Category: {category.name} -> Slug: {category.slug}")

    # Process subcategories
    for subcategory_data in category_data["subcategories"]:
        subcategory_data["slug"] = slugify(subcategory_data["name"])  # Ensure slug exists
        subcategory_data.setdefault("type", "General")

        subcategory, created = Subcategory.objects.update_or_create(
            machine_name=subcategory_data["machine_name"],
            defaults={
                "name": subcategory_data["name"],
                "slug": subcategory_data["slug"],
                "type": subcategory_data["type"],
                "description": subcategory_data.get("description", ""),
                "subcategoriesImage": subcategory_data.get("subcategoriesImage", ""),
                "distance": None,
                "clickCollect": False,
                "halal": False,
                "handicapped": False,
                "rooftop": False,
                "freeCancellation": False,
                "is_active": True,
                "is_deleted": False,
                "status": True,
                "order_by": subcategory_data["order_by"],
                "parentCategoryId": category,
            }
        )

        action = "Created" if created else "Updated"
        # print(f"{action} Subcategory: {subcategory.name} -> Slug: {subcategory.slug}")

print("Categories and subcategories added/updated successfully!")

# updated code 