import requests
from google.transit import gtfs_realtime_pb2
import pandas as pd
import streamlit as st

# Define the GTFS-RT feed URL
GTFS_RT_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def fetch_vehicle_fields(url):
    """Fetch GTFS-RT data and list all fields in feed.entity.vehicle."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Ensure request was successful
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        
        # Extract fields for the first vehicle entity
        data = []
        for entity in feed.entity:
            if entity.HasField("vehicle"):
                vehicle = entity.vehicle
                trip = entity.trip_update.trip
                stop=entity.trip_update.stop_time_update
                data.append({
                    "Vehicle ID": vehicle.vehicle.id,
                    "Label": vehicle.vehicle.label,
                    "Latitude": vehicle.position.latitude,
                    "Longitude": vehicle.position.longitude,
                    "Bearing": vehicle.position.bearing,
                    "Speed (m/s)": vehicle.position.speed,
                    "Route ID": vehicle.trip.route_id,
                    "Trip ID": vehicle.trip.trip_id,
                    "Trip start_time": trip.start_time if trip.HasField("start_time") else "Unknown",
                    "Delay": stop.arrival.delay if trip.HasField("arrival") else "Unknown",
                    "Stop Sequence": vehicle.current_stop_sequence if vehicle.HasField("current_stop_sequence") else "Unknown",
                    "Occupancy Status": vehicle.occupancy_status if vehicle.HasField("occupancy_status") else "Unknown",
                    "Timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else "Unknown"
                })
        
        return pd.DataFrame(data)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching GTFS-RT feed: {e}")
        return pd.DataFrame()

# Streamlit App
st.title("GTFS Realtime Vehicle Fields")

# Fetch data and display as table
df = fetch_vehicle_fields(GTFS_RT_URL)
if not df.empty:
    st.dataframe(df)
else:
    st.write("No vehicle data available.")
