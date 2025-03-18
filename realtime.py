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
                trip = entity.trip_update if entity.HasField("trip_update") else None
                stop_time_update = trip.stop_time_update if trip and trip.stop_time_update else []
                
                stop_time_str = ", ".join([f"Stop {stu.stop_sequence}: Arrival - {stu.arrival.time if stu.HasField('arrival') else 'N/A'}, Departure - {stu.departure.time if stu.HasField('departure') else 'N/A'}" for stu in stop_time_update]) if stop_time_update else "No Stop Updates"
                
                data.append({
                    "Vehicle ID": vehicle.vehicle.id,
                    "Label": vehicle.vehicle.label,
                    "Latitude": vehicle.position.latitude,
                    "Longitude": vehicle.position.longitude,
                    "Bearing": vehicle.position.bearing,
                    "Speed (m/s)": vehicle.position.speed,
                    "Route ID": trip.route_id if trip and trip.HasField("route_id") else "Unknown",
                    "Trip ID": trip.trip_id if trip and trip.HasField("trip_id") else "Unknown",
                    "Trip start_time": trip.start_time if trip and trip.HasField("start_time") else "Unknown",
                    "Trip Modifications": trip.schedule_relationship if trip and trip.HasField("schedule_relationship") else "Unknown",
                    "Stop Sequence": vehicle.current_stop_sequence if vehicle.HasField("current_stop_sequence") else "Unknown",
                    "Stop Time Update": stop_time_str,
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
