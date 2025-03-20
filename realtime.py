# import requests
# from google.transit import gtfs_realtime_pb2
# import pandas as pd
import streamlit as st

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
#                 trip = vehicle.trip
#                 position = vehicle.position                


#                 data.append({
#                     "Vehicle ID": vehicle.vehicle.id,
#                     "Label": vehicle.vehicle.label,
#                     "Latitude": vehicle.position.latitude,
#                     "Longitude": vehicle.position.longitude,
#                     "Route ID": trip.route_id ,
#                     "Trip ID": trip.trip_id ,
#                     "Stop Sequence": vehicle.current_stop_sequence ,
#                     "Stop ID": vehicle.stop_id ,
#                     "current_status": vehicle.current_status ,
#                     "Timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else "Unknown"
#                 })
        
#         return pd.DataFrame(data)
#     except requests.exceptions.RequestException as e:
#         st.error(f"Error fetching GTFS-RT feed: {e}")
#         return pd.DataFrame()

import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime

def fetch_gtfs_rt(url):
    """Fetch GTFS-RT data from a given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        st.error(f"Error fetching GTFS-RT data: {e}")
        return None

def get_realtime_vehicles():
    """Fetch real-time vehicle positions from GTFS-RT API."""
    feed = gtfs_realtime_pb2.FeedMessage()
    content = fetch_gtfs_rt("https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus")
    if not content:
        return pd.DataFrame()
    
    feed.ParseFromString(content)
    vehicles = []
    # timestamp = datetime.utcnow()
    
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            vehicle = entity.vehicle
            vehicles.append({
                "trip_id": vehicle.trip.trip_id,
                "route_id": vehicle.trip.route_id,
                "vehicle_id": vehicle.vehicle.label,
                "lat": vehicle.position.latitude,
                "lon": vehicle.position.longitude,
                "Stop Sequence": vehicle.current_stop_sequence ,
                "Stop ID": vehicle.stop_id ,
                "current_status": vehicle.current_status ,
                "Timestamp": vehicle.timestamp if vehicle.HasField("timestamp") else "Unknown"
            })
    
    return pd.DataFrame(vehicles)

def get_trip_updates():
    """Fetch trip updates (delays, cancellations) from GTFS-RT API."""
    feed = gtfs_realtime_pb2.FeedMessage()
    content = fetch_gtfs_rt("https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates/Bus")
    if not content:
        return pd.DataFrame()
    
    feed.ParseFromString(content)
    updates = []
    
    for entity in feed.entity:
        if entity.HasField("trip_update"):
            trip_update = entity.trip_update
            delay = trip_update.stop_time_update[0].arrival.delay if trip_update.stop_time_update else None
            updates.append({
                "trip_id": trip_update.trip.trip_id,
                "route_id": trip_update.trip.route_id,
                "delay": delay,
                "status": "Delayed" if delay and delay > 300 else ("Early" if delay and delay < -60 else "On Time")
            })
    
    return pd.DataFrame(updates)

def get_vehicle_updates():
    """Merge real-time vehicle positions with trip updates on trip_id and route_id."""
    vehicles_df = get_realtime_vehicles()
    updates_df = get_trip_updates()
    
    if vehicles_df.empty:
        return updates_df
    if updates_df.empty:
        return vehicles_df
    
    veh_update = vehicles_df.merge(updates_df, on=["trip_id", "route_id"], how="left")
    return veh_update

# Streamlit App
st.set_page_config(layout="wide")
st.title("GTFS Realtime Vehicle Fields")

# Fetch data and display as table
# df = fetch_vehicle_fields(GTFS_RT_URL)
df=get_vehicle_updates()
if not df.empty:
    st.dataframe(df)
else:
    st.write("No vehicle data available.")


# id: "VU-9F10C7088E8F64E70D53AB5059107979_1"
# vehicle {
#   trip {
#     trip_id: "31460054-WBS 24_25-38247"
#     route_id: "526-4010"
#   }
#   position {
#     latitude: -27.6113338
#     longitude: 152.865952
#   }
#   current_stop_sequence: 5
#   current_status: IN_TRANSIT_TO
#   timestamp: 1742286803
#   stop_id: "310421"
#   vehicle {
#     id: "9F10C7088E8F64E70D53AB5059107979_1"
#     label: "1"
#   }
# }

# import requests
# from google.transit import gtfs_realtime_pb2
# import streamlit as st

# # Define the GTFS-RT feed URL
# GTFS_RT_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

# def fetch_all_entities(url):
#     """Fetch GTFS-RT data and display all entity details as text."""
#     try:
#         response = requests.get(url)
#         response.raise_for_status()  # Ensure request was successful
        
#         feed = gtfs_realtime_pb2.FeedMessage()
#         feed.ParseFromString(response.content)
        
#         # Extract all entity data
#         entity_texts = []
#         for entity in feed.entity:
#             entity_texts.append(str(entity))
        
#         return "\n\n".join(entity_texts)
#     except requests.exceptions.RequestException as e:
#         st.error(f"Error fetching GTFS-RT feed: {e}")
#         return ""

# # Streamlit App
# st.title("GTFS Realtime Feed Entities")

# # Fetch and display all data as text
# entities_text = fetch_all_entities(GTFS_RT_URL)
# if entities_text:
#     st.text_area("GTFS-RT Entity Data", entities_text, height=600)
# else:
#     st.write("No entity data available.")

