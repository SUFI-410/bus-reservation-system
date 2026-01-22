from django.db.models import Q


def filter_trips(trips_queryset, from_city=None, to_city=None, search_text=None):
    """
    Filter trips by from_city, to_city, or search text.
    """
    if from_city:
        trips_queryset = trips_queryset.filter(route__location_from__icontains=from_city)
    if to_city:
        trips_queryset = trips_queryset.filter(route__location_to__icontains=to_city)
    if search_text:
        trips_queryset = trips_queryset.filter(
            Q(bus__bus_number__icontains=search_text) |
            Q(route__route_name__icontains=search_text)
        )
    return trips_queryset


def sort_trips(trips_queryset, sort_field="departure_time"):
    """
    Sort trips by any field.
    Default: departure_time ascending.
    """
    return trips_queryset.order_by(sort_field)


def sort_bookings(bookings_queryset, sort_field="-created_at"):
    """
    Sort bookings by any field.
    Default: newest first.
    """
    return bookings_queryset.order_by(sort_field)
