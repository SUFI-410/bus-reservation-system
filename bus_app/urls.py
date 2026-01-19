from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    api_root,
    TripListAPIView,
    CreateBookingAPIView,
    MyBookingsAPIView,
    CancelBookingAPIView,
    RegisterAPIView,
    LoginAPIView,
    FakePaymentAPIView,
)

urlpatterns = [
    # API Root
    path("", api_root, name="api-root"),

    # Auth
    path("register/", RegisterAPIView.as_view(), name="api-register"),
    path("login/", LoginAPIView.as_view(), name="api-login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),

    # Trips
    path("trips/", TripListAPIView.as_view(), name="api-trips"),

    # Bookings
    path("book/", CreateBookingAPIView.as_view(), name="api-book"),
    path("bookings/", MyBookingsAPIView.as_view(), name="api-my-bookings"),
    path(
        "bookings/<int:booking_id>/cancel/",
        CancelBookingAPIView.as_view(),
        name="api-cancel-booking",
    ),

    # Payments (Fake)
    path(
        "bookings/<int:booking_id>/pay/",
        FakePaymentAPIView.as_view(),
        name="api-fake-payment",
    ),
]
