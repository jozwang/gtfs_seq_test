# import requests
# from google.transit import gtfs_realtime_pb2
# import pandas as pd


import streamlit as st
import folium
from streamlit_folium import folium_static
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
    """Merge real-time vehicle positions with trip updates, add route_name, and categorize by lat/lon."""
    vehicles_df = get_realtime_vehicles()
    updates_df = get_trip_updates()
    
    if vehicles_df.empty:
        return updates_df
    if updates_df.empty:
        return vehicles_df
    
    veh_update = vehicles_df.merge(updates_df, on=["trip_id", "route_id"], how="left")
    veh_update["route_name"] = veh_update["route_id"].str.split("-").str[0]
    
    # Categorize by lat/lon
    def categorize_region(lat, lon):
        if -27.75 <= lat <= -27.0 and 152.75 <= lon <= 153.5:
            return "Brisbane"
        elif -28.2 <= lat <= -27.8 and 153.3 <= lon <= 153.6:
            return "Gold Coast"
        elif -26.9 <= lat <= -26.3 and 152.8 <= lon <= 153.2:
            return "Sunshine Coast"
        else:
            return "Other"
    
    veh_update["region"] = veh_update.apply(lambda row: categorize_region(row["lat"], row["lon"]), axis=1)
    
    return veh_update


# Streamlit App
st.set_page_config(layout="wide")
st.title("GTFS Realtime Vehicle Fields")

# Cache the last selection
if "selected_region" not in st.session_state:
    st.session_state.selected_region = "Gold Coast"
if "selected_route" not in st.session_state:
    st.session_state.selected_route = "777"

# Fetch vehicle data
df = get_vehicle_updates()

# Sidebar filters
st.sidebar.title("🚍 Select Filters")

# Region selection
region_options = sorted(df["region"].unique())
st.session_state.selected_region = st.sidebar.selectbox("Select a Region", region_options, index=region_options.index(st.session_state.selected_region) if st.session_state.selected_region in region_options else 0)

# Filter routes based on selected region
filtered_df = df[df["region"] == st.session_state.selected_region]
route_options = sorted(filtered_df["route_name"].unique())
st.session_state.selected_route = st.sidebar.selectbox("Select a Route", route_options, index=route_options.index(st.session_state.selected_route) if st.session_state.selected_route in route_options else 0)

# Apply filters
display_df = filtered_df[filtered_df["route_name"] == st.session_state.selected_route]

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# Display filtered data
if not display_df.empty:
    st.dataframe(display_df)
else:
    st.write("No vehicle data available.")

# Display map if there are filtered results
if not display_df.empty:
    st.write("### Vehicle Map")
    # map_container = st.container()
    # with map_container:
    #     map_width = st.get_option("server.maxUploadSize")  # Set width to fit the layout
    m = folium.Map(location=[display_df["lat"].mean(), display_df["lon"].mean()], zoom_start=10, tiles="cartodb positron")

    for _, row in display_df.iterrows():
        # Set marker color based on stop status
        if row["status"] == "On Time":
            color = "green"
        elif row["status"] == "Delayed":
            color = "yellow"
        else:
            color = "red"
        
        marker = folium.Marker(
            location=[row["lat"], row["lon"]],
            popup=f"Vehicle ID: {row['vehicle_id']}",
            icon=folium.Icon(color=color)
        ).add_to(m)
        
        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=folium.DivIcon(html=f'<div style="font-size: 12px; font-weight: bold; color: black; background-color: white; padding: 2px; border-radius: 3px;">{row["vehicle_id"]}</div>')
        ).add_to(m)

    folium_static(m)


# Add auto-refresh checkbox
auto_refresh = st.sidebar.checkbox("Auto-refresh every 30 seconds")
# Add simple auto-refresh
if auto_refresh:
    st.empty()
    st.rerun()
        
# st.set_page_config(layout="wide")
# st.title("GTFS Realtime Vehicle Fields")

# # Fetch data and display as table
# # df = fetch_vehicle_fields(GTFS_RT_URL)
# df=get_vehicle_updates() 
# if not df.empty:
#     st.dataframe(df)
# else:
#     st.write("No vehicle data available.")


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

