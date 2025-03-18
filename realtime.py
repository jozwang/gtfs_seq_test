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
                trip = vehicle.trip
                position = vehicle.position                


                data.append({
                    "Vehicle ID": vehicle.vehicle.id,
                    "Label": vehicle.vehicle.label,
                    "Latitude": vehicle.position.latitude,
                    "Longitude": vehicle.position.longitude,
                    "Route ID": trip.route_id ,
                    "Trip ID": trip.trip_id ,
                    "Stop Sequence": vehicle.current_stop_sequence ,
                    "Stop ID": vehicle.stop_id ,
                    "current_status": vehicle.current_status ,
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

