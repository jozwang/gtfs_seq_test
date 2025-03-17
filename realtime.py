import requests
import pandas as pd
import streamlit as st
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
                    "Trip ID": vehicle.trip.trip_id,
                    "Route ID": vehicle.trip.route_id,
                    "Vehicle ID": vehicle.vehicle.id,
                    "Latitude": vehicle.position.latitude,
                    "Longitude": vehicle.position.longitude,
                    "Speed (m/s)": vehicle.position.speed if vehicle.position.HasField("speed") else None
                })

    if not vehicles:
        return pd.DataFrame(), f"No active vehicles found for route {route_id}"

    return pd.DataFrame(vehicles), None

# Streamlit App
st.title("Real-Time Bus Tracking - Route 700")

route_id = "700"  # Fixed route for display
df, error = get_realtime_data(route_id)

if error:
    st.warning(error)
else:
    st.write(f"### Live Vehicle Data for Route {route_id}")
    st.dataframe(df)

# Run the script with: `streamlit run script.py`
