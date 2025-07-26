import streamlit as st
import folium
from folium.features import DivIcon
from streamlit_folium import folium_static
import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import pytz

# --- Constants ---
# Use constants for URLs and other magic values for easy maintenance.
VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"
TRIP_UPDATES_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates/Bus"
BRISBANE_TZ = pytz.timezone('Australia/Brisbane')

# Set a wide layout for the app
st.set_page_config(layout="wide")

# --- Data Fetching Functions ---

def fetch_gtfs_rt(url: str) -> bytes | None:
    """Fetch GTFS-RT data from a given URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4xx or 5xx)
        return response.content
    except requests.RequestException as e:
        st.error(f"Couldn't fetch data from the API: {e}")
        return None

def parse_vehicle_positions(content: bytes) -> pd.DataFrame:
    """Parses vehicle position data from GTFS-RT protobuf content."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    
    vehicles = []
    for entity in feed.entity:
        if entity.HasField("vehicle"):
            v = entity.vehicle
            vehicles.append({
                "trip_id": v.trip.trip_id,
                "route_id": v.trip.route_id,
                "vehicle_id": v.vehicle.label,
                "lat": v.position.latitude,
                "lon": v.position.longitude,
                "stop_sequence": v.current_stop_sequence,
                "stop_id": v.stop_id,
                "current_status": v.current_status,
                "timestamp": datetime.fromtimestamp(v.timestamp, BRISBANE_TZ).strftime('%Y-%m-%d %H:%M:%S %Z') if v.HasField("timestamp") else "N/A"
            })
    return pd.DataFrame(vehicles)

def parse_trip_updates(content: bytes) -> pd.DataFrame:
    """Parses trip update data from GTFS-RT protobuf content."""
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)

    updates = []
    for entity in feed.entity:
        if entity.HasField("trip_update"):
            tu = entity.trip_update
            # IMPROVEMENT: Check if stop_time_update list is not empty before accessing index 0
            if tu.stop_time_update:
                delay = tu.stop_time_update[0].arrival.delay
                status = "On Time"
                if delay > 300:
                    status = "Delayed"
                elif delay < -60:
                    status = "Early"
                
                updates.append({
                    "trip_id": tu.trip.trip_id,
                    "delay": delay,
                    "status": status
                })
    return pd.DataFrame(updates)

# --- Main Data Processing ---

# IMPROVEMENT: Use st.cache_data to cache the data for 60 seconds.
# This prevents re-fetching on every filter change and handles auto-refresh.
@st.cache_data(ttl=60)
def get_live_bus_data() -> pd.DataFrame:
    """
    Fetches, merges, and processes vehicle and trip data.
    The result of this function is cached to improve performance.
    """
    vehicle_content = fetch_gtfs_rt(VEHICLE_POSITIONS_URL)
    trip_content = fetch_gtfs_rt(TRIP_UPDATES_URL)

    if not vehicle_content or not trip_content:
        return pd.DataFrame()

    vehicles_df = parse_vehicle_positions(vehicle_content)
    updates_df = parse_trip_updates(trip_content)

    if vehicles_df.empty:
        return pd.DataFrame()

    # Merge dataframes
    live_data = vehicles_df.merge(updates_df, on="trip_id", how="left")
    
    # Fill NaN values for cleaner data
    live_data["delay"].fillna(0, inplace=True)
    live_data["status"].fillna("On Time", inplace=True)

    # Feature Engineering
    live_data["route_name"] = live_data["route_id"].str.split('-').str[0]
    
    # Simple region categorization
    def categorize_region(lat):
        if -27.75 <= lat <= -27.0:
            return "Brisbane"
        elif -28.2 <= lat <= -27.78:
            return "Gold Coast"
        elif -26.9 <= lat <= -26.3:
            return "Sunshine Coast"
        else:
            return "Other"
    
    live_data["region"] = live_data["lat"].apply(categorize_region)
    
    return live_data

# --- Streamlit App UI ---

st.title("🚌 SEQ Live Bus Tracker")

# Fetch the data (will use cache if available)
master_df = get_live_bus_data()

if master_df.empty:
    st.warning("Could not retrieve live bus data. Please try again later.")
    st.stop() # Stop the script if no data is available

# IMPROVEMENT: Use a sidebar and a form for a better filter experience.
with st.sidebar:
    st.header("Filters")
    with st.form("filter_form"):
        # Filter widgets
        selected_region = st.selectbox(
            "Select Region",
            options=["All"] + sorted(master_df["region"].unique().tolist())
        )
        
        selected_route = st.selectbox(
            "Select Route Name",
            options=["All"] + sorted(master_df["route_name"].unique().tolist())
        )
        
        selected_status = st.multiselect(
            "Select Status",
            options=sorted(master_df["status"].unique().tolist()),
            default=sorted(master_df["status"].unique().tolist())
        )
        
        # The 'Apply Filters' button
        submitted = st.form_submit_button("Apply Filters")


# Apply filters only after the form is submitted
filtered_df = master_df.copy() # Start with the full dataset

if selected_region != "All":
    filtered_df = filtered_df[filtered_df["region"] == selected_region]

if selected_route != "All":
    filtered_df = filtered_df[filtered_df["route_name"] == selected_route]

if selected_status:
    filtered_df = filtered_df[filtered_df["status"].isin(selected_status)]


# Display stats and map
st.metric("Buses Currently Tracked", len(filtered_df))

# --- Create Folium Map ---
# This section is updated to include custom labels next to the bus icons.

if not filtered_df.empty:
    map_center = [filtered_df['lat'].mean(), filtered_df['lon'].mean()]
    m = folium.Map(location=map_center, zoom_start=10)

    for _, row in filtered_df.iterrows():
        # Determine the color based on status
        color = "green"
        if row['status'] == 'Delayed':
            color = "red"
        elif row['status'] == 'Early':
            color = "blue"

        # --- 1. Add the main bus icon with its popup ---
        popup_html = f"""
        <b>Route:</b> {row['route_name']} ({row['route_id']})<br>
        <b>Vehicle ID:</b> {row['vehicle_id']}<br>
        <b>Status:</b> {row['status']}<br>
        <b>Delay:</b> {int(row['delay'])} seconds<br>
        <b>Last Update:</b> {row['timestamp']}
        """
        folium.Marker(
            [row['lat'], row['lon']],
            popup=folium.Popup(popup_html, max_width=300),
            icon=folium.Icon(color=color, icon="bus", prefix="fa")
        ).add_to(m)

        # --- 2. Add the custom text label next to the icon ---
        label_text = f"vehicle: {row['vehicle_id']} on stop_seq: {row['stop_sequence']}"
        
        # Define the custom HTML for our label using DivIcon
        label_icon = DivIcon(
            icon_size=(200, 36),
            icon_anchor=(85, 15), # Anchor point to position the label
            html=f"""
            <div style="
                font-size: 10pt; 
                font-weight: bold; 
                color: {color}; 
                background-color: #f5f5f5;
                padding: 4px 8px;
                border: 1px solid {color};
                border-radius: 5px;
                box-shadow: 3px 3px 5px rgba(0,0,0,0.3);
                white-space: nowrap;">
                {label_text}
            </div>
            """
        )
        
        # Add the label as a second, text-only marker at the same location
        folium.Marker(
            location=[row['lat'], row['lon']],
            icon=label_icon
        ).add_to(m)
        
    folium_static(m, width=1400, height=700)
    
    with st.expander("Show Raw Data"):
        st.dataframe(filtered_df)
else:
    st.info("No buses match the current filter criteria.")
