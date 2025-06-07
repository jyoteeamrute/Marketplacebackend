from django.urls import path

from payment import views

from .views import *

urlpatterns = [
    # path('webhook/', views.stripe_webhook, name='stripe-webhook'),
    
    path("create-subscription-payment/", CreatePaymentIntentView.as_view(), name="create-payment-intent"),

    
    path("user-order-payment/", UserCardPaymentView.as_view(), name="User-order-payment"),
    path("verify-order-payment/", VerifyuserorderPaymentView.as_view(), name="confirm-payment-order"),
    # path("payment-history/", PaymentHistoryView.as_view(), name="payment-history"),
    
    
    path("stripe-webhook/", stripe_webhookssss, name="stripe-webhook"),

    
    
    path("confirm-payment/", ConfirmPaymentView.as_view(), name="confirm-payment"),
    path('add-card/', AddCardView.as_view(), name='add-card'),
    path('get-cards/', GetCardView.as_view(), name='get-cards'),
    path('update-card/<int:pk>/', UpdateCardView.as_view(), name='update-card'),
    path('advertisement-payments/<int:professional_id>/', AdvertisementPaymentDetailView.as_view(), name='advertisement-payment-detail'),
    path('advertisement-payments-list/', PaymentListView.as_view(), name='payment-list'),
    
    path("create-stripe-customer/", CreateStripeCustomerView.as_view(), name="create-stripe-customer"),
    path("attach-payment-method/", views.attach_payment_method, name="attach_payment_method"),
    
    path("user/order/create-stripe-customer/", CreateUserOrderStripeCustomerView.as_view(), name="create-stripe-customer"),
    # path("attach/user/order/payment-method/", views.attach_payment_method, name="attach_payment_method"),
    # path("order-payment/<str:order_id>/",PayOrderWithSavedCardView.as_view(),name="payment-user-order"),
    path('user/order/payment/', MakeOrderPaymentAPIView.as_view(), name='make-order-payment'),
    path('get-order-cards/', GetUserOrderCardAPIView.as_view(), name='get-cards'),


]



