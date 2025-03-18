# import requests
# from google.transit import gtfs_realtime_pb2
# import pandas as pd
# import streamlit as st

# # Define the GTFS-RT feed URL
# GTFS_RT_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

# def fetch_vehicle_fields(url):
#     """Fetch GTFS-RT data and list all fields in feed.entity.vehicle."""
#     try:
#         response = requests.get(url)
#         response.raise_for_status()  # Ensure request was successful
        
#         feed = gtfs_realtime_pb2.FeedMessage()
#         feed.ParseFromString(response.content)
        
#         # Extract fields for the first vehicle entity
#         data = []
#         for entity in feed.entity:
#             if entity.HasField("vehicle"):
#                 vehicle = entity.vehicle
#                 stop_time_update = vehicle.trip.stop_time_update if vehicle.trip and vehicle.trip.stop_time_update else []
                
#                 stop_time_str = ", ".join([f"Stop {stu.stop_sequence}: Arrival - {stu.arrival.time if stu.HasField('arrival') else 'N/A'}, Departure - {stu.departure.time if stu.HasField('departure') else 'N/A'}" for stu in stop_time_update]) if stop_time_update else "No Stop Updates"
                
#                 data.append({
#                     "Vehicle ID": vehicle.vehicle.id,
#                     "Label": vehicle.vehicle.label,
#                     "Latitude": vehicle.position.latitude,
#                     "Longitude": vehicle.position.longitude,
#                     "Bearing": vehicle.position.bearing,
#                     "Speed (m/s)": vehicle.position.speed,
#                     "Route ID": vehicle.trip.route_id if vehicle.HasField("trip") and vehicle.trip.HasField("route_id") else "Unknown",
#                     "Trip ID": vehicle.trip.trip_id if vehicle.HasField("trip") and vehicle.trip.HasField("trip_id") else "Unknown",
#                     "Trip start_time": vehicle.trip.start_time if vehicle.HasField("trip") and vehicle.trip.HasField("start_time") else "Unknown",
#                     "Trip Modifications": vehicle.trip.schedule_relationship if vehicle.HasField("trip") and vehicle.trip.HasField("schedule_relationship") else "Unknown",
#                     "Stop Sequence": vehicle.current_stop_sequence if vehicle.HasField("current_stop_sequence") else "Unknown",
#                     "Stop Time Update": stop_time_str,
#                     "Occupancy Status": vehicle.occupancy_status if vehicle.HasField("occupancy_status") else "Unknown",
#                     "Timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else "Unknown"
#                 })
        
#         return pd.DataFrame(data)
#     except requests.exceptions.RequestException as e:
#         st.error(f"Error fetching GTFS-RT feed: {e}")
#         return pd.DataFrame()

# # Streamlit App
# st.title("GTFS Realtime Vehicle Fields")

# # Fetch data and display as table
# df = fetch_vehicle_fields(GTFS_RT_URL)
# if not df.empty:
#     st.dataframe(df)
# else:
#     st.write("No vehicle data available.")

import requests
from google.transit import gtfs_realtime_pb2
import streamlit as st

# Define the GTFS-RT feed URL
GTFS_RT_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def fetch_all_entities(url):
    """Fetch GTFS-RT data and display all entity details as text."""
    try:
        response = requests.get(url)
        response.raise_for_status()  # Ensure request was successful
        
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        
        # Extract all entity data
        entity_texts = []
        for entity in feed.entity:
            entity_texts.append(str(entity))
        
        return "\n\n".join(entity_texts)
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching GTFS-RT feed: {e}")
        return ""

# Streamlit App
st.title("GTFS Realtime Feed Entities")

# Fetch and display all data as text
entities_text = fetch_all_entities(GTFS_RT_URL)
if entities_text:
    st.text_area("GTFS-RT Entity Data", entities_text, height=600)
else:
    st.write("No entity data available.")

