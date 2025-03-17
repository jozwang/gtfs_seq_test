import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2

# GTFS-RT URL (TransLink - Bus)
GTFS_RT_VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def get_realtime_data(route_id):
    """Fetch and parse GTFS-RT vehicle positions for a specific route."""
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(GTFS_RT_VEHICLE_POSITIONS_URL)

    if response.status_code != 200:
        return pd.DataFrame(), "Failed to fetch real-time data"

    feed.ParseFromString(response.content)

    vehicles = []
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            vehicle = entity.vehicle
            if vehicle.trip.route_id == route_id:
                vehicles.append({
                    "trip_id": vehicle.trip.trip_id,
                    "route_id": vehicle.trip.route_id,
                    "vehicle_id": vehicle.vehicle.id,
                    "lat": vehicle.position.latitude,
                    "lon": vehicle.position.longitude,
                    "speed": vehicle.position.speed if vehicle.position.HasField("speed") else None
                })

    if not vehicles:
        return pd.DataFrame(), f"No active vehicles found for route {route_id}"

    return pd.DataFrame(vehicles), None

# Example usage
route_id = "700"
df, error = get_realtime_data(route_id)
if error:
    print(error)
else:
    print(df)
