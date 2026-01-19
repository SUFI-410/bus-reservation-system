from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from bus_app.models import Booking, Trip


def welcome_page(request):
    """
    Landing page. Shows system info and Login/Register buttons.
    Redirects logged-in users to trips page.
    """
    if request.user.is_authenticated:
        return redirect("trips-page")
    return render(request, "frontend/welcome.html")


@login_required
def trips_page(request):
    """
    Main Trips Listing Page
    Allows filtering by from/to cities
    Only future active trips shown
    """
    from_city = request.GET.get("from_city")
    to_city = request.GET.get("to_city")

    trips = Trip.objects.filter(
        is_active=True,
        departure_time__gte=timezone.now()
    )

    if from_city:
        trips = trips.filter(route__location_from=from_city)

    if to_city:
        trips = trips.filter(route__location_to=to_city)

    from_cities = Trip.objects.values_list("route__location_from", flat=True).distinct()
    to_cities = Trip.objects.values_list("route__location_to", flat=True).distinct()

    for trip in trips:
        trip.available_seats = trip.available_seats()

    context = {
        "trips": trips,
        "from_cities": from_cities,
        "to_cities": to_cities,
        "selected_from": from_city,
        "selected_to": to_city,
    }

    return render(request, "frontend/home.html", context)


def login_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            messages.error(request, "All fields are required")
            return render(request, "frontend/login.html")

        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect("trips-page")
        else:
            messages.error(request, "Invalid credentials")

    return render(request, "frontend/login.html")


def register_page(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        if not username or not password:
            messages.error(request, "All fields required")
        elif User.objects.filter(username=username).exists():
            messages.error(request, "Username already exists")
        else:
            User.objects.create_user(username=username, password=password)
            messages.success(request, "Account created successfully")
            return redirect("login")

    return render(request, "frontend/register.html")


@login_required
def logout_page(request):
    logout(request)
    return redirect("welcome-page")


@login_required
def booking_page(request, trip_id):
    """
    Seat booking page for a specific trip
    Prevent booking after departure
    """
    trip = get_object_or_404(Trip, id=trip_id)

    # ❗ Prevent booking after departure
    if trip.departure_time <= timezone.now():
        messages.error(request, "This trip has already departed. Booking closed.")
        return redirect("trips-page")

    booked_seats = trip.booked_seats()
    available_seats = trip.available_seats()

    if request.method == "POST":
        seat_number = request.POST.get("seat_number")

        if not seat_number:
            messages.error(request, "Please select a seat")
            return redirect("booking-page", trip_id=trip.id)  # noqa

        seat_number = int(seat_number)

        if seat_number not in available_seats:
            messages.error(request, f"Seat {seat_number} is already booked!")
            return redirect("booking-page", trip_id=trip.id)  # noqa

        booking = Booking.objects.create(
            user=request.user,
            trip=trip,
            seat_number=seat_number,
            is_confirmed=False,
            payment_status="pending",
        )

        messages.success(request, f"Seat {seat_number} reserved! Please complete payment.")
        return redirect("payment-page", booking_id=booking.id)  # noqa

    total_seats = trip.bus.capacity
    seats = [{"number": i, "booked": i in booked_seats} for i in range(1, total_seats + 1)]

    return render(request, "frontend/booking.html", {
        "trip": trip,
        "seats": seats
    })


@login_required
def payment_page(request, booking_id):
    """
    Fake payment page
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # ❗ Prevent paying for cancelled booking
    if booking.is_cancelled:
        messages.error(request, "This booking was cancelled.")
        return redirect("my-bookings-page")

    if request.method == "POST":
        booking.payment_status = "paid"
        booking.is_confirmed = True
        booking.save()
        messages.success(request, f"Payment successful! Seat {booking.seat_number} confirmed ✅")
        return redirect("my-bookings-page")

    return render(request, "frontend/payment.html", {
        "booking": booking
    })


@login_required
def my_bookings_page(request):
    bookings = (
        Booking.objects
        .filter(user=request.user)
        .select_related("trip", "trip__bus", "trip__route")
        .order_by("-created_at")
    )

    return render(request, "frontend/my_bookings.html", {
        "bookings": bookings,
        "now": timezone.now(),
    })


@login_required
def cancel_booking_page(request, booking_id):
    """
    Cancel booking + refund logic
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.is_cancelled:
        messages.info(request, "Booking already cancelled.")
        return redirect("my-bookings-page")

    booking.is_cancelled = True
    booking.is_confirmed = False

    # ✅ Refund logic (simple status)
    if booking.payment_status == "paid":
        booking.payment_status = "refunded"
        messages.success(request, "Booking cancelled. Refund will be processed.")
    else:
        booking.payment_status = "failed"
        messages.success(request, "Booking cancelled.")

    booking.save()
    return redirect("my-bookings-page")
