from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from bus_app.models import Route, Bus, Trip


class Command(BaseCommand):
    help = "Create 5 routes, 5 buses, and ONLY 5 trips (1 per route) on 20 Feb 2026"

    def handle(self, *args, **options):

        self.stdout.write(self.style.WARNING("Starting population..."))

        # ----------------------------
        # Routes with distance & price
        # ----------------------------
        routes_data = [
            {"from": "Lahore", "to": "Islamabad", "price": 1500, "distance_km": 380},
            {"from": "Lahore", "to": "Karachi", "price": 5000, "distance_km": 1215},
            {"from": "Karachi", "to": "Islamabad", "price": 4800, "distance_km": 1140},
            {"from": "Karachi", "to": "Lahore", "price": 5000, "distance_km": 1215},
            {"from": "Rawalpindi", "to": "Quetta", "price": 4000, "distance_km": 930},
        ]

        avg_speed = 70  # km/h

        # 20 Feb 2026 (timezone aware)
        base_date = timezone.make_aware(datetime(2026, 2, 20, 0, 0, 0))

        # different time for each route
        trip_hours = [6, 7, 8, 9, 10]

        trip_count = 0

        for i, r in enumerate(routes_data):

            # ---- Route ----
            route, _ = Route.objects.get_or_create(
                location_from=r["from"],
                location_to=r["to"],
            )

            # ---- Bus (1 bus per route) ----
            bus_number = f"BUS20{i + 1}"
            bus, _ = Bus.objects.get_or_create(
                bus_number=bus_number,
                defaults={
                    "capacity": 40,
                    "type_of_bus": "AC",
                    "is_available": True,
                },
            )

            # ---- Duration ----
            duration_hours = r["distance_km"] / avg_speed
            duration = timedelta(hours=duration_hours)

            # ---- Trip (ONLY ONE) ----
            departure_time = base_date.replace(hour=trip_hours[i])
            arrival_time = departure_time + duration

            if departure_time < timezone.now():
                self.stdout.write(self.style.ERROR("Trip date is in the past. Skipping..."))
                continue

            trip, created = Trip.objects.get_or_create(
                bus=bus,
                route=route,
                departure_time=departure_time,
                defaults={
                    "arrival_time": arrival_time,
                    "price": r["price"],
                    "is_active": True,
                    "status": "scheduled",
                },
            )

            if not created:
                trip.arrival_time = arrival_time
                trip.price = r["price"]
                trip.save(update_fields=["arrival_time", "price"])

            trip_count += 1

            self.stdout.write(
                self.style.SUCCESS(
                    f"Trip Created: {route.route_name} | Bus {bus.bus_number} | "
                    f"{departure_time.time()} → {arrival_time.time()} | Rs {r['price']}"
                )
            )

        self.stdout.write(self.style.SUCCESS(f"\n✅ DONE! Total Trips: {trip_count}\n"))
