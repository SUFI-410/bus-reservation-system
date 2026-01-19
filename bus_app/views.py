from django.contrib.auth import authenticate
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.parsers import JSONParser

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.authentication import JWTAuthentication

from .models import Trip, Booking
from .serializers import TripSerializer, BookingSerializer
from .services import create_booking, cancel_booking
from .permissions import IsBookingOwner


# -----------------------
# JWT Tokens
# -----------------------
def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


# -----------------------
# API ROOT
# -----------------------
@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request, format=None):  # noqa
    return Response({
        "name": "Bus Reservation System API",
        "version": "v1",
        "endpoints": {
            "register": reverse("api-register", request=request, format=format),
            "login": reverse("api-login", request=request, format=format),
            "trips": reverse("api-trips", request=request, format=format),
            "book": reverse("api-book", request=request, format=format),
            "my_bookings": reverse("api-my-bookings", request=request, format=format),
            "cancel_booking": reverse("api-cancel-booking", request=request, format=format),
        }
    })


# -----------------------
# TRIPS
# -----------------------
class TripListAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):  # noqa
        trip_id = request.query_params.get("trip_id")

        if trip_id:
            try:
                trip = Trip.objects.get(id=trip_id, is_active=True)
            except Trip.DoesNotExist:
                return Response(
                    {"error": "Trip not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = TripSerializer(trip)
            return Response(serializer.data)

        trips = Trip.objects.filter(is_active=True)
        serializer = TripSerializer(trips, many=True)
        return Response(serializer.data)


# -----------------------
# CREATE BOOKING (RESERVE SEAT)
# -----------------------
class CreateBookingAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    def post(self, request):  # noqa
        trip_id = request.data.get("trip")
        seat_number = request.data.get("seat_number")

        if not trip_id or not seat_number:
            return Response(
                {"error": "trip and seat_number are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            trip = Trip.objects.get(id=trip_id, is_active=True)
        except Trip.DoesNotExist:
            return Response(
                {"error": "Trip not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            booking = create_booking(
                user=request.user,
                trip=trip,
                seat_number=seat_number
            )
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({
            "message": "Seat reserved. Please complete payment.",
            "booking_id": booking.id, # noqa
            "payment_url": f"/api/bookings/{booking.id}/pay/" # noqa
        }, status=status.HTTP_201_CREATED)


# -----------------------
# MY BOOKINGS
# -----------------------
class MyBookingsAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):  # noqa
        bookings = (
            Booking.objects
            .filter(user=request.user)
            .select_related("trip", "trip__bus", "trip__route")
            .order_by("-created_at")
        )

        serializer = BookingSerializer(bookings, many=True)
        return Response(serializer.data)


# -----------------------
# CANCEL BOOKING
# -----------------------
class CancelBookingAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsBookingOwner]

    def post(self, request, booking_id):
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        self.check_object_permissions(request, booking)

        try:
            cancel_booking(booking)
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {"message": "Booking cancelled successfully"},
            status=status.HTTP_200_OK
        )


# -----------------------
# REGISTER
# -----------------------
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):  # noqa
        username = request.data.get("username")
        email = request.data.get("email")
        password = request.data.get("password")

        if not username or not password:
            return Response(
                {"error": "username and password are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if User.objects.filter(username=username).exists():
            return Response(
                {"error": "username already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "message": "User registered successfully",
                "tokens": tokens
            },
            status=status.HTTP_201_CREATED
        )


# -----------------------
# LOGIN
# -----------------------
class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):  # noqa
        username = request.data.get("username")
        password = request.data.get("password")

        user = authenticate(username=username, password=password)

        if not user:
            return Response(
                {"error": "Invalid credentials"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        tokens = get_tokens_for_user(user)

        return Response(
            {
                "message": "Login successful",
                "tokens": tokens
            }
        )


# -----------------------
# FAKE PAYMENT API
# -----------------------
class FakePaymentAPIView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, booking_id):  # noqa
        try:
            booking = Booking.objects.get(id=booking_id, user=request.user)
        except Booking.DoesNotExist:
            return Response({"error": "Booking not found"}, status=status.HTTP_404_NOT_FOUND)

        booking.payment_status = "paid"
        booking.is_confirmed = True
        booking.save()

        return Response({"message": "Payment successful. Booking confirmed ✅"})
