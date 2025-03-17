import requests
import pandas as pd
import streamlit as st
from google.transit import gtfs_realtime_pb2
import time

# GTFS-RT URL (TransLink - Bus)
GTFS_RT_VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def get_realtime_data(route_id=None):
    """Fetch and parse GTFS-RT vehicle positions. If route_id is provided, filter by that route."""
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(GTFS_RT_VEHICLE_POSITIONS_URL)

    if response.status_code != 200:
        return pd.DataFrame(), [], "Failed to fetch real-time data"

    feed.ParseFromString(response.content)

    vehicles = []
    routes = set()  # Collect unique route IDs
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            vehicle = entity.vehicle
            routes.add(vehicle.trip.route_id)  # Store unique routes
            if route_id is None or vehicle.trip.route_id == route_id:
                vehicles.append({
                    "Trip ID": vehicle.trip.trip_id,
                    "Route ID": vehicle.trip.route_id,
                    "Vehicle ID": vehicle.vehicle.id,
                    "Latitude": vehicle.position.latitude,
                    "Longitude": vehicle.position.longitude,
                    "Speed (m/s)": vehicle.position.speed if vehicle.position.HasField("speed") else None
                })

    return pd.DataFrame(vehicles), sorted(routes), None

# Streamlit App
st.title("Real-Time Bus Tracking")

# Auto-refresh mechanism
REFRESH_INTERVAL = 30  # Auto-refresh every 30 seconds
st.text(f"Auto-refreshing every {REFRESH_INTERVAL} seconds")

# Add auto-refresh using Streamlit's built-in function
st_autorefresh = st.experimental_rerun if hasattr(st, "experimental_rerun") else None
if st_autorefresh:
    st_autorefresh(interval=REFRESH_INTERVAL * 1000, key="data_refresh")

# Fetch real-time data
df, route_list, error = get_realtime_data()

if error:
    st.error(error)
elif not route_list:
    st.error("No routes found in real-time data.")
else:
    # Dropdown for selecting route
    selected_route = st.selectbox("Select a Route", options=route_list, index=route_list.index("700") if "700" in route_list else 0)

    # Fetch and display data for the selected route
    df_filtered, _, _ = get_realtime_data(selected_route)

    if df_filtered.empty:
        st.warning(f"No active vehicles found for route {selected_route}")
    else:
        st.write(f"### Live Vehicle Data for Route {selected_route}")
        st.dataframe(df_filtered)

# Run with: `streamlit run script.py`
