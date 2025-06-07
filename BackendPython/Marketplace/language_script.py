import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Marketplace.settings")
django.setup()

from Admin.models import Language 

USER_ID = None
languages_list = [
    {
        "name": "French",
        "code": "FR",
        "shortName": "(française)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/fr.svg",
        "countryFlag": "🇫🇷",
        "translateName": "Français",
        "order_by": 2,
        
    },
    {
        "name": "English",
        "code": "US",
        "shortName": "(English)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/us.svg",
        "countryFlag": "🇺🇸",
        "translateName": "English",
        "order_by": 1,
    },
    {
        "name": "Spanish",
        "code": "ES",
        "shortName": "(español)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/es.svg",
        "countryFlag": "🇪🇸",
        "translateName": "Español",
        "order_by": 3,
    },
    {
        "name": "Chinese",
        "code": "CN",
        "shortName": "Zhōngguó (中國)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/cn.svg",
        "countryFlag": "🇨🇳",
        "translateName": "中文",
        "order_by": 4,
    },
    {
        "name": "Arabic",
        "code": "SA",
        "shortName": "(عربي)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/sa.svg",
        "countryFlag": "🇸🇦",
        "translateName": "العربية",
        "order_by": 5,
    },
    {
        "name": "German",
        "code": "DE",
        "shortName": "(Deutsch)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/de.svg",
        "countryFlag": "🇩🇪",
        "translateName": "Deutsch",
        "order_by": 6,
    },
    {
        "name": "Dutch",
        "code": "NL",
        "shortName": "(Nederlands)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/nl.svg",
        "countryFlag": "🇳🇱",
        "translateName": "Nederlands",
        "order_by": 7,
    },
    {
        "name": "Italian",
        "code": "IT",
        "shortName": "(italiano)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/it.svg",
        "countryFlag": "🇮🇹",
        "translateName": "Italiano",
        "order_by": 8,
    },
    {
        "name": "Portuguese",
        "code": "PT",
        "shortName": "(português)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/pt.svg",
        "countryFlag": "🇵🇹",
        "translateName": "Português",
        "order_by": 9,
    },
    {
        "name": "Japanese",
        "code": "JP",
        "shortName": "(日本語)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/jp.svg",
        "countryFlag": "🇯🇵",
        "translateName": "日本語",
        "order_by": 10,
    },
    {
        "name": "Thai",
        "code": "TL",
        "shortName": "(แบบไทย)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/tl.svg",
        "countryFlag": "🇹🇭",
        "translateName": "ไทย",
        "order_by": 11,
    },
    {
        "name": "Swedish",
        "code": "SE",
        "shortName": "(svenska)",
        "userID": USER_ID,
        "image": "https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/se.svg",
        "countryFlag": "🇸🇪",
        "translateName": "Svenska",
        "order_by": 12,
    },
    { "name": 'Russian',
    "code": 'RU',
    "shortName": '(Russian)',
    "userID": USER_ID,
    "image": 'https://cdn.jsdelivr.net/gh/lipis/flag-icons@7.2.3/flags/4x3/ru.svg',
    "countryFlag": '🇷🇺',
    "translateName": 'Русский',
    "order_by": 13,
    }
]

def seed_languages():
    user = None  

    for language_data in languages_list:
        language, created = Language.objects.update_or_create(
            code=language_data["code"],  
            defaults={
                "name": language_data["name"],
                "shortName": language_data["shortName"],
                "userID": user,  
                "image": language_data["image"],
                "countryFlag": language_data["countryFlag"],
                "translateName": language_data["translateName"],
                
                "status": True, 
            },
        )
        if created:
            print(f"Inserted: {language.name} ({language.code})")
        else:
            print(f"Updated: {language.name} ({language.code})")

if __name__ == "__main__":
    seed_languages()