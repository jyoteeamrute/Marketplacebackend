from re import M

from django.contrib import admin

from .forms import ProfessionalUserAdminForm
from .models import *

admin.site.unregister(ProfessionalUser)

@admin.register(Follow)
class FollowUserAdmin(admin.ModelAdmin):
    list_display = ('id','user', 'company')


class ProfessionalUserAdmin(admin.ModelAdmin):
    form = ProfessionalUserAdminForm
    list_display = ['id','email', 'userName', 'company'] 

admin.site.register(ProfessionalUser, ProfessionalUserAdmin)
 
@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('id',)


@admin.register(eventBooking)
class eventBooking(admin.ModelAdmin):
    list_display = ('id','created_at',)
    


@admin.register(RoomBooking)
class RoomBooking(admin.ModelAdmin):
    list_display = ('id','checkin_date','checkout_date')


@admin.register(CompanyDetails)
class CompanyDetailsAdmin(admin.ModelAdmin):
    list_display = ('id','companyName','managerFullName','email','phoneNumber')
    

@admin.register(StoreReel)
class StoreReelAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'views', 'likes', 'created_at')  # ✅ Ensure fields exist in StoreReel
    list_filter = ('created_at',)
    search_fields = ('title',)
    readonly_fields = ('created_at',)  # ✅ Remove invalid fields

    def m3u8_url_display(self, obj):
        return obj.m3u8_url if obj.m3u8_url else "No URL"

    def thumbnail_display(self, obj):
        return obj.thumbnail.url if obj.thumbnail else "No Thumbnail"

    m3u8_url_display.short_description = "M3U8 URL"
    thumbnail_display.short_description = "Thumbnail"

    readonly_fields = ('m3u8_url_display', 'thumbnail_display', 'created_at')

@admin.register(ReelLike)
class ReelLikeAdmin(admin.ModelAdmin):
    list_display = ('user', 'reel', 'is_liked')  # Jo fields dikhni chahiye
    search_fields = ('user__username', 'reel__id')  # Search option ke liye
    list_filter = ('is_liked',)
    
@admin.register(ReelShare)
class ReelShareAdmin(admin.ModelAdmin):
    list_display = ('user', 'reel')  # Jo fields dikhni chahiye
    
@admin.register(ReelView)
class ReelViewAdmin(admin.ModelAdmin):
    list_display = ("user", "reel", "viewed_at") 
    
@admin.register(ReelComment)
class ReelCommentAdmin(admin.ModelAdmin):
    list_display = ("id","user", "reel", "comment", "parent", "created_at") 
    
@admin.register(StoreImage)
class StoreImageAdmin(admin.ModelAdmin):
    list_display = ('id','title', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('title',)
    readonly_fields = ('created_at',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "id", "productname", "company", "productType", "folder", "serviceTime", "created_at", "categoryId","subCategoryId","totalEmployees"
    )
    list_filter = ("company", "productType", "categoryId", "subCategoryId", "isActive")
    search_fields = ("productname", "company__name", "categoryId__name", "subCategoryId__name")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "service_time_formatted")

    def service_time_formatted(self, obj):
        if obj.serviceTime is None:
            return "00:00:00"
        seconds = obj.serviceTime
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"
    service_time_formatted.short_description = "Service Time (HH:MM:SS)"

    fieldsets = (
        ("Product Information", {
            "fields": ("productname", "productType", "cruiseFacility","description", "keywords", "cruiseName", "petAllowed", "petType","roomFacility","smokingAllowed","noofMembers","roomview","duration","bookedQuantity","totalEmployees")
        }),
        ("Pricing & Stock", {
            "fields": ("priceOnsite", "priceClickAndCollect", "priceDelivery",
                       "promotionalPrice", "vatRate", "quantity","onsite", "clickandCollect", "onDelivery", "basePrice", "discount")
        }),
        ("Tickets Concert", {
            "fields": ("artistName", "bandName","startTime","endTime")
        }),
         ("Cruise Addresses", {
            "fields": ("startAddress", "endAddress")
        }),
        ("Category & Company Details", {
            "fields": ("folder", "company", "categoryId", "subCategoryId")
        }),
        ("Availability & Preparation", {
            "fields": ("availabilityDateTime", "preparationDateTime", "serviceTime", "service_time_formatted")
        }),
        ("Images & Gallery", {
            "fields": ("ProductImage", "galleryImage")
        }),
        ("Delivery Details", {
            "fields": ("deliveryMethod", "deliveryPricePerGram", "delivery", "nonRestaurant")
        }),
        ("Ratings & Status", {
            "fields": ("average_rating", "total_ratings", "isActive")
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),

    )


@admin.register(StoreEvent)
class EventAdmin(admin.ModelAdmin):
    list_display = ('id','eventTitle', 'createdAt')
    list_filter = ('createdAt',)
    search_fields = ('evenTitle',)
    readonly_fields = ('createdAt',)
    

    
@admin.register(TableReservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = ('id', 'customerName', 'reservationDate', 'timeSlot', 'status')
    list_filter = ('status', 'reservationDate')
    search_fields = ('customerName', 'contactInfo')
    ordering = ('-reservationDate',)

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('id','customer_name', 'product_service', 'total_amount')
    search_fields = ('total_amount',)

@admin.register(SavedReel)
class SavedReelAdmin(admin.ModelAdmin):
    list_display = ('id',)
    
@admin.register(ReelFolder)
class SavedReelAdminaa(admin.ModelAdmin):
    list_display = ('id','name',)

@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = ("id", "company", "product", "stock_quantity", "low_stock_threshold", "last_updated")
    list_filter = ("company", "product")
    search_fields = ("product__name", "company__name")
    ordering = ("-last_updated",)
    

@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ("id", "sender", "receiver", "relationship_type", "status", "created_at")
    list_filter = ("relationship_type", "status", "created_at")
    search_fields = ("sender_object_id", "receiver_object_id")
    ordering = ("-created_at",)
    
@admin.register(DeliveryService)
class DeliveryServiceAdmin(admin.ModelAdmin):
    list_display = ("id","company", "service_type", "delivery_fee", "minimum_order_amount", "travel_fee_per_km", "is_enabled")
    list_filter = ("service_type", "is_enabled", "company")
    search_fields = ("company__name", "service_type")
 

    
@admin.register(CategoryFolder)
class CategoryFolderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "productType", "professionalUser", "created_at")
    list_filter = ("productType", "created_at")
    search_fields = ("name", "professionalUser__email")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)

    fieldsets = (
        ("Basic Information", {
            "fields": ("name", "productType", "professionalUser")
        }),
        ("Categories", {
            "fields": ("categories",)
        }),
        ("Timestamps", {
            "fields": ("created_at",)
        }),
    )

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product', 'quantity', 'price')
    can_delete = False
    
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'orderStatus', 'order_type', 'total_price', 'is_paid', 'created_at',"order_id")
    list_filter = ('orderStatus', 'order_type', 'is_paid', 'created_at')
    search_fields = ('user__email', 'professional_user__email', 'customer_name', 'contact_number', 'email')
    readonly_fields = ('created_at',)
    inlines = [OrderItemInline]
    fieldsets = (
        (None, {
            'fields': (
                'user', 'company', 'orderStatus', 'order_type', 'is_paid','order_id',
                'promo_code', 'note', 'total_price','clickCollectPreparationTime','deliveryPreparationTime','onSitePreparationTime'
            )
        }),
        ('Onsite Info', {
            'fields': ('date', 'time', 'members'),
            'classes': ('collapse',)
        }),
        ('Click & Collect Info', {
            'fields': ('customer_name', 'contact_number', 'email'),
            'classes': ('collapse',)
        }),
        ('Delivery Info', {
            'fields': ('user_address',),
            'classes': ('collapse',)
        }),
        ('Home Visit Info', {
            'fields': ('manual_address',),
            'classes': ('collapse',)
        }),
    )
@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'product', 'quantity', 'price')
    list_filter = ('product',)
    search_fields = ('product__productname', 'order__id')
  
@admin.register(Promotions)
class PromotionsAdmin(admin.ModelAdmin):
    list_display = (
        'promotionName',
        'company',
        'get_product_ids',
        'product_service_type',
        'discountAmount',
        'startDateTime',
        'endDateTime'
    )
    search_fields = ('promotionName', 'promotionDescription')
    def get_product_ids(self, obj):
        return ", ".join([str(p.id) for p in obj.productId.all()])
    get_product_ids.short_description = 'Product IDs'  

    def get_product_ids(self, obj):
        return ", ".join([str(p.id) for p in obj.productId.all()])
    get_product_ids.short_description = 'Product IDs'
@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('sender__username', 'recipient__user__username', 'content')
    ordering = ('-created_at',)
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'product__productname', 'comment')
    ordering = ('-created_at',)
    autocomplete_fields = ('user', 'product')
    
@admin.register(CompanyReview)
class CompanyReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'user', 'rating', 'created_at')
    list_filter = ('company', 'rating', 'created_at')
    search_fields = ('company__company_name', 'user__username', 'review_text')
    ordering = ('-created_at',)
    readonly_fields = ('created_at',)
    

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'company', 'product', 'quantity', 'order_type', 
        'promo_code', 'get_item_total_display', 'created_at'
    )
    list_filter = ('order_type', 'created_at', 'company')
    search_fields = (
        'user__email', 'company__company_name', 'product__productname', 
        'customer_name', 'contact_number', 'email'
    )
    readonly_fields = ('created_at', 'get_item_total_display')

    fieldsets = (
        (None, {
            'fields': (
                'user', 'company', 'product', 'quantity', 'order_type', 
                'promo_code', 'note', 'get_item_total_display'
            )
        }),
        ('Onsite Info', {
            'fields': ('date', 'time', 'members'),
            'classes': ('collapse',)
        }),
        ('Click & Collect Info', {
            'fields': ('customer_name', 'contact_number', 'email'),
            'classes': ('collapse',)
        }),
        ('Delivery Info', {
            'fields': ('address',),
            'classes': ('collapse',)
        }),
        ('Home Visit Info', {
            'fields': ('manual_address',),
            'classes': ('collapse',)
        }),
    )

    def get_item_total_display(self, obj):
        return obj.get_item_total()
    get_item_total_display.short_description = 'Total Price'

@admin.register(AdvertiseCampaign)
class AdvertiseCampaignAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'title', 'company', 'objective', 'ad_type', 'bid_type', 
        'max_bid', 'daily_budget', 'duration_days', 'startDateTime', 
        'endDateTime', 'target_type', 'location', 'age_range', 'gender', 
        'today_clicks', 'today_impressions', 'last_updated'
    )
    list_filter = ('bid_type', 'objective', 'ad_type', 'target_type', 'gender', 'age_range')
    search_fields = ('title', 'description', 'company__company_name', 'location')
    readonly_fields = ('created_at', 'last_updated')
    filter_horizontal = ('preferences',)
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'company', 'objective', 'ad_type', 'content')
        }),
        ('Bidding & Placement', {
            'fields': ('bid_type', 'max_bid')
        }),
        ('Budget & Schedule', {
            'fields': ('daily_budget', 'duration_days', 'startDateTime', 'endDateTime')
        }),
        ('Targeting', {
            'fields': ('target_type', 'location', 'age_range', 'gender', 'preferences')
        }),
        ('Tracking', {
            'fields': ('today_clicks', 'today_impressions', 'last_updated', 'created_at')
        }),
    )



@admin.register(slotBooking)
class SlotBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'full_name', 'email', 'phone', 'booking_date', 'slot', 'status', 'is_paid', 'created_at')
    list_filter = ('status', 'booking_date', 'is_paid', 'created_at')
    search_fields = ('booking_id', 'full_name', 'email', 'phone')
    ordering = ('-created_at',)


@admin.register(Promocode)
class PromocodeAdmin(admin.ModelAdmin):
    list_display = ('promocode', 'specificAmount', 'startDateTime', 'endDateTime', 'company')
    search_fields = ('promocode', 'title', 'description')
    ordering = ('-startDateTime',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'user', 'notification_type', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('sender__username', 'user__username', 'message')
    ordering = ('-created_at',)    

@admin.register(LoyaltyCard)
class LoyaltyCardAdmin(admin.ModelAdmin):
    list_display = ("company", "threshold_point")

@admin.register(LoyaltyPoint)
class LoyaltyPoint(admin.ModelAdmin):
    list_display = ("company","total_points") 
  
    
    
@admin.register(CruiseRoom)
class CruiseRoomAdmin(admin.ModelAdmin):
    list_display = (
        'room_id', 'product_id_display', 'roomType', 'roomQuantity', 'roomPrice', 'adults', 'created_at'
    )
    list_filter = ('roomType', 'product', 'created_at')
    search_fields = ('room_id', 'roomType', 'product__productname')
    ordering = ('-created_at',)

    def product_id_display(self, obj):
        return obj.product.id if obj.product else None
    product_id_display.short_description = 'Product ID'



@admin.register(TicketsConcert)
class TicketsConcertAdmin(admin.ModelAdmin):
    list_display = (
        "name", "description", "members", "quantity", "price", "created_at"
    )

@admin.register(NightClubTicket)
class NightClubTicketAdmin(admin.ModelAdmin):
    list_display = (
        "tableName", "description", "members", "quantity", "price", "created_at"
    )

@admin.register(TicketsAmusementPark)
class TicketsAmusementParkAdmin(admin.ModelAdmin):
    list_display = (
        "name", "description", "adultPrice", "childPrice", "created_at"
    )



@admin.register(CruiseFacility)
class CruiseFacility(admin.ModelAdmin):
    list_display = (
       'name',
    )

@admin.register(RoomFacility)
class RoomFacility(admin.ModelAdmin):
    list_display = (
       'name',
    )
@admin.register(OrderBookingIcons)
class OrderBookingIcons(admin.ModelAdmin):
    list_display = (
       'name','icon',
    )


@admin.register(Ticket)
class Ticket(admin.ModelAdmin):
    list_display = (
       'id',
    )

@admin.register(BookingTicketItem)
class BookingTicketItem(admin.ModelAdmin):
    list_display = (
       'id',
    )





@admin.register(experienceBooking)
class experienceBooking(admin.ModelAdmin):
    list_display = (
       'id',
    )


@admin.register(aestheticsBooking)
class AestheticsBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'full_name', 'email', 'phone', 'booking_date', 'slot', 'status', 'is_paid', 'created_at')
    search_fields = ('booking_id', 'full_name', 'email', 'phone')
    list_filter = ('status', 'is_paid', 'booking_date')
    ordering = ('-created_at',)

@admin.register(relaxationBooking)
class RelaxationBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'full_name', 'email', 'phone', 'booking_date', 'slot', 'status', 'is_paid', 'created_at')
    search_fields = ('booking_id', 'full_name', 'email', 'phone')
    list_filter = ('status', 'is_paid', 'booking_date')
    ordering = ('-created_at',)

@admin.register(artandcultureBooking)
class ArtAndCultureBookingAdmin(admin.ModelAdmin):
    list_display = ('booking_id', 'full_name', 'email', 'phone', 'booking_date', 'slot', 'status', 'is_paid', 'created_at')
    search_fields = ('booking_id', 'full_name', 'email', 'phone')
    list_filter = ('status', 'is_paid', 'booking_date')
    ordering = ('-created_at',)