import streamlit as st
import folium
from streamlit_folium import folium_static
from folium.features import DivIcon
from folium.plugins import AntPath
import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta
import pytz
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components

# --- Constants ---
VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"
TRIP_UPDATES_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates/Bus"
BRISBANE_TZ = pytz.timezone('Australia/Brisbane')
REFRESH_INTERVAL_SECONDS = 60

# Set a wide layout for the app
st.set_page_config(layout="wide")

# --- Data Fetching & Processing Functions (No changes here) ---

@st.cache_data(ttl=REFRESH_INTERVAL_SECONDS)
def get_live_bus_data() -> tuple[pd.DataFrame, datetime]:
    """
    Fetches, merges, and processes vehicle and trip data.
    Returns the DataFrame and the time of the data refresh.
    """
    vehicle_content = fetch_gtfs_rt(VEHICLE_POSITIONS_URL)
    trip_content = fetch_gtfs_rt(TRIP_UPDATES_URL)

    if not vehicle_content or not trip_content:
        return pd.DataFrame(), datetime.now(BRISBANE_TZ)

    vehicles_df = parse_vehicle_positions(vehicle_content)
    updates_df = parse_trip_updates(trip_content)

    if vehicles_df.empty:
        return pd.DataFrame(), datetime.now(BRISBANE_TZ)

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

    return live_data, datetime.now(BRISBANE_TZ)

def fetch_gtfs_rt(url: str) -> bytes | None:
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        st.error(f"Couldn't fetch data from the API: {e}")
        return None

def parse_vehicle_positions(content: bytes) -> pd.DataFrame:
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


# --- Streamlit App UI ---

st.title("🚌 SEQ Live Bus Tracker")

# Automatically rerun the script to refresh data
st_autorefresh(interval=REFRESH_INTERVAL_SECONDS * 1000, key="data_refresher")

# Fetch current data and the time it was refreshed
current_df, last_refreshed_time = get_live_bus_data()
previous_df = st.session_state.get('previous_df', pd.DataFrame())

# Merge current data with previous locations to track movement
if not previous_df.empty:
    prev_locations = previous_df[['vehicle_id', 'lat', 'lon']]
    master_df = current_df.merge(
        prev_locations, on='vehicle_id', how='left', suffixes=('', '_prev')
    )
else:
    master_df = current_df
    master_df['lat_prev'] = pd.NA
    master_df['lon_prev'] = pd.NA

if master_df.empty:
    st.warning("Could not retrieve live bus data. Please try again later.")
    st.stop()

# --- Initialize session state for filters if they don't exist ---
if 'selected_region' not in st.session_state:
    st.session_state['selected_region'] = 'Gold Coast'
if 'selected_route' not in st.session_state:
    st.session_state['selected_route'] = '700'
if 'selected_status' not in st.session_state:
    st.session_state['selected_status'] = master_df['status'].unique().tolist()
if 'selected_vehicle' not in st.session_state:
    st.session_state['selected_vehicle'] = 'All'


# --- CASCADING FILTERS IN SIDEBAR ---
with st.sidebar:
    st.header("Filters")
    with st.form("filter_form"):
        # 1. REGION FILTER
        region_options = ["All"] + sorted(master_df["region"].unique().tolist())
        # Set index based on session state
        try:
            region_index = region_options.index(st.session_state['selected_region'])
        except ValueError:
            region_index = 0 # Default to "All" if saved region not found
        selected_region = st.selectbox("Region", region_options, index=region_index)

        # 2. ROUTE FILTER
        df_after_region = master_df[master_df["region"] == selected_region] if selected_region != "All" else master_df
        route_options = ["All"] + sorted(df_after_region["route_name"].unique().tolist())
        # Check if saved route is still valid, otherwise reset
        if st.session_state['selected_route'] not in route_options:
            st.session_state['selected_route'] = "All"
        try:
            route_index = route_options.index(st.session_state['selected_route'])
        except ValueError:
            route_index = 0
        selected_route = st.selectbox("Route", route_options, index=route_index)

        # 3. STATUS FILTER
        df_after_route = df_after_region[df_after_region["route_name"] == selected_route] if selected_route != "All" else df_after_region
        status_options = sorted(df_after_route["status"].unique().tolist())
        selected_status = st.multiselect("Status", status_options, default=st.session_state['selected_status'])

        # 4. VEHICLE ID FILTER
        df_after_status = df_after_route[df_after_route["status"].isin(selected_status)] if selected_status else df_after_route
        vehicle_options = ["All"] + sorted(df_after_status["vehicle_id"].unique().tolist())
        if st.session_state['selected_vehicle'] not in vehicle_options:
            st.session_state['selected_vehicle'] = 'All'
        try:
            vehicle_index = vehicle_options.index(st.session_state['selected_vehicle'])
        except ValueError:
            vehicle_index = 0
        selected_vehicle = st.selectbox("Vehicle ID", vehicle_options, index=vehicle_index)

        submitted = st.form_submit_button("Apply Filters")

        # If form is submitted, update the session state with new selections
        if submitted:
            st.session_state['selected_region'] = selected_region
            st.session_state['selected_route'] = selected_route
            st.session_state['selected_status'] = selected_status
            st.session_state['selected_vehicle'] = selected_vehicle
            st.rerun() # Rerun to apply selections immediately

# Use session state values to filter the dataframe
filtered_df = master_df
if st.session_state['selected_region'] != "All":
    filtered_df = filtered_df[filtered_df['region'] == st.session_state['selected_region']]
if st.session_state['selected_route'] != "All":
    filtered_df = filtered_df[filtered_df['route_name'] == st.session_state['selected_route']]
if st.session_state['selected_status']:
    filtered_df = filtered_df[filtered_df['status'].isin(st.session_state['selected_status'])]
if st.session_state['selected_vehicle'] != "All":
    filtered_df = filtered_df[filtered_df['vehicle_id'] == st.session_state['selected_vehicle']]


# --- Display stats and map ---

# Use columns for a tidy layout of stats
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Buses Currently Tracked", len(filtered_df))
with col2:
    st.metric("Last Refreshed", last_refreshed_time.strftime('%I:%M:%S %p %Z'))
with col3:
    next_refresh_time = last_refreshed_time + timedelta(seconds=REFRESH_INTERVAL_SECONDS)
    st.metric("Next Refresh", next_refresh_time.strftime('%I:%M:%S %p %Z'))
with col4:
    # --- LIVE CLOCK (Aligned Version) ---
    initial_time = datetime.now(BRISBANE_TZ)
    tz_string = BRISBANE_TZ.zone

    clock_html = f"""
    <head>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif, "Apple Color Emoji", "Segoe UI Emoji";
            margin: 0;
            padding: 0;
        }}
        .clock-container {{ text-align: center; padding-top: 12px; }}
        .clock-label {{ font-size: 0.8rem; margin-bottom: 0px; color: rgba(49, 51, 63, 0.6); }}
        .clock-time {{ font-weight: 600; font-size: 1.75rem; color: rgb(49, 51, 63); letter-spacing: -0.025rem; margin-top: 0px; padding-top: 0px; }}
    </style>
    </head>
    <body>
        <div class="clock-container">
            <p class="clock-label">Current Time</p>
            <h1 id="clock" class="clock-time">{initial_time.strftime('%I:%M:%S %p')}</h1>
        </div>
        <script>
            function updateClock() {{
                const clockElement = document.getElementById('clock');
                if (clockElement) {{
                    const options = {{ timeZone: '{tz_string}', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true }};
                    const timeString = new Date().toLocaleTimeString('en-AU', options);
                    clockElement.innerHTML = timeString;
                }}
            }}
            if (window.clockIntervalId) clearInterval(window.clockIntervalId);
            window.clockIntervalId = setInterval(updateClock, 1000);
        </script>
    </body>
    """
    components.html(clock_html, height=95)

st.markdown(
    f"<p style='text-align:right; color:grey; font-size:0.9rem;'>{initial_time.strftime('%A, %d %B %Y')}</p>",
    unsafe_allow_html=True
)


# --- Map rendering ---
if not filtered_df.empty:
    map_center = [filtered_df['lat'].mean(), filtered_df['lon'].mean()]
    m = folium.Map(location=map_center, zoom_start=12)

    for _, row in filtered_df.iterrows():
        # --- Draw the animated path for buses that have moved ---
        if pd.notna(row['lat_prev']) and (row['lat'] != row['lat_prev'] or row['lon'] != row['lon_prev']):
            AntPath(
                locations=[[row['lat_prev'], row['lon_prev']], [row['lat'], row['lon']]],
                color="blue",
                weight=5,
                delay=800,
                dash_array=[10, 20]
            ).add_to(m)

        # --- Draw the bus icon and its label ---
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
        st.dataframe(filtered_df[['vehicle_id', 'route_name', 'status', 'delay', 'region', 'timestamp']])
else:
    st.info("No buses match the current filter criteria.")


# --- Save current data to session state for the next refresh ---
st.session_state['previous_df'] = current_df
