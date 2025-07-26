
import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta
import time
import pytz
from gtfs_realtime import get_vehicle_updates 


# Streamlit App
st.set_page_config(layout="wide")
st.title("GTFS Realtime Vehicle Fields")

# Cache the last selection
if "selected_region" not in st.session_state:
    st.session_state.selected_region = "Gold Coast"
if "selected_route" not in st.session_state:
    st.session_state.selected_route = "777"
if "last_refreshed" not in st.session_state:
    st.session_state["last_refreshed"] = "N/A"
if "next_refresh" not in st.session_state:
    st.session_state["next_refresh"] = "N/A"


# Fetch vehicle data
df = get_vehicle_updates()

# Put all filters in a form in the sidebar
with st.sidebar.form(key="filter_form"):
    st.header("🚍 Filter Options")
    
    # Filter by Region
    region_options = ["All"] + list(df['region'].unique())
    selected_region = st.selectbox("Region", options=region_options)

    # Filter by Route
    route_options = ["All"] + list(df['route_name'].sort_values().unique())
    selected_routes = st.multiselect("Route Name", options=route_options, default="All")

    # The button that triggers the rerun
    submit_button = st.form_submit_button(label="Apply Filters")

# --- Apply filters AFTER the form is submitted ---
filtered_df = df.copy() # Start with the full dataset

if selected_region != "All":
    filtered_df = filtered_df[filtered_df['region'] == selected_region]

if "All" not in selected_routes and selected_routes:
    filtered_df = filtered_df[filtered_df['route_name'].isin(selected_routes)]

# Now, use `filtered_df` to display your map and data
st.map(filtered_df)
st.dataframe(filtered_df)

# Refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

# # Display filtered data
# if not display_df.empty:
#     st.dataframe(display_df)
# else:
#     st.write("No vehicle data available.")

# Colorize Table Rows to Match Map Markers
def colorize_row(row):
    color = "background-color: green;" if row["status"] == "On Time" else \
            "background-color: orange;" if row["status"] == "Delayed" else \
            "background-color: red;"
    return [color] * len(row)

if not display_df.empty:
    styled_df = display_df.style.apply(colorize_row, axis=1)
    st.write("### Vehicle Data Table")
    st.dataframe(styled_df)
    
# Display map if there are filtered results
if not display_df.empty:
    col1, col2 = st.columns([8, 2])
    with col1:
        st.write("### Vehicle on a Map")
        m = folium.Map(location=[display_df["lat"].mean(), display_df["lon"].mean()], zoom_start=12, tiles="cartodb positron")
        
        for _, row in display_df.iterrows():
            color = "green" if row["status"] == "On Time" else "orange" if row["status"] == "Delayed" else "red"

            # folium.CircleMarker(
            #     location=[row["lat"], row["lon"]],
            #     radius=10,
            #     color=color,
            #     fill=True,
            #     fill_color=color,
            #     fill_opacity=0.9,
            # ).add_to(m)

            folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=folium.Icon(icon="bus", prefix="fa",color=color)
            
           ).add_to(m)
            
            folium.Marker(
                location=[row["lat"], row["lon"]],
                icon=folium.DivIcon(html=f'<div style="font-size: 12px; font-weight: bold; color: black; text-align: center;">{row["vehicle_id"]}-{f"At stop:{row['Stop Sequence']}"}</div>')
            ).add_to(m)
            
            # folium.Marker(
            #     location=[row["lat"] - 0.0002, row["lon"]],
            #     icon=folium.DivIcon(html=f'<div style="font-size: 12px; font-weight: bold; color: black; padding: 2px; border-radius: 6px;"> {f"At stop-{row['Stop Sequence']}"}</div>')
            # ).add_to(m)
        
        folium_static(m)
    
    with col2:
        st.write("### Refresh Info")
        st.write(f"🕒 Last Refreshed: {st.session_state.get('last_refreshed', 'N/A')}")
        st.write(f"⏳ Next Refresh: {st.session_state.get('next_refresh', 'N/A')}")


# Detect browser timezone (defaulting to Australia/Brisbane if unknown)
def get_browser_timezone():
    try:
        import tzlocal
        local_timezone = tzlocal.get_localzone()
        return pytz.timezone(str(local_timezone))
    except Exception:
        return pytz.timezone("Australia/Brisbane")
browser_timezone =get_browser_timezone() 
# pytz.timezone("Australia/Brisbane")

# Auto-refresh
auto_refresh = st.sidebar.checkbox("Auto-refresh every 30 seconds")
if auto_refresh:
    time.sleep(30)
    st.session_state["next_refresh"] = (datetime.now(pytz.utc) + timedelta(seconds=30)).astimezone(browser_timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
    st.session_state["last_refreshed"] = (datetime.now(pytz.utc)).astimezone(browser_timezone).strftime("%Y-%m-%d %H:%M:%S %Z")
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

