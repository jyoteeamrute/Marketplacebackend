from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *



from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from ProfessionalUser.models import ProfessionalUser  # Update path if needed

class ProfessionalUserAdminForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput, required=False)

    class Meta:
        model = ProfessionalUser
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and not password.startswith('pbkdf2_'):
            return make_password(password)
        return password


class ProfessionalUserAdmin(admin.ModelAdmin):
    form = ProfessionalUserAdminForm
    list_display = ['email', 'userName', 'company']

admin.site.register(ProfessionalUser, ProfessionalUserAdmin)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'machine_name', 'description')
    search_fields = ('name', 'machine_name')


@admin.register(AdminUser)
class AdminUserAdmin(UserAdmin):  
    list_display = ('id','name','email', 'mobile', 'role', 'is_active', 'is_staff')
    search_fields = ('email', 'mobile')
    list_filter = ('is_active', 'is_staff', 'role')
    ordering = ('email',)
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('mobile', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'mobile', 'role', 'password1', 'password2'),
        }),
    )
    filter_horizontal = ('groups', 'user_permissions')
    
    
#register you rest of the app    
@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("id", "menuname", "created_at", "updated_at", "is_deleted")
    search_fields = ("menuname",)
    list_filter = ("is_deleted",)

@admin.register(Submenu)
class SubmenuAdmin(admin.ModelAdmin):
    list_display = ("id", "submenuname", "menu", "created_at", "updated_at", "is_deleted")
    search_fields = ("submenuname",)
    list_filter = ("menu", "is_deleted")

@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "status", "created_at", "updated_at")
    list_filter = ("status",)
    search_fields = ("name",)

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "sale_name", "sale_value", "role", "created_at")
    search_fields = ("sale_name",)
    list_filter = ("role",)

@admin.register(Submodule)
class SubmoduleAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "module")
    search_fields = ("name",)
    list_filter = ("module",)

@admin.register(Language)
class LanguageAdmin(admin.ModelAdmin):
    list_display = ("id", "name","translateName", "code", "status")
    search_fields = ("name", "code")
    list_filter = ("status",)

@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code", "emoji", "status")
    search_fields = ("name", "code")
    list_filter = ("status",)
    
    
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'slug', 'is_active', 'is_deleted', 'created_at')
    search_fields = ('name',)
    list_filter = ('is_active', 'is_deleted')
    ordering = ('-created_at',)
    readonly_fields = ('slug',)
    
@admin.register(Subcategory)
class SubcategoryAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'slug','parentCategoryId', 'is_active', 'is_deleted', 'created_at')
    readonly_fields = ('slug',)
    search_fields = ('name', 'parent_category__name')
    list_filter = ('is_active', 'is_deleted')
    


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'name', 
        'get_status', 
        'popular', 
        'is_active', 
        'category_limit', 
        'subcategory_limit', 
        'get_three_month_plan', 
        'created_at'
    )
    search_fields = ('name',)
    list_filter = ('popular', 'is_active')
    ordering = ('-created_at',)

    def get_latest_plan(self, obj):
        """Fetch the latest SubscriptionPlan associated with this Subscription."""
        return obj.plans.order_by('-id').first()

    def get_price(self, obj):
        """Get price from the latest SubscriptionPlan."""
        latest_plan = self.get_latest_plan(obj)
        return latest_plan.price if latest_plan else "N/A"
    get_price.short_description = 'Price'

    def get_subscription_type(self, obj):
        """Get subscription type from the latest SubscriptionPlan."""
        latest_plan = self.get_latest_plan(obj)
        return latest_plan.subscription_type if latest_plan else "N/A"
    get_subscription_type.short_description = 'Subscription Type'

    def get_status(self, obj):
        """Get status from the latest SubscriptionPlan."""
        latest_plan = self.get_latest_plan(obj)
        return latest_plan.status if latest_plan else "N/A"
    get_status.short_description = 'Status'

    def get_no_commitment_plan(self, obj):
        """Get no commitment plan from the latest SubscriptionPlan."""
        latest_plan = self.get_latest_plan(obj)
        return latest_plan.no_commitment_plan if latest_plan else "N/A"
    get_no_commitment_plan.short_description = 'No Commitment Plan'

    def get_three_month_plan(self, obj):
        """Get three-month plan from the latest SubscriptionPlan."""
        latest_plan = self.get_latest_plan(obj)
        return latest_plan.three_month_plan if latest_plan else "N/A"
    get_three_month_plan.short_description = 'Three Month Plan'

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'get_subscription_name',
        'subscription_type',
        'price',
        # 'save_profit_percentage',
        'no_commitment_plan',
        'three_month_plan',
        'status',
        'monthlyPlan',
        'annualPlan',
        'is_active',
        'is_deleted',
        'created_at'
    )
    search_fields = ('subscription__name', 'subscription_type', 'status')
    list_filter = ('subscription_type', 'status', 'is_active', 'is_deleted')
    ordering = ('-created_at',)

    def get_subscription_name(self, obj):
        """Return the related Subscription's name."""
        return obj.subscription.name
    get_subscription_name.short_description = "Subscription Name"


@admin.register(RolePermissions)
class RolePermissionsAdmin(admin.ModelAdmin):
    list_display = ('id','rolename', 'menu', 'get_submenus', 'create_permission', 'read_permission', 'update_permission', 'delete_permission', 'status', 'is_deleted', 'created_at')
    search_fields = ('role__name', 'menu__menuname')  
    list_filter = ('status', 'is_deleted', 'create_permission', 'read_permission', 'update_permission', 'delete_permission')
    ordering = ('-created_at',)

    def get_submenus(self, obj):
        """Find other menus that might be considered submenus for this role."""
        submenus = RolePermissions.objects.filter(role=obj.rolename).exclude(menu=obj.menu)
        
        if submenus.exists():
            return ", ".join([submenu.menu.menuname for submenu in submenus if submenu.menu])
        return "No Submenus"

    get_submenus.short_description = 'Submenus'
@admin.register(Facility)
class FacilityAdmin(admin.ModelAdmin):
    list_display = ('id','name', 'is_selected', 'created_at')
    search_fields = ('name',)
    ordering = ('-created_at',)



@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('couponCode', 'discount_type', 'amount', 'status', 'is_deleted', 'created_at', 'updated_at')
    list_filter = ('status', 'discount_type', 'is_deleted', 'created_at')
    search_fields = ('couponCode',)
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')




@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ('id', 'subject', 'ticket_category', 'status', 'created_at', 'resolved_at', 'is_deleted')
    list_filter = ('status', 'ticket_category', 'is_deleted')
    search_fields = ('subject', 'description')
    readonly_fields = ('created_at', 'updated_at', 'resolved_at')


@admin.register(SupportOption)
class Supportoption(admin.ModelAdmin):
    list_display = ('title','description')
    search_fields = ('title',)
  

  
@admin.register(Advertisement)
class Advertisement(admin.ModelAdmin):
    list_display = ('title','description')
    search_fields = ('title',)
    


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'notification_type', 'user', 'professional_user', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username', 'professional_user__userName')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)



@admin.register(LegalDocument)
class LegalDocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'language', 'is_active', 'version', 'updated_at')
    search_fields = ('title', 'content')
    list_filter = ('language', 'is_active')
    prepopulated_fields = {"slug": ("title",)}
