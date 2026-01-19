from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import Booking, Trip


# -------------------------------
# BOOKING SERVICES
# -------------------------------

@transaction.atomic
def create_booking(*, user, trip: Trip, seat_number: int) -> Booking:
    """
    Create a booking safely using DB transaction.
    """

    if not trip.is_active:
        raise ValidationError("This trip is not active.")

    if trip.status == "cancelled":
        raise ValidationError("This trip has been cancelled.")

    if trip.departure_time <= timezone.now():
        raise ValidationError("Cannot book a past trip.")

    booking = Booking(
        user=user,
        trip=trip,
        seat_number=seat_number,
        is_confirmed=True,
        payment_status="paid",
        is_cancelled=False,
    )

    booking.full_clean()
    booking.save()

    return booking


@transaction.atomic
def cancel_booking(*, booking: Booking, user) -> Booking:
    """
    Cancel a booking if rules allow.
    """

    if booking.user != user:
        raise ValidationError("You cannot cancel this booking.")

    if booking.is_cancelled:
        raise ValidationError("Booking is already cancelled.")

    if booking.trip.status == "completed":
        raise ValidationError("Completed trip bookings cannot be cancelled.")

    time_diff = booking.trip.departure_time - timezone.now()
    if time_diff.total_seconds() < 24 * 3600:
        raise ValidationError(
            "Booking can only be cancelled 24 hours before departure."
        )

    booking.is_cancelled = True
    booking.is_confirmed = False
    booking.payment_status = "failed"

    booking.save(update_fields=[
        "is_cancelled",
        "is_confirmed",
        "payment_status",
        "updated_at",
    ])

    return booking


# -------------------------------
# TRIP SERVICES
# -------------------------------

@transaction.atomic
def complete_trip(*, trip: Trip) -> Trip:
    """
    Mark a trip as completed.
    """
    if trip.status != "scheduled":
        raise ValidationError("Only scheduled trips can be completed.")

    trip.status = "completed"
    trip.is_active = False
    trip.save(update_fields=["status", "is_active", "updated_at"])

    return trip


@transaction.atomic
def cancel_trip(*, trip: Trip) -> Trip:
    """
    Cancel a trip and cancel all related bookings.
    """

    if trip.status == "cancelled":
        raise ValidationError("Trip is already cancelled.")

    trip.status = "cancelled"
    trip.is_active = False
    trip.save(update_fields=["status", "is_active", "updated_at"])

    trip.bookings.update(  # noqa
        is_cancelled=True,
        is_confirmed=False,
        payment_status="failed",
    )

    return trip
