from rest_framework.permissions import BasePermission, SAFE_METHODS
from django.utils import timezone


# -------------------------------
# OWNER OR READ ONLY
# -------------------------------
class IsOwnerOrReadOnly(BasePermission):
    """
    Read-only access for everyone.
    Write access only for the object owner.
    """

    def has_permission(self, request, view):
        # Allow read access for everyone
        if request.method in SAFE_METHODS:
            return True

        # Write actions require authentication
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True

        return obj.user == request.user


# -------------------------------
# BOOKING OWNER ONLY
# -------------------------------
class IsBookingOwner(BasePermission):
    """
    Allow access only to the booking owner.
    """

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return obj.user == request.user


# -------------------------------
# ADMIN OR READ ONLY
# -------------------------------
class IsAdminOrReadOnly(BasePermission):
    """
    Read-only for everyone.
    Write access only for admin users.
    """

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True

        return request.user and request.user.is_authenticated and request.user.is_staff


# -------------------------------
# CAN CANCEL BOOKING
# -------------------------------
class CanCancelBooking(BasePermission):
    """
    Allow booking cancellation only if:
    - User is authenticated
    - User owns the booking
    - Booking is not already cancelled
    - Trip is not completed
    - Cancellation is at least 24 hours before departure
    """

    def has_permission(self, request, view):
        # Cancellation requires authentication
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Only allow cancel actions (POST / DELETE)
        if request.method not in ("POST", "DELETE"):
            return False

        if obj.user != request.user:
            return False

        if obj.is_cancelled:
            return False

        if obj.trip.status == "completed":
            return False

        time_diff = obj.trip.departure_time - timezone.now()
        return time_diff.total_seconds() >= 24 * 60 * 60


# -------------------------------
# ADMIN REPORT ACCESS
# -------------------------------
class CanViewRevenueReport(BasePermission):
    """
    Allow only admin users to view revenue and analytics reports.
    """

    def has_permission(self, request, view):
        return (
                request.user
                and request.user.is_authenticated
                and request.user.is_staff
        )
