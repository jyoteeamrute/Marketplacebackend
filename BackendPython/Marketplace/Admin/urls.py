from django.urls import path
from .views import *
from django.conf.urls.static import static
from django.conf import settings


# urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path('login/', AdminLoginAPIView.as_view(), name='admin-login'),
    path('forgot-password/', AdminForgotPasswordAPIView.as_view(), name='forgot-password'),
    path("update-password/", AdminResetPasswordAPIView.as_view(), name="reset-password"),
    path('view-profile/', AdminProfileView.as_view(), name='view-profile'),
    path('refresh-token/', RefreshAccessTokenView.as_view(), name='token-refresh'),
    path('logout/', AdminLogoutView.as_view(), name='admin-logout'),
    
     
    path('create-users/', AdminCreateUserAPIView.as_view(), name='admin-create-user'),
    path('all-users-list/', AdminUserListView.as_view(), name='user-list'),
    path('admin-user/get/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-user-detail'),
    path('admin-user/update/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-user-update'),
    path('admin-user/delete/<int:pk>/', AdminUserDetailAPIView.as_view(), name='admin-user-delete'),
    
    
    path('professional-user/verify/<int:user_id>/', VerifyProfessionalUserAPIView.as_view(), name='verify-professional'),
    path('all-prousers-list/', ProfessionalUserListView.as_view(), name='prouser-list'),
    path('all-prousers-lists/', ProfessionalUserListViewNew.as_view(), name='all-prouser-list'), 
    path('professional-user/get/<int:user_id>/', GetProfessionalUserAPIView.as_view(), name='get-professional-user'),
    path('professional-login-details/', AdminProfessionalUserLoginDetailsView.as_view(), name='professional-user-login-details'),

    path('regular-users/', AdminListUsersAPIView.as_view(), name='list-users'),
    path('regular-users/get/<int:user_id>/', UserAppAPIView.as_view(), name='list-users'),
    path('update-user/<int:user_id>/', UpdateUserByIdAPIView.as_view(), name='update-user'),
    path('user-login-details/', AdminUserLoginDetailsView.as_view(), name='user-login-details'),
    path('normal-user/<int:user_id>/update/', AdminUpdateUserView.as_view(), name='admin-update-user'),
    

    path('administrators/', AdminListAdministratorsAPIView.as_view(), name='list-administrators'),
    path('professionals/', AdminListProfessionalsAPIView.as_view(), name='list-professionals'),
    
    
    path('role-create/', AdminRoleCreateAPIView.as_view(), name='create-role'),  
    path('get-role-list/', AdminRoleCreateAPIView.as_view(), name='get-role-list'), 
    path('roles/get/<int:pk>/', AdminRoleDetailAPIView.as_view(), name='role-get'), 
    path('roles/update/<int:pk>/', AdminRoleDetailAPIView.as_view(), name='role-update'), 
    path('roles/delete/<int:pk>/', AdminRoleDetailAPIView.as_view(), name='role-delete'), 
    
    
    path('menus-add/', MenuListCreateAPIView.as_view(), name='menu-create'),
    path('menus-list/', MenuListCreateAPIView.as_view(), name='menu-list-create'),
    path('menus/get/<int:pk>/', MenuDetailAPIView.as_view(), name='menu-detail'),
    path('menus/update/<int:pk>/', MenuDetailAPIView.as_view(), name='menu-update'),
    path('menus/delete/<int:pk>/', MenuDetailAPIView.as_view(), name='menu-delete'),
    
    path('submenus-add/', SubmenuListCreateAPIView.as_view(), name='submenu-create'),
    path('submenus-list/', SubmenuListCreateAPIView.as_view(), name='submenu-list-create'),
    path('submenus/get/<int:pk>/', SubmenuDetailAPIView.as_view(), name='submenu-detail'),
    path('submenus/update/<int:pk>/', SubmenuDetailAPIView.as_view(), name='submenu-update'),
    path('submenus/delete/<int:pk>/', SubmenuDetailAPIView.as_view(), name='submenu-delete'),
    
    
    path('module-add/', ModuleListCreateAPIView.as_view(), name='module-create'),
    path('modules-list/', ModuleListCreateAPIView.as_view(), name='module-list-create'),
    path('modules/get/<int:pk>/', ModuleDetailAPIView.as_view(), name='module-detail'),
    path('modules/update/<int:pk>/', ModuleDetailAPIView.as_view(), name='module-update'),
    path('modules/delete/<int:pk>/', ModuleDetailAPIView.as_view(), name='module-delete'),
    path('modules/status-options/', ModuleStatusDropdownAPIView.as_view(), name='module-status-options'),
    
    
    path('sales-add/', SaleListCreateAPIView.as_view(), name='sale-create'),
    path('sales-list/', SaleListCreateAPIView.as_view(), name='sale-list-create'),
    path('sales/get/<int:pk>/', SaleDetailAPIView.as_view(), name='sale-detail'),
    path('sales/update/<int:pk>/', SaleDetailAPIView.as_view(), name='sale-update'),
    path('sales/delete/<int:pk>/', SaleDetailAPIView.as_view(), name='sale-delete'),
    
    
    path('submodule-add/', SubmoduleListCreateAPIView.as_view(), name='submodule-create'),
    path('submodule-list/', SubmoduleListCreateAPIView.as_view(), name='submodule-list-create'),
    path('submodule/get/<int:pk>/', SubmoduleDetailAPIView.as_view(), name='submodule-detail'),
    path('submodule/update/<int:pk>/', SubmoduleDetailAPIView.as_view(), name='submodule-update'),
    path('submodule/delete/<int:pk>/', SubmoduleDetailAPIView.as_view(), name='submodule-delete'),


    path('languages-add/', LanguageListCreateAPIView.as_view(), name='create-language'),
    path('languages-list/', LanguageListCreateAPIView.as_view(), name='language-list'),
    path('languages/get/<int:pk>/', LanguageRetrieveUpdateDeleteAPIView.as_view(), name='language-detail'),
    path('languages/update/<int:pk>/', LanguageRetrieveUpdateDeleteAPIView.as_view(), name='language-update'),
    path('languages/delete/<int:pk>/', LanguageRetrieveUpdateDeleteAPIView.as_view(), name='language-delete'),
    path('languages/search/', SearchLanguageAPIView.as_view(), name='search-language'),
    
    path('country-add/', ConutryListCreateAPIView.as_view(), name='country-create'),
    path('country-list/', ConutryListCreateAPIView.as_view(), name='country-list-detail'),
    path('country/get/<int:pk>/', CountryRetrieveUpdateDeleteAPIView.as_view(), name='country-detail'),
    path('country/update/<int:pk>/', CountryRetrieveUpdateDeleteAPIView.as_view(), name='country-update'),
    path('country/delete/<int:pk>/', CountryRetrieveUpdateDeleteAPIView.as_view(), name='country-delete'),
    path('country/search/', SearchCountryAPIView.as_view(), name='search-country'),
    
    
    path('categories-add/', CategoryListCreateAPIView.as_view(), name='category-create'),
    path('categories-list/', CategoryListCreateAPIView.as_view(), name='category-list'),
    path('categories/get/<int:pk>/', CategoryRetrieveUpdateDeleteAPIView.as_view(), name='category-detail'),
    path('categories/update/<int:pk>/', CategoryRetrieveUpdateDeleteAPIView.as_view(), name='category-update'),
    path('categories/delete/<int:pk>/', CategoryRetrieveUpdateDeleteAPIView.as_view(), name='category-delete'),
    path('categories/find/', CategoryFilterAPIView.as_view(), name='category-find'),
    path('categories/search/', CategorysubcategoryListAPIView.as_view(), name='category-list'),

    path('categories/reorder/', CategoryReorderAPIView.as_view(), name='category-reorder'),

    path('upload-multiple-category-images/', UploadMultipleCategoryImages.as_view(), name='upload-multiple-category-images'),
    
    
    path('subcategories-add/', SubcategoryListCreateAPIView.as_view(), name='subcategories-create'),
    path('subcategories-list/', SubcategoryListCreateAPIView.as_view(), name='subcategories-list'),
    path('subcategories/get/<int:pk>/', SubcategoryRetrieveUpdateDeleteAPIView.as_view(), name='subcategory-detail'),
    path('subcategories/update/<int:pk>/', SubcategoryRetrieveUpdateDeleteAPIView.as_view(), name='subcategory-update'),
    path('subcategories/delete/<int:pk>/', SubcategoryRetrieveUpdateDeleteAPIView.as_view(), name='subcategory-delete'),
    path("subcategories/<int:parentCategoryId>/", GetAllSubCategoryWithFilterParents.as_view(), name="subcategory-filter"),
    path("subcategories/search/", SearchSubCategory.as_view(), name="subcategory-search"),
    
    path('subscription/add/', SubscriptionListCreateAPIView.as_view(), name='create_subscription'),
    path('subscription/list/', SubscriptionListCreateAPIView.as_view(), name='list_subscriptions'),
    path('subscription/get/<int:pk>/', SubscriptionRetrieveUpdateDeleteAPIView.as_view(), name='get_subscription_details'),
    path('subscription/update/<int:pk>/', SubscriptionRetrieveUpdateDeleteAPIView.as_view(), name='update_subscription'),
    path('subscription/delete/<int:pk>/', SubscriptionRetrieveUpdateDeleteAPIView.as_view(), name='delete_subscription'),
    path("subscriptions/popular/", PopularSubscriptionAPIView.as_view(), name="popular-subscriptions"),
    path("subscriptions/search/", SearchSubscriptionAPIView.as_view(), name="search-subscriptions"),

    path("subscription-plan/create/", SubscriptionPlanCreateView.as_view(), name="create-subscription-plan"),
    path("subscription-plan/list/", SubscriptionPlanListView.as_view(), name="create-subscription-plan-list"),
    path('subscription-plan/update/<int:pk>/', UpdateSubscriptionPlanAPI.as_view(), name='update-subscription-plan'),
    path('subscription-plan/delete/<int:pk>/', DeleteSubscriptionPlanAPI.as_view(), name='delete-subscription-plan'),
    path('subscription-plan/subscription/<int:pk>/', SubscriptionPlanBySubscriptionView.as_view(), name='getList-subscription-plan'),


    path('rolepermissions/save/', RolePermissionsView.as_view(), name='create-role-permissions'),
    path('rolepermissions/list/', RolePermissionViewAll.as_view(), name='list-role-permissions'),  
    path('rolepermissions/get/<int:role_permission_id>/', RolePermissionViewAll.as_view(), name='role-permissions-detail'),  
    path('rolepermissions/update/<int:role_permission_id>/', RolePermissionsView.as_view(), name='update-role-permissions'),  
    path('rolepermissions/delete/<int:role_permission_id>/', RolePermissionsView.as_view(), name='delete-role-permissions'),  

    path("support_tickets-list/", AdminTicketListView.as_view(), name="admin-ticket-list"),  # View all tickets
    path("support_tickets/get/<int:pk>/", AdminTicketDetailView.as_view(), name="admin-ticket-detail"),  # View single ticket
    path("support_tickets/<int:ticket_id>/update/", AdminResolveTicketView.as_view(), name="admin-refund-ticket"),  # Resolve escalated tickets
    path("support_tickets/<int:ticket_id>/delete/", AdminDeleteTicketView.as_view(), name="admin-delete-ticket"),  # Soft delete ticket
    path('tickets/refund-list/', GetRefundTicketsAPIView.as_view(), name='refund-tickets-list'),

    

    path('professional-user/verify/<int:user_id>/', VerifyProfessionalUserAPIView.as_view(), name='verify-professional'),
    
    path("facility/create/", FacilityCreateView.as_view(), name="facility-create"),
    path("facility/list/", FacilityListView.as_view(), name="facility-list"),
    path("facility/<int:id>/", FacilityDetailView.as_view(), name="facility-detail"),
    path("facility/update/<int:id>/", FacilityUpdateView.as_view(), name="facility-update"),
    path("facility/delete/<int:id>/", FacilityDeleteView.as_view(), name="facility-delete"),
    path("facility/select/", FacilitySelectView.as_view(), name="facility-select"),
    path("facility/create-all-once/", FacilityBulkCreateView.as_view(), name="facility-create-all-once"),

    path('subcategories/filter/', SubcategoryFilterView.as_view(), name='subcategory-filter'),
    

    
    path('coupons/create/', CouponCreateView.as_view(), name='admin-create-coupon'),
    path('coupons-list/', CouponListView.as_view(), name='admin-list-coupons'),
    path('coupons/<int:id>/', CouponRetrieveView.as_view(), name='admin-get-coupon'),
    path('coupons/update/<int:id>/', CouponUpdateView.as_view(), name='admin-update-coupon'),
    path('coupons/delete/<int:id>/', CouponDeleteView.as_view(), name='admin-delete-coupon'),

    path('payments-list/', PaymentListView.as_view(), name='payment-list'),
    path('payments-export-list/', PaymentListViewExports.as_view(), name='payment-export-list'),
    path('user-payments-export-list/', UserPaymentListViewExports.as_view(), name='user-payment-list'),
    path('user-payments/', UserPaymentListView.as_view(), name='user-payment-list'),
    path('payment-cards/', CardListView.as_view(), name='card-list'),

    path('admin-dashboard/', DashboardStatsAPIView.as_view(), name='admin-dashboard-summary'),


    path('professional-user-orders/', ProfessionalUserOrderSummaryAPIView.as_view(), name='professional-user-orders'),

    path('help-center-list/', HelpCenterView.as_view(), name='help-center'),
    path('create-help-category/', HelpCategoryCreateView.as_view(), name='create-help-category'),
    path('update-help-category/<int:pk>/', HelpCategoryUpdateView.as_view(), name='update-help-category'),
    path('delete-help-category/<int:id>/', HelpCategoryDeleteView.as_view(), name='delete-help-category'),

    path('create-help-faq/', HelpFAQViewSet.as_view({'post': 'create'}), name='create-help-faq'),
    path('list-help-faq/', HelpFAQViewSet.as_view({'get': 'list'}), name='list-help-faq'),
    path('get-help-faq/<int:pk>/', HelpFAQViewSet.as_view({'get': 'retrieve'}), name='get-help-faq'),
    path('update-help-faq/<int:pk>/', HelpFAQViewSet.as_view({'put': 'update'}), name='update-help-faq'),
    path('partial-update-help-faq/<int:pk>/', HelpFAQViewSet.as_view({'patch': 'partial_update'}), name='partial-update-help-faq'),
    path('delete-help-faq/<int:pk>/', HelpFAQViewSet.as_view({'delete': 'destroy'}), name='delete-help-faq'),

    path('companies-list/', CompanyDetailsListView.as_view(), name='company-list'),
    path('companies/<int:company_id>/', CompanyDetailsRetrieveView.as_view(), name='company-detail'),
    path('companies/<int:company_id>/update/', CompanyDetailsUpdateView.as_view(), name='company-update'),
    path('store-media/', StoreMediaListView.as_view(), name='store-media-list'),
    path('update-media-status/', UpdateStoreMediaStatusView.as_view(), name='update-store-media-status'),
    path('company/update-status/<int:company_id>/', UpdateCompanyIsActiveAPIView.as_view(), name='update-company-status'),

    path('reel-reports-list/', AllReelReportsView.as_view(), name='all-reports'),
    path('reel-reports/<int:report_id>/', ReelReportDetailView.as_view(), name='report-detail'),
    path('reel-reports/<int:report_id>/update-status/', UpdateReelReportStatusView.as_view(), name='update-report-status'),
    path('reel-reports/<int:report_id>/delete/', DeleteReelReportView.as_view(), name='delete-report'),
    
    path('advertisements/', AdvertisementListCreateView.as_view(), name='advertisementcreate'),
    path('advertisements/<int:pk>/', AdvertisementDetailView.as_view(), name='advertisement-detail'),
    path('advertisement/delete/<int:pk>/', AdvertisementDeleteAPIView.as_view(), name='advertisement-delete'),
    path('update-advertisement-status/<int:advertisement_id>/', UpdateAdvertisementIsActiveAPIView.as_view(), name='update-advertisement-status'),
    # path("categories/upload/", upload_category, name="upload_category"),
    path('admin-bank-accounts-list/', BankAccountListView.as_view(), name='bank-account-list'),
    path('admin-bank-accounts/create/', BankAccountCreateView.as_view(), name='bank-account-create'),
    path('admin-bank-accounts/<int:pk>/', BankAccountRetrieveView.as_view(), name='bank-account-detail'),
    path('admin-bank-accounts/<int:pk>/update/', BankAccountUpdateView.as_view(), name='bank-account-update'),
    path('admin-bank-accounts/<int:pk>/delete/', BankAccountDeleteView.as_view(), name='bank-account-delete'),

    path('all-order-booking-list/', AdminAllOrdersAPIView.as_view(), name='category-reorder'),

    path('admin-notifications/', AdminNotificationListView.as_view(), name='admin-notification-list'),
    path('admin-notifications/delete/', AdminNotificationDeleteView.as_view(), name='admin-notification-delete'),
    path('terms-conditions-create/', LegalDocumentCreateView.as_view(), name='category-reorder'),
    path('terms-conditions/get-list/', LegalDocumentDetailView.as_view(), name='category-reorder'),
    path('terms-conditions/<int:id>/update/', LegalDocumentUpdateView.as_view(), name='legal-document-update'),
    path('terms-conditions/<int:id>/delete/', LegalDocumentDeleteView.as_view(), name='legal-document-delete'),
    path('legal-documents/title-choices/', LegalDocumentTitleChoicesView.as_view(), name='legal-document-title-choices'),
    
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)