from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Booking, Trip


# ----------------------------
# TRIP SERIALIZER
# ----------------------------
class TripSerializer(serializers.ModelSerializer):
    available_seats = serializers.SerializerMethodField()
    route_name = serializers.CharField(
        source="route.route_name",
        read_only=True
    )
    bus_number = serializers.CharField(
        source="bus.bus_number",
        read_only=True
    )

    class Meta:
        model = Trip
        fields = [
            "id",
            "bus_number",
            "route_name",
            "departure_time",
            "arrival_time",
            "price",
            "available_seats",
            "is_active",
        ]

    def get_available_seats(self, obj):  # noqa
        return obj.available_seats()


# ----------------------------
# BOOKING SERIALIZER
# ----------------------------
class BookingSerializer(serializers.ModelSerializer):
    trip_detail = TripSerializer(
        source="trip",
        read_only=True
    )

    class Meta:
        model = Booking
        fields = [
            "id",
            "trip",
            "trip_detail",
            "seat_number",
            "is_confirmed",
        ]
        read_only_fields = ["is_confirmed"]

    def validate(self, data):
        """
        Prevent double booking of the same seat
        """
        trip = data.get("trip")
        seat_number = data.get("seat_number")

        if Booking.objects.filter(
                trip=trip,
                seat_number=seat_number
        ).exists():
            raise serializers.ValidationError(
                {"seat_number": "This seat is already booked."}
            )

        return data

    def create(self, validated_data):
        """
        Attach authenticated user to booking
        """
        request = self.context.get("request")

        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError(
                "Authentication required to create booking."
            )

        return Booking.objects.create(
            user=request.user,
            is_confirmed=True,
            **validated_data
        )


# ----------------------------
# REGISTER SERIALIZER
# ----------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=6
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
        ]

    def validate_username(self, value):  # noqa
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "Username already exists."
            )
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data.get("email"),
            password=validated_data["password"],
        )
        return user


# ----------------------------
# LOGIN SERIALIZER
# ----------------------------
class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(
        write_only=True
    )

    def validate(self, data):
        user = authenticate(
            username=data.get("username"),
            password=data.get("password")
        )

        if not user:
            raise serializers.ValidationError(
                "Invalid username or password."
            )

        if not user.is_active:
            raise serializers.ValidationError(
                "User account is disabled."
            )

        return user
