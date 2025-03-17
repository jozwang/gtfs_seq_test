import requests
from google.transit import gtfs_realtime_pb2
import pandas as pd
import streamlit as st

# Define the GTFS-RT feed URL
GTFS_RT_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def fetch_gtfs_realtime_entities(url):
    """Fetch and parse GTFS-RT VehiclePositions feed."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Ensure request was successful
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        
        # Extract entities as structured data
        data = []
        for entity in feed.entity:
            vehicle = entity.vehicle
            data.append({
                "Vehicle ID": vehicle.vehicle.id,
                "Label": vehicle.vehicle.label,
                "Latitude": vehicle.position.latitude,
                "Longitude": vehicle.position.longitude,
                "Bearing": vehicle.position.bearing,
                "Speed (m/s)": vehicle.position.speed,
                "Route ID": vehicle.trip.route_id,
                "Trip ID": vehicle.trip.trip_id
            })
        
        return pd.DataFrame(data)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching GTFS-RT feed: {e}")
        return pd.DataFrame()

# Streamlit App
st.title("GTFS Realtime Vehicle Positions")

# Fetch data and display as table
df = fetch_gtfs_realtime_entities(GTFS_RT_URL)
if not df.empty:
    st.dataframe(df)
else:
    st.write("No vehicle data available.")
