from django.contrib import admin
from django.db.models import Count
from .models import Booking, Bus, Route, Trip


# -------------------------------
# Bus Admin
# -------------------------------
@admin.register(Bus)
class BusAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "bus_number",
        "capacity",
        "type_of_bus",
        "is_available",
        "created_at",
    )
    search_fields = ("bus_number",)
    list_filter = ("type_of_bus", "is_available")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("id",)


# -------------------------------
# Route Admin
# -------------------------------
@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "route_name",
        "location_from",
        "location_to",
        "created_at",
    )
    search_fields = ("location_from", "location_to", "route_name")
    readonly_fields = ("route_name", "created_at", "updated_at")
    ordering = ("id",)


# -------------------------------
# Trip Admin (Optimized)
# -------------------------------
@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "route",
        "bus",
        "departure_time",
        "arrival_time",
        "price",
        "booked_seat_count",
        "remaining_seats",
        "is_active",
        "status",
    )

    list_filter = ("route", "bus", "is_active", "status")
    search_fields = ("route__route_name", "bus__bus_number")
    ordering = ("departure_time",)
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(booked_count=Count("bookings"))

    def booked_seat_count(self, obj):
        return obj.booked_count

    booked_seat_count.short_description = "Booked Seats"

    def remaining_seats(self, obj):
        return obj.bus.capacity - obj.booked_count

    remaining_seats.short_description = "Available Seats"


# -------------------------------
# Booking Admin
# -------------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "trip",
        "seat_number",
        "payment_status",
        "is_confirmed",
        "booking_time",
    )

    list_filter = ("is_confirmed", "payment_status", "trip")
    search_fields = ("user__username", "trip__route__route_name")
    ordering = ("id",)
    list_select_related = ("user", "trip")
    readonly_fields = ("booking_time", "created_at", "updated_at")
