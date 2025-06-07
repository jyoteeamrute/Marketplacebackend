from django.urls import path

from UserApp.booking import *
from UserApp.cart import *
from UserApp.categorydetails import *
from UserApp.searchtab import *
from UserApp.userprofile import *
from UserApp.views import *

urlpatterns = [
    path('register/', UserRegistrationAPIView.as_view(), name='user-register'),
    path('create-adminuser-prouser/', UserCreateAPIView.as_view(), name='create-user'),
    path('login/', LoginView.as_view(), name='user-login'),
    path('logout/', LogoutView.as_view(), name='user-logout'),
    path('use-refresh-token/', RefreshProfessionalUserAccessTokenView.as_view(), name='user-refresh-token'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify-otp'),
    path('get-automatic-address/', GetAutomaticAddress.as_view(), name='get-automatic-address'),
    path('get-user-profile/', GetUserProfileView.as_view(), name='all-users'),
    path('delete-user/', DeleteUserView.as_view(), name='delete-user'),
    path("send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("verify-user-otp/", VerifyUserOTPView.as_view(), name="verify-User-otp"),
    path('update-profile/', UserProfileUpdateView.as_view(), name='update-profile'),
    path('api/v1/users/profile/<int:user_id>-<str:username>/', PublicUserProfileView.as_view(), name='public-user-profile'),
    path("resend-otp/", ResendOTPView.as_view(), name="resend-otp"),
    path("forgot-password/", ForgetPasswordView.as_view(), name="forgot-password"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"), 
    path("update-password/", UpdatePasswordView.as_view(), name="reset-password"),    
    path("check-email/",CheckEmailAvailabilityView.as_view(), name="check-email-avail"),
    path("check-username/",CheckUsernameAvailabilityView.as_view(), name="check-username-avail"),


    #----------------------company-details-------------------------------------------------------------
    path('company-labels/<int:company_id>/', CompanyLabelsByCategoryView.as_view(), name='company-labels'),
    path('company/items-by-service/<int:company_id>/', CompanyItemsByServiceKeyView.as_view(), name='company-items-by-service'),
    path("company/<int:company_id>/media/", CompanyMediaView.as_view(), name="company-media"),
    path("company/<int:company_id>/event/", CompanyEventView.as_view(), name="company-event"),
    path('company/event/<int:event_id>/', StoreEventDetailViewNew.as_view(), name='store-event-detail'),
    path('company/<int:company_id>/products-services/', CompanyProductsAndServicesView.as_view(), name='company-products-services'),
    path('company/<int:company_id>/products-services-news/', CompanyProductsAndServicesViewsnewsss.as_view(), name='company-products-services-new'),
    path('company/<int:company_id>/products-services-new/', CompanyProductsAndServicesViews.as_view(), name='company-products-services-new'),
    path('company/<int:company_id>/feedback/', CompanyFeedbackAPIView.as_view(), name='company-feedback'),
    path('company/<int:company_id>/details/', CompanyDetailsAPIView.as_view(), name='company-details'),
    path('company/<int:company_id>/follow-toggle/', ToggleFollowCompanyView.as_view(), name='toggle-follow-company'),
    path('company-about-user/<int:company_id>/', GetCompanyAboutsByUserView.as_view(), name='company-details-user'),
    path("orders/fulfilled/<str:order_id>/", FulfilledOrderDetailView.as_view(), name="fulfilled-order-detail"),
    path('advertisements/random/', RandomAdvertisementView.as_view(), name='random_advertisement'),
    path('advertisements/count/<int:ad_id>/', AdvertisementClickAPIView.as_view(), name='advertisement-click'),
    path("product/review/", ReviewCreateAPIView.as_view(), name="product-review"),
    path('reviews/<int:review_id>/', ReviewDetailView.as_view(), name='review_detail'),
    path('reviews/', ReviewListView.as_view(), name='review_list'),






    #-----------------------------------------add to cart-----------------------------------
    path('cart/my-carts/', MyCartGroupedAPIView.as_view()),
    path('cart/update-meta/<company_id>/<str:order_type>/', UpdateCartMetaAPIView.as_view(), name='update-cart-meta'),
    path('cart/company/<int:company_id>/', CompanyCartDetailAPIView.as_view()),
    path('cart/add/', AddToCartAPIView.as_view(), name='add_to_cart'),
    path('order/create/<company_id>/<int:order_type>/', CreateOrderAPIView.as_view(), name='create_order'),
    path('promocodes/<int:company_id>/', PromoCodeListView.as_view(), name='promocode-list'),
    path('orders/', UserOrdersAPIView.as_view(), name='user-orders'),
    path('orders-new/', UserOrdersAPIViewNew.as_view(), name='user-orders'),
    path('add-new-address/', AddNewAddressAPIView.as_view(), name='add_new_address'),
    path('address/list/', GetUserAddressesAPIView.as_view(), name='list-address'),
    path('address/update/<int:address_id>/', EditUserAddressAPIView.as_view(), name='update-address'),
    path('address/delete/<int:address_id>/', DeleteUserAddressAPIView.as_view(), name='delete_user_address'),
    path('order-detail/<int:company_id>/', OrderDetailView.as_view(), name='order-detail'),
   
    #-----------------------------------------search-Tab-----------------------------------
    path('verification-status/', UserVerificationStatusView.as_view(), name='verification-status'),
    path('search-tab/', SearchView.as_view(), name='search'),
    path('product-tab/', ProductSearchView.as_view(), name='Product-Search'),
    path('product-list/', ProductListByKeyAndCategoryView.as_view(), name='Product-List'),
    path('search/label-based-products/', LabelBasedProductSearchView.as_view(), name='label-product-search'),
    path('products/subcategory/<int:id>/', SubCategoryProductListView.as_view(), name='products-by-subcategory-id'),
    path('api/nearby-details/', RestaurantDetailsView.as_view(), name='restaurant-details'),
    path('filter-by-label/', FilterByLabelView.as_view(), name='filter-by-label'),
    path('product/<int:product_id>/', ProductDetailAPIView.as_view(), name='product-detail'),
    path('onsite-booking-options/<int:company_id>/', OnsiteBookingOptionsAPIView.as_view(), name='onsite-booking-options'),
    path('home-tab/', HomeTabView.as_view(), name='home-tab'),
    path("api/mention-suggestions/", MentionSuggestionAPIView.as_view()),






    #---------------------------------support and feedback-------------------------------------
    path('feedback/', FeedbackView.as_view(), name='feedback'),
    path('invoice/<str:order_id>/', render_invoice_view, name='order-invoice'),
    path('support/options/', SupportOptionListView.as_view(), name='support-options'),
    path('support/create/', CreateSupportRequestView.as_view(), name='create-support'),
    #-----------------------------------------reel-----------------------------------------
    path('get-company-reels/<int:company_id>/', CompanyReelsView.as_view(), name='get_all_reels'),
    path('get_reel_folder/', ReelFolderListAPIView.as_view(), name='get_reel_folder'),
    path('reelfolder/<int:pk>/delete/', ReelFolderDeleteView.as_view(), name='reelfolder-delete'),
    path('reelfolder/<int:pk>/update/', ReelFolderUpdateView.as_view(), name='reelfolder-update'),
    path('users-list/', UserListAPIView.as_view(), name='user-list'),
    path('get-company-details/', FilterCompanyReelsAPIView.as_view(), name='get-restaurant-details'),
    path('get-saved-reels/',GetSavedLikedReelsAPIView.as_view(), name='get-saved-reels'),
    path('report-reel/', CreateReelReportView.as_view(), name='report-reel'),
    path('my-reel-reports/', ListUserReelReportsView.as_view(), name='my-reel-reports'),
    path('report-reasons/', GetReportReasonsView.as_view(), name='report-reasons'),


    #---------------------------------------------friend and  follow-----------------------------------
    path("friends/request/send/", send_friend_and_follow_request, name="send_friend_and_follow_request"),
    path("update/friends/", update_friend_request, name="update_friend_request"),
    path("friends/request/respond/", respond_to_request, name="respond_to_request"),
    path("received/friend-request/list/", pending_list_requests, name="ist-reacived-friend-requests"),
    path("followers/list/", list_followers, name="list_followers"),
    path("following/list/", list_following, name="list_following"),
    path("my/all-friends/count/", friends_list, name="friends_list"),
    path("send/friend/request/status/",all_friends_status_list,name="friends_status_list"),
    path('search/friends/', SearchUsersView.as_view(), name='search-users'),
    path("unfollow/company/", unfollow_professional_users, name="unfolow-comapnay"),
    path('get-users-profile-by-barcode/<str:username>/', GetUserProfileByBarcodeView.as_view(), name='follow-single-user-by-barcode'),
    path("suggested-friends/", SuggestedFriendsByCompany.as_view(), name="suggested-friend"),
    path('user-followers/', FollowersListView.as_view(), name='followers-list'),
    path('user-following/', FollowingListView.as_view(), name='following-list'),
    path('user-followers-following/', FriendshipListView.as_view(), name='followers-following-list'),
    path("mentionable-users-list/", MentionableEntitiesAPIView.as_view(), name="mentionable-users"),

    # <-----------------------------------------room booking----------------------------------------
    path('room-availability/', RoomAvailabilityView.as_view(), name='room-availability'),
    path('cruise-rooms/availability/', CruiseRoomAvailabilityView.as_view(), name='cruise-room-availability'),
    path('cruise-rooms/book/', CruiseRoomBookingView.as_view(), name='cruise-room-book'),
    path('hotel-rooms/book/', BookRoomAPIView.as_view(), name='hotel-room-book'),
    path('vailidate-room/',ValidateProductBookingView.as_view(), name='validate-room-book'),
    path('Unavailable-room/',GetUnavailableDatesView.as_view(), name='Unavailable-room'),
    

    #-------------------------------------------for support ticket for user ----------------------------------
    path('support-tickets/create/', CreateSupportTicketView.as_view(), name='create-support-ticket'),
    path('support-tickets/', UserSupportTicketListView.as_view(), name='user-support-ticket-list'),
    path('support-tickets/<int:pk>/', UserSupportTicketDetailView.as_view(), name='user-support-ticket-detail'),
    path('support-tickets/<int:pk>/update/', UpdateSupportTicketView.as_view(), name='update-support-ticket'),
    path('ticket/categories-choices/', TicketCategoryChoicesView.as_view(), name='ticket-category-choices'),
    

    #-----------------------details by  subcategory-------------------------------------------------------
    path('cruise-products/<int:product_id>/', cruiseDetailView.as_view(), name='cruise-detail'),
    path('hotel-products/<int:product_id>/', hotelDetailView.as_view(), name='hotel-detail'),
    path('music-products/<int:product_id>/', MusicDetailView.as_view(), name='musicproduct-detail'),
    path('nightclubs-products/<int:product_id>/', nightclubsDetailView.as_view(), name='nightclubs-detail'),
    path('experience-products/<int:product_id>/', experienceDetailView.as_view(), name='experience-detail'),
    path('eventworkshop-products/<int:product_id>/', eventDetailView.as_view(), name='events-detail'),
    path('sportsandnauticalactivity-products/<int:product_id>/', sportsDetailView.as_view(), name='sports-detail'),
    path('guidedandpersonalized-products/<int:product_id>/', guidedDetailView.as_view(), name='guided-detail'),
    path('aesthetics-products/<int:product_id>/', aestheticsDetailView.as_view(), name='aesthetics-detail'),
    path('relaxation-products/<int:product_id>/', relaxationDetailView.as_view(), name='relaxation-detail'),
    path('artandculture-products/<int:product_id>/', artandcultureDetailView.as_view(), name='relaxation-detail'),
    path('cruise-rooms/', CruiseRoomListView.as_view(), name='cruise-room-list'),
    
    
     
    #----------------------------------slots-Availability-----------------------------
    path('available-slots/', AvailableSlotsAPIView.as_view()),
    path('availableaesthetics-slots/', AvailableAestheticsSlotAPIView.as_view()),
    path('availablerelaxation-slots/', AvailableRelaxaionSlotsAPIView.as_view()),
    path('availableartandculture-slots/', AvailableArtandcultureSlotsAPIView.as_view()),

    
    #---------------------------------bookslots------------------------------------
    path('book-slot/', BookexperiencecreateAPIView.as_view()),
    path('book-Aestheticslot/', AestheticscreateAPIView.as_view()),
    path('book-Relaxationslot/', RelaxationcreateAPIView.as_view()),
    path('book-Artandcultureslot/', ArtandculturecreateAPIView.as_view()),
    path('eventandworkshopBooking/create/', eventandworkshopBookingCreateAPIView.as_view(), name='eventandworkshop-detail'),
    path('musicbooking/create/', MusicBookingCreateAPIView.as_view(), name='music-booking'),
    path('experiencebooking/create/', EventBookingCreateAPIView.as_view(), name='create-booking'),


    # ------------------------------------------loyalty-card-------------------------------------
    path('loyalty/cards/<int:company_id>/', LoyaltyCardProductListView.as_view(), name='loyalty-company'),
    path('loyalty/purchase/', LoyaltyPurchaseAPIView.as_view(), name='loyalty-purchase'),
    path('loyalty-points/', LoyaltyPointListView.as_view(), name='loyalty-points'),
    

   
    #----------------------------------------help-support------------------------------------
    path('get-privacy-settings/', GetPrivacySettingView.as_view(), name='get_privacy_settings'),
    path('update-privacy-settings/', UpdatePrivacySettingView.as_view(), name='update_privacy_settings'),
    path('help-support/', HelpAndSupport.as_view(), name='help-center'),
    
 

    #-----------------------order-tracking-----------------------------------------------------
    path("order/tracking/<str:order_id>/", OrderTrackingView.as_view(), name="order-tracking"),
    path('get-order/tracking/', UserOrderTrackingView.as_view(), name='order-tracking'),
    path('orders-list/', UserOrderListView.as_view(), name='user-order-list'),
    path('orders/<str:order_id>/', UserOrderDetailView.as_view(), name='user-order-detail'),
    

    
    #---------------------------------order-cancel---------------------------------------
    path('order/cancel-reasons/', CancelReasonsAPIView.as_view(), name='cancel-reasons-list'),
    path('orders/cancel/<str:identifier>/', CancelOrderBookingsAPIView.as_view(), name='order-cancel'),       
    path('orders/feedback/<str:identifier>/', OrderFeedBackAPIView.as_view(), name='order-feedback'),   

    #----------------------------------------one-signal------------------------------------------
    path('store-onesignal-player-id/', StorePlayerIdView.as_view(), name='save-player-id'),


]
