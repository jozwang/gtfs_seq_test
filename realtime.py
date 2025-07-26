import streamlit as st
import folium
from streamlit_folium import folium_static
from folium.features import DivIcon
import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime
import pytz

# --- Constants ---
VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"
TRIP_UPDATES_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates/Bus"
BRISBANE_TZ = pytz.timezone('Australia/Brisbane')

# Set a wide layout for the app
st.set_page_config(layout="wide")

# --- Data Fetching & Processing Functions (No changes here) ---

def fetch_gtfs_rt(url: str) -> bytes | None:
    """Fetch GTFS-RT data from a given URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
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

@st.cache_data(ttl=60)
def get_live_bus_data() -> pd.DataFrame:
    """Fetches, merges, and processes vehicle and trip data."""
    vehicle_content = fetch_gtfs_rt(VEHICLE_POSITIONS_URL)
    trip_content = fetch_gtfs_rt(TRIP_UPDATES_URL)

    if not vehicle_content or not trip_content:
        return pd.DataFrame()

    vehicles_df = parse_vehicle_positions(vehicle_content)
    updates_df = parse_trip_updates(trip_content)

    if vehicles_df.empty:
        return pd.DataFrame()

    live_data = vehicles_df.merge(updates_df, on="trip_id", how="left")
    live_data["delay"].fillna(0, inplace=True)
    live_data["status"].fillna("On Time", inplace=True)
    live_data["route_name"] = live_data["route_id"].str.split('-').str[0]
    
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

master_df = get_live_bus_data()

if master_df.empty:
    st.warning("Could not retrieve live bus data. Please try again later.")
    st.stop()

# --- CASCADING FILTERS IN SIDEBAR ---
with st.sidebar:
    st.header("Filters")
    with st.form("filter_form"):
        # 1. REGION FILTER (with default)
        region_options = ["All"] + sorted(master_df["region"].unique().tolist())
        try:
            default_region_index = region_options.index("Gold Coast")
        except ValueError:
            default_region_index = 0 # Default to "All" if GC not found
        selected_region = st.selectbox("Region", region_options, index=default_region_index)

        # 2. ROUTE FILTER (cascades from region)
        df_after_region = master_df[master_df["region"] == selected_region] if selected_region != "All" else master_df
        route_options = ["All"] + sorted(df_after_region["route_name"].unique().tolist())
        try:
            default_route_index = route_options.index("700")
        except ValueError:
            default_route_index = 0 # Default to "All" if 700 not found
        selected_route = st.selectbox("Route", route_options, index=default_route_index)

        # 3. STATUS FILTER (cascades from route)
        df_after_route = df_after_region[df_after_region["route_name"] == selected_route] if selected_route != "All" else df_after_region
        status_options = sorted(df_after_route["status"].unique().tolist())
        selected_status = st.multiselect("Status", status_options, default=status_options)

        # 4. VEHICLE ID FILTER (cascades from status)
        df_after_status = df_after_route[df_after_route["status"].isin(selected_status)] if selected_status else df_after_route
        vehicle_options = ["All"] + sorted(df_after_status["vehicle_id"].unique().tolist())
        selected_vehicle = st.selectbox("Vehicle ID", vehicle_options)
        
        submitted = st.form_submit_button("Apply Filters")

# Apply final filter from the form's selections
if selected_vehicle != "All":
    filtered_df = df_after_status[df_after_status["vehicle_id"] == selected_vehicle]
else:
    filtered_df = df_after_status

# --- Display stats and map ---

st.metric("Buses Currently Tracked", len(filtered_df))

if not filtered_df.empty:
    map_center = [filtered_df['lat'].mean(), filtered_df['lon'].mean()]
    m = folium.Map(location=map_center, zoom_start=10)

    for _, row in filtered_df.iterrows():
        color = "green"
        if row['status'] == 'Delayed':
            color = "red"
        elif row['status'] == 'Early':
            color = "blue"

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

        label_text = f"vehicle: {row['vehicle_id']} on stop_seq: {row['stop_sequence']}"
        label_icon = DivIcon(
            icon_size=(200, 36),
            icon_anchor=(85, 15),
            html=f"""
            <div style="font-size: 10pt; font-weight: bold; color: {color}; background-color: #f5f5f5;
                        padding: 4px 8px; border: 1px solid {color}; border-radius: 5px;
                        box-shadow: 3px 3px 5px rgba(0,0,0,0.3); white-space: nowrap;">
                {label_text}
            </div>
            """
        )
        folium.Marker(
            location=[row['lat'], row['lon']],
            icon=label_icon
        ).add_to(m)
        
    folium_static(m, width=1400, height=700)
    
    with st.expander("Show Raw Data"):
        st.dataframe(filtered_df)
else:
    st.info("No buses match the current filter criteria.")
