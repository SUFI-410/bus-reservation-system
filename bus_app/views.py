from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.reverse import reverse
from rest_framework.parsers import JSONParser
from rest_framework.pagination import PageNumberPagination

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
@permission_classes([IsAdminUser])
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
        }
    })


# -----------------------
# TRIPS (FILTER + SORT + PAGINATION)
# -----------------------
class TripPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 50


@permission_classes([IsAdminUser])
class TripListAPIView(APIView):
    permission_classes = [AllowAny]

    ALLOWED_SORT_FIELDS = {
        "price": "price",
        "-price": "-price",
        "departure_time": "departure_time",
        "-departure_time": "-departure_time",
    }

    def get(self, request):  # noqa
        trip_id = request.query_params.get("trip_id")

        # -------- Single Trip Detail --------
        if trip_id:
            try:
                trip = Trip.objects.select_related("bus", "route").get(
                    id=trip_id,
                    is_active=True
                )
            except Trip.DoesNotExist:
                return Response(
                    {"error": "Trip not found"},
                    status=status.HTTP_404_NOT_FOUND
                )

            serializer = TripSerializer(trip)
            return Response(serializer.data)

        # -------- Base Query --------
        trips = Trip.objects.select_related("bus", "route").filter(
            is_active=True,
            departure_time__gte=timezone.now()
        )

        # -------- Filtering --------
        from_city = request.query_params.get("from_city")
        to_city = request.query_params.get("to_city")
        search = request.query_params.get("search")
        travel_date = request.query_params.get("date")  # YYYY-MM-DD

        if from_city:
            trips = trips.filter(route__location_from__icontains=from_city)

        if to_city:
            trips = trips.filter(route__location_to__icontains=to_city)

        if travel_date:
            trips = trips.filter(departure_time__date=travel_date)

        if search:
            trips = trips.filter(
                Q(bus__bus_number__icontains=search) |
                Q(route__route_name__icontains=search)
            )

        # -------- Sorting (Safe) --------
        sort_param = request.query_params.get("sort", "departure_time")
        sort_field = self.ALLOWED_SORT_FIELDS.get(sort_param, "departure_time")
        trips = trips.order_by(sort_field)

        # -------- Pagination --------
        paginator = TripPagination()
        page = paginator.paginate_queryset(trips, request)

        serializer = TripSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


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
            "booking_id": booking.id,  # noqa
            "payment_url": f"/api/bookings/{booking.id}/pay/"  # noqa
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
            .order_by("-created_at")  # newest first
        )

        # Optional search query
        q = request.query_params.get("q")
        if q:
            bookings = bookings.filter(
                Q(seat_number__icontains=q) |
                Q(trip__bus__bus_number__icontains=q) |
                Q(trip__route__route_name__icontains=q)
            )

        # Optional status filter
        status_filter = request.query_params.get("status")
        if status_filter == "confirmed":
            bookings = bookings.filter(is_confirmed=True, is_cancelled=False)
        elif status_filter == "cancelled":
            bookings = bookings.filter(is_cancelled=True)

        # Pagination
        paginator = PageNumberPagination()
        paginator.page_size = 10  # 10 bookings per page
        paginated_bookings = paginator.paginate_queryset(bookings, request)

        serializer = BookingSerializer(paginated_bookings, many=True)
        return paginator.get_paginated_response(serializer.data)


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
            cancel_booking(booking=booking, user=request.user)
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
@permission_classes([IsAdminUser])
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
@permission_classes([IsAdminUser])
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

        return Response({"message": "Payment successful. Booking confirmed"})
