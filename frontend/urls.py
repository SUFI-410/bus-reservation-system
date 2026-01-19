from django.urls import path
from . import views

urlpatterns = [
    path("", views.welcome_page, name="welcome-page"),
    path("trips/", views.trips_page, name="trips-page"),
    path("login/", views.login_page, name="login"),
    path("register/", views.register_page, name="register"),
    path("logout/", views.logout_page, name="logout"),
    path("booking/<int:trip_id>/", views.booking_page, name="booking-page"),
    path("payment/<int:booking_id>/", views.payment_page, name="payment-page"),
    path("booking/<int:booking_id>/cancel/", views.cancel_booking_page, name="cancel-booking-page"),
    path("my-bookings/", views.my_bookings_page, name="my-bookings-page"),
]
