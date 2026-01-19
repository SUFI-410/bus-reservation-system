from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


# -------------------------------
# Bus Model
# -------------------------------
class Bus(models.Model):
    bus_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveIntegerField()
    type_of_bus = models.CharField(max_length=50)
    is_available = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.bus_number} ({self.type_of_bus})"

    class Meta:
        verbose_name = "Bus"
        verbose_name_plural = "Buses"


# -------------------------------
# Route Model
# -------------------------------
class Route(models.Model):
    location_from = models.CharField(max_length=100)
    location_to = models.CharField(max_length=100)
    route_name = models.CharField(max_length=150, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.route_name = f"{self.location_from} → {self.location_to}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.route_name

    class Meta:
        unique_together = ("location_from", "location_to")
        verbose_name = "Route"
        verbose_name_plural = "Routes"


# -------------------------------
# Trip Model
# -------------------------------
class Trip(models.Model):
    bus = models.ForeignKey(Bus, on_delete=models.CASCADE, related_name="trips")
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="trips")

    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    price = models.DecimalField(max_digits=8, decimal_places=2)

    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("scheduled", "Scheduled"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="scheduled",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        if self.arrival_time <= self.departure_time:
            raise ValidationError("Arrival time must be after departure time.")

        if self.departure_time < timezone.now():
            raise ValidationError("Departure time cannot be in the past.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def booked_seats(self):
        return list(self.bookings.values_list("seat_number", flat=True))  # noqa

    def available_seats(self):
        booked = set(self.booked_seats())
        return [
            seat for seat in range(1, self.bus.capacity + 1)
            if seat not in booked
        ]

    def __str__(self):
        return f"{self.route.route_name} | {self.departure_time:%Y-%m-%d %H:%M}"

    class Meta:
        ordering = ["departure_time"]
        verbose_name = "Trip"
        verbose_name_plural = "Trips"


# -------------------------------
# Booking Model
# -------------------------------
class Booking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bookings")
    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="bookings")

    seat_number = models.PositiveIntegerField()

    is_confirmed = models.BooleanField(default=False)
    is_cancelled = models.BooleanField(default=False)

    payment_status = models.CharField(
        max_length=20,
        choices=[
            ("pending", "Pending"),
            ("paid", "Paid"),
            ("failed", "Failed"),
        ],
        default="pending",
    )

    booking_time = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Cannot book cancelled trip
        if self.trip.status == "cancelled":
            raise ValidationError("This trip has been cancelled.")

        # Seat capacity validation
        if self.seat_number > self.trip.bus.capacity:
            raise ValidationError("Seat number exceeds bus capacity.")

        # Prevent duplicate seat booking
        if (
                Booking.objects
                        .filter(trip=self.trip, seat_number=self.seat_number)
                        .exclude(pk=self.pk)
                        .exists()
        ):
            raise ValidationError("This seat is already booked for this trip.")

        # Prevent overbooking
        if Booking.objects.filter(trip=self.trip).count() >= self.trip.bus.capacity:
            raise ValidationError("This trip is fully booked.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Seat {self.seat_number} | {self.user.username} | {self.trip}"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["trip", "seat_number"],
                name="unique_seat_per_trip"
            )
        ]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
