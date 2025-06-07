from django.urls import path 
from .views import *
from django.conf.urls.static import static
from ProfessionalUser.orders import *
from ProfessionalUser.marketing import *
from ProfessionalUser.loyaltyCard import *

urlpatterns = [
    
    path('register/', ProfessionalUserSignupView.as_view(), name='professional-user-register'),
    path('login/', ProfessionalUserLoginView.as_view(), name='professional-user-login'),
    path('document-status/', DocumentVerificationStatusView.as_view(), name='document-status'),
    path('logout/', LogoutAPIView.as_view(), name='reset-password'),
    path('profile/', ProfessionalUserProfileView.as_view(), name='professional-user-profile'),
    path('forgot-password/', ForgotPasswordAPIView.as_view(), name='forgot-password'),
    path('reset-password/', ResetPasswordAPIView.as_view(), name='reset-password'),
    path('update-password/', UpdatePasswordAPIView.as_view(), name='reset-password'),
    path('company-details/',CompanyDetailsView.as_view(), name='company-details-create'),
    path('get_address/', GetAddressView.as_view(), name='get_address-api'),
    path('update/', UpdateProfessionalUserView.as_view(), name="update-user"),
    path('prof-refresh-token/', RefreshProfessionalUserAccessTokenView.as_view(), name='refresh-token-professional'),
    
    path('company-update-details/', UpdateCompanyDetailsAPI.as_view(), name='update_company'),
    path("company-delete-images/", CompanyImageDeleteView.as_view(), name="delete-company-images"),
    path('company-coverphoto-update/', UpdateCoverPhotoAPI.as_view(), name='upload-coverphoto'),
    
    path('reels-upload/', StoreReelCreateAPIView.as_view(), name='upload-reel'),
    path('reels-title-update/', StoreReelUpdateTitleAPIView.as_view(), name='upload-title'),
    path('reel-like/', ReelLikeToggleAPIView.as_view(), name= 'reel-like'),
    path("reels-view/<int:reel_id>/", ReelViewAPI.as_view(), name="reel-view"),
    path('like-comment/', LikeCommentAPIView.as_view(), name='like_comment'),
    path('comments-reel/',ReelCommentCreateAPIView.as_view(), name='comments-reel'),
    path('get-comments-reel/<int:reel_id>/', ReelCommentListAPIView.as_view(), name='get-comments-reel'),
    path('reels-comments-delete/<int:comment_id>/', ReelCommentDeleteAPIView.as_view(), name='delete_comment'),
    path('share-reel/',ReelShareCreateAPIView.as_view(),name='share-reel'),
    path('get-store-reels/<int:company_id>/', GetStoreReelAPIView.as_view(), name='get-store-reels'),
    path('store-reels-delete/<int:pk>/', StoreReelDeleteAPIView.as_view(), name='store-reel-delete'),
    path('reels/folder/<int:folder_id>/', ReelFolderDetailAPIView.as_view(), name='reel-folder-detail'), 
    
    path('upload-store-images/', StoreImageUploadAPIView.as_view(), name='upload-store-images'),
    path('store-images-delete/<int:pk>/', StoreImageDeleteAPIView.as_view(), name='store-image-delete'),

    path('store-add-event/', AddEventAPIView.as_view(), name='store-add-event'),
    path('store-get-events/', GetEventsAPIView.as_view(), name='get-events'),  # Get all events
    path('store-get-events/<int:event_id>/', GetEventsAPIView.as_view(), name='event-detail'), 
    path('store-event-update/', EventsUpdateAPIView.as_view(), name='update-event'),
    path('store-deleteEvent/<int:event_id>/', DeleteEventAPIView.as_view(), name='delete-event'),
    path('update-image/', StoreImageUpdateTitleAPIView.as_view(), name='update-image'),
    path('get-store-media/', GetStoreMediaAPIView.as_view(), name='get-store-media'),
    path('get-store-media-category/', GetStoreMediaCategoryAPIView.as_view(), name='get-store-media-by-company'),
    
    path('get-count-all-orders/',GetCountAllUserOrdersAPIView.as_view(), name='get-count-all-orders'),
    path('get-all-users-orders/', GetAllUserOrdersAPIView.as_view(), name='get-all-orders'),
    path('order-update-details/', OrderUpdateAPIView.as_view(), name='order-update-details'),
    path('unique-get-order/', GetUniqueUserOrdersAPIView.as_view(), name='unique-order-id'),
    path('order-booking-icons/create/', OrderBookingIconsCreateView.as_view(), name='order-booking-icons-create'),

    
    


    path('bookings/', UnifiedBookingListView.as_view(), name='bookings'),

    path('update-booking-status/', UpdateBookingStatusAPIView.as_view(), name='update-bookings'),

    

    path('verify_email/', VerifyEmailView.as_view(), name='verify-email-api'),
    path('send-otp/', SendOTPView.as_view(), name='send-otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name="verify-otp"),
    path('resend-otp/', ResendOTPView.as_view(), name="resend-otp"),
    
    path('get-invoices-list/', GetInvoiceListView.as_view(), name='get-invoice-list'),
    path('get-invoices-list/<int:id>/', GetInvoiceListView.as_view(), name='get-invoice-detail'),
    path('update-invoices-list/', UpdateInvoiceListView.as_view(), name='update-invoices-details'),
    path('delete-invoices-list/<int:id>/', DeleteInvoiceListView.as_view(), name='delete-invoices-details'),
 
    #------------------------------product------------------------------
 
    path('create-products/', CreateProductAPIView.as_view(), name='product-list-create'),
    path('get/products/', CompanyProductListAPIView.as_view(), name='product-detail'),
    path('get/products/<int:id>/', CompanyProductDetailAPIViewss.as_view(), name='product-all-detail'),
    path("update/products/<int:id>/", UpdateProductAPIView.as_view(), name="update-product"), 
    path("delete/products/<int:id>/", DeleteProductAPIView.as_view(), name="delete-product"),
    path('get-categorywise-products/', CategoryProductListAPIView.as_view(), name='get-category-wise-products'),
    path('create-product-folder',CreateCategoryFolderAPIView.as_view(), name='create-product-folder'),
    path('get-folderwise-product/',GetProductsByFolderNameAPIView.as_view(), name='get-product-folder'),
    path('get-without-folder-product/',GetWithoutFolderProductListAPIView.as_view(), name='get-without-product-folder'),
    path('get-all-product-folder/',GetAllFoldersWithProductCountAPIView.as_view(), name='get-all-product-folder'),
    path('update-product-folder/<int:folder_id>/',UpdateCategoryFolderAPIView.as_view(), name='update-product-folder'),
    path('delete-tickets-product/',DeleteTicketAPIView.as_view(), name='delete-product-folder'),
    #------------------------------campaign------------------------------
    
    path('campaigns/', UserCampaignListAPIView.as_view(), name='user-campaigns'),
    path('campaigns/create/', CreateCampaignAPIView.as_view(), name='create-campaign'),
    path('campaigns/<int:pk>/', RetrieveCampaignAPIView.as_view(), name='retrieve-campaign'),
    path('campaigns/update/<int:pk>/', UpdateCampaignAPIView.as_view(), name='update-campaign'),
    path('campaigns/delete/<int:pk>/', DeleteCampaignAPIView.as_view(), name='delete-campaign'),

    #------------------------------promotion------------------------------
    path('promotion/', UserPromotionListAPIView.as_view(), name='user-promotion'),
    path('promotion/create/', CreatePromotionsAPIView.as_view(), name='create-promotion'),
    path('promotion/<int:pk>/', RetrievePromotionAPIView.as_view(), name='retrieve-promotion'),
    path('promotion/update/<int:pk>/', UpdatePromotionAPIView.as_view(), name='update-promotion'),
    path('promotion/delete/<int:pk>/', DeletePromotionAPIView.as_view(), name='delete-promotion'),

    #------------------------------promocode------------------------------
    path('promocode/', UserPromocodeListAPIView.as_view(), name='user-promocode'),
    path('promocode/create/', CreatePromocodeAPIView.as_view(), name='create-promocode'),
    path('promocode/update/<int:promocode_id>/', UpdatePromocodeAPIView.as_view(), name='update-promocode'),
    path('promocode/delete/<int:promocode_id>/', DeletePromocodeAPIView.as_view(), name='delete-promocode'),
    path('check-unique-promocode/', CheckPromocodeAvailabilityAPIView.as_view(), name='check-unique-promocode'),


    #------------------------------inventory------------------------------
    path("update-inventory/", UpdateInventoryView.as_view(), name="update-inventory-details"),
    path("delete-inventory/",DeleteInventoryView.as_view(),name="delete-inventory-details"),
    path("get-inventory-details/",GetInventoryView.as_view(), name="get-inventory-details"),
    path('create-delivery-charges/',CreateDeliveryServiceAPIView.as_view(), name='create-delivery-charges'),
    path('update-delivery-charges/',UpdateDeliveryServiceAPIView.as_view(), name='update-delivery-charges'),
    path('get-delivery-charges/',GetDeliveryServiceAPIView.as_view(), name='get-delivery-charges'),
    
    #review
    path('review/respond/<int:review_id>/', RespondToReviewView.as_view(), name='respond_to_review'),
    

    path('all-reviews/users/', ReviewersListView.as_view(), name='reviewers-users-list'),

    # company review
    # path('company/<int:id>/', CompanyDetailsreviewView.as_view(), name='company-details'),
    path('company/review/', CompanyReviewCreateView.as_view(), name='create-company-review'),
    path('company-review-list/',AllReviewListView.as_view(), name='company-review-list'),
    
    path('folder/create/', LocalFolderCreateAPIView.as_view(), name='create_folder'),

    #performance metrics
    path('performance-metrics/', PerformanceMetricsView.as_view(), name='performance-metrics'),
    path('order-performance/', OrderPerformanceView.as_view(), name='order-performance'),
    path('review-performance/', RevenuePerformanceView.as_view(), name='order-performance'),
    path('order-chart/', OrderChartView.as_view(), name='order-chart'),

    path('dashboard-list/', DashboardIncomeSummaryView.as_view(), name='dashboard-list'),

    #------------------------------marketing------------------------------
    path('marketing-create-campaign/',AdvertiseCampaignCreateAPIView.as_view(),name='create-campaign'),
    path('marketing-update-campaign/<int:campaign_id>/',UpdateAdvertiseCampaignAPIView.as_view(),name='update-campaign'),
    path('marketing-get-campaign/',AdvertiseCampaignListAPIView.as_view(),name='get-campaign'),
    path('marketing-impression-ad/',AdImpressionAPIView.as_view(),name='impression-ad'),
    path('marketing-costperclick-ad/',AdClickAPIView.as_view(),name='click-ad'),
    path('marketing-delete-campaign/<int:campaign_id>/', DeleteAdvertiseCampaignAPIView.as_view(), name='delete-campaign'),
    
    # #accounting-data
    path('accounting-recent-transactions/',ProfessionalUserTransactionView.as_view(), name ='recent-transactions'),
    path('accounting-export-data/',ExportDataAPIView.as_view(), name='export-data'),
    path('accounting-invoice/', GenerateInvoiceAPIView.as_view(), name='generate-invoice'),


    path('marketing-advertising-dashboard/', AdvertisingDashboardAPIView.as_view(), name='advertising-dashboard'),
    path('marketing/performance-insights/', CampaignPerformanceInsightsAPIView.as_view(), name='campaign-performance-insights'),

    path('offers/create/', CreateOfferAPIView.as_view(), name='create-offer'),
    path('offers/list/', OfferListAPIView.as_view(), name='list-offers'),
    path('offers/<int:offer_id>/update/', UpdateOfferAPIView.as_view(), name='update_offer'),
    path('offers/<int:offer_id>/delete/', DeleteOfferAPIView.as_view(), name='delete_offer'),
    
    #------------------------------employee------------------------------
    path('employees/', EmployeeListView.as_view(), name='employee-list'),
    path('employees/create/', EmployeeCreateView.as_view(), name='employee-create'),
    path('employees/update/<int:pk>/', UpdateEmployeeLastNameView.as_view(), name='employee-update-detail'),
    path('employee/delete/<int:pk>/', EmployeeDeleteByIdView.as_view(), name='employee-delete'),
    path('employees/<int:pk>/', EmployeeDetailView.as_view(), name='employee-detail'),
    
    path('feedback-pro/',FeedbackProfessionalUser.as_view(),name='feedbackProfessionaluser'),

    path('suppot-tickets/create-profuser/', CreateSupportTicketView.as_view(), name='create-ticket'),
    path('support-tickets/profuser-list/', SellerTicketListAPIView.as_view(), name='seller-ticket-list'),
    path('support-tickets/specific-orders/', MySpecificOrderTicketsView.as_view(), name='my_specific_order_tickets'),


    path('reel-notifications/', NotificationListView.as_view(), name='notification-list'),
    path('delete-reel-notifications/', NotificationDeleteView.as_view(), name='delete-notifications'),
    path('preview-subscription-change/', PreviewSubscriptionChangeView.as_view(),name='select-subscription'),
    path('preview-categories-update/<plan_id>/', GetCategorySelectionLimitsAPIView.as_view(),name='select-category'),

    path('cruise-facilities/', CruiseFacilityListView.as_view(), name='cruise-facility-list'),
    path('cruise-facilities/create/', CruiseFacilityCreateView.as_view(), name='cruise-facility-create'),
    path('cruise-facilities/bulk-create/', FacilityBulkCreateView.as_view(), name='cruise-facility-bulk-create'),
    path('cruise/room-types/', RoomTypeListAPIView.as_view(), name='room-type-list'),
    path('room-facilities-list/', RoomFacilityListView.as_view(), name='room-facility-list'),
    
    #-------------------------------loyalty-card------------------------------
    
    path('loyalty-card-create/', CreateLoyaltyCardView.as_view(), name='create-loyalty-card'),
    path('loyalty-card-list/', GetLoyaltyCardView.as_view(), name='loyalty-card-list'),
    path('loyalty-card-update/<int:pk>/', UpdateLoyaltyCardView.as_view(), name='loyalty-card-update'),
    path('loyalty-card-delete/<int:pk>/', DeleteLoyaltyCardView.as_view(), name='loyalty-card-delete'),
    path('get/subscription/list/', GetSubscriptionListView.as_view(), name='get-subscription-list'),
    path('professional-user/delete/', SoftDeleteProfessionalUserView.as_view(), name='soft-delete-professional-user'),
]



urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
