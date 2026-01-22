from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from datetime import timedelta
from bus_app.models import Booking, Trip
from bus_app.utils import filter_trips, sort_trips

# Hold time for pending bookings (before payment) in minutes
HOLD_TIME_MINUTES = 5


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
    trips = Trip.objects.filter(is_active=True, departure_time__gte=timezone.now())

    from_city = request.GET.get("from_city")
    to_city = request.GET.get("to_city")
    search = request.GET.get("search")
    sort = request.GET.get("sort")  # e.g., "price", "-departure_time"

    trips = filter_trips(trips, from_city, to_city, search)
    trips = sort_trips(trips, sort if sort else "departure_time")

    # calculate available seats
    for trip in trips:
        trip.available_seats = trip.available_seats()

    return render(request, "frontend/home.html", {
        "trips": trips,
        "from_cities": Trip.objects.values_list("route__location_from", flat=True).distinct(),
        "to_cities": Trip.objects.values_list("route__location_to", flat=True).distinct(),
        "selected_from": from_city,
        "selected_to": to_city,
        "selected_search": search,
        "selected_sort": sort,
    })


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
    Seat booking page for a specific trip.
    Implements temporary seat hold for pending bookings.
    """
    trip = get_object_or_404(Trip, id=trip_id)

    # ❗ Prevent booking after departure
    if trip.departure_time <= timezone.now():
        messages.error(request, "This trip has already departed. Booking closed.")
        return redirect("trips-page")

    # Release expired pending bookings
    Booking.objects.filter(
        trip=trip,
        is_confirmed=False,
        payment_status="pending",
        hold_expires_at__lt=timezone.now()
    ).delete()

    booked_seats = trip.booked_seats()
    available_seats = trip.available_seats()

    if request.method == "POST":
        seat_number = request.POST.get("seat_number")
        if not seat_number:
            messages.error(request, "Please select a seat")
            return redirect("booking-page", trip_id=trip.id)  # noqa

        seat_number = int(seat_number)

        if seat_number not in available_seats:
            messages.error(request, f"Seat {seat_number} is already booked or on hold!")
            return redirect("booking-page", trip_id=trip.id)  # noqa

        try:
            with transaction.atomic():
                # Lock seat to prevent race conditions
                booking = Booking.objects.create(
                    user=request.user,
                    trip=trip,
                    seat_number=seat_number,
                    is_confirmed=False,
                    payment_status="pending",
                    hold_expires_at=timezone.now() + timedelta(minutes=HOLD_TIME_MINUTES)
                )
        except Exception:  # noqa
            messages.error(request, f"Seat {seat_number} could not be reserved. Try again.")
            return redirect("booking-page", trip_id=trip.id)  # noqa

        messages.success(request,
                         f"Seat {seat_number} reserved! Please complete payment within {HOLD_TIME_MINUTES} minutes.")
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
        try:
            with transaction.atomic():
                booking.payment_status = "paid"
                booking.is_confirmed = True
                booking.hold_expires_at = None
                booking.save()
        except Exception as e:
            messages.error(request, f"Payment failed: {str(e)}")
            return redirect("payment-page", booking_id=booking.id)  # noqa

        messages.success(request, f"Payment successful! Seat {booking.seat_number} confirmed ✅")
        return redirect("my-bookings-page")

    return render(request, "frontend/payment.html", {
        "booking": booking
    })


@login_required
def my_bookings_page(request):
    q = request.GET.get("q")
    status = request.GET.get("status")
    sort_by = request.GET.get("sort", "-created_at")  # default: newest first

    bookings = Booking.objects.filter(user=request.user).select_related("trip", "trip__bus", "trip__route")

    if q:
        bookings = bookings.filter(
            Q(seat_number__icontains=q) |
            Q(trip__bus__bus_number__icontains=q) |
            Q(trip__route__route_name__icontains=q)
        )

    if status:
        if status == "confirmed":
            bookings = bookings.filter(is_confirmed=True, is_cancelled=False)
        elif status == "cancelled":
            bookings = bookings.filter(is_cancelled=True)

    bookings = bookings.order_by(sort_by)

    return render(request, "frontend/my_bookings.html", {
        "bookings": bookings,
        "now": timezone.now(),
    })


@login_required
def cancel_booking_page(request, booking_id):
    """
    Booking cancellation:
    - Marks booking as cancelled
    - Refunds payment if already paid
    - Atomic transaction for database safety
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    if booking.is_cancelled:
        messages.info(request, "This booking has already been cancelled.")
        return redirect("my-bookings-page")

    try:
        with transaction.atomic():
            booking.is_cancelled = True
            booking.is_confirmed = False

            if booking.payment_status == "paid":
                booking.payment_status = "refunded"
                messages.success(request,
                                 f"Booking for seat {booking.seat_number} has been cancelled. Refund will be processed.")
            else:
                messages.success(request, f"Booking for seat {booking.seat_number} has been cancelled.")

            booking.save()
    except Exception as e:
        messages.error(request, f"Failed to cancel booking: {str(e)}")
        return redirect("my-bookings-page")

    # ✅ Redirect to booking page so seats are recalculated
    return redirect("booking-page", trip_id=booking.trip.id)
