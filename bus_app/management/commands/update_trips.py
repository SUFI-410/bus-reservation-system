from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from bus_app.models import Trip


class Command(BaseCommand):
    help = 'Update only past trips to future dates for testing/demo'

    def handle(self, *args, **options):
        now = timezone.now()
        past_trips = Trip.objects.filter(departure_time__lt=now).order_by('id')

        if not past_trips.exists():
            self.stdout.write(self.style.SUCCESS("No past trips to update. All trips are in the future!"))
            return

        for i, trip in enumerate(past_trips):
            trip.departure_time = now + timedelta(days=i + 1)
            trip.arrival_time = trip.departure_time + timedelta(hours=5)
            trip.save()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Updated past trip {trip.bus.bus_number}: {trip.departure_time} → {trip.arrival_time}"
                )
            )

        self.stdout.write(self.style.SUCCESS("All past trips have been updated to future dates!"))
