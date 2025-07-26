import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import pandas as pd
from google.transit import gtfs_realtime_pb2
from datetime import datetime, timedelta
import time
import pytz

def fetch_gtfs_rt(url):
    """Fetch GTFS-RT data from a given URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        st.error(f"Error fetching GTFS-RT data: {e}")
        return None

# --- CONSTANTS ---
SEQ_VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"
SEQ_TRIP_UPDATES_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/TripUpdates/Bus"
BRISBANE_TZ = pytz.timezone('Australia/Brisbane')

# Region boundaries defined as a clear structure
REGION_BOUNDS = {
    "Brisbane": {"lat": (-27.75, -27.0), "lon": (152.75, 153.5)},
    "Gold Coast": {"lat": (-28.2, -27.78), "lon": (153.2, 153.6)},
    "Sunshine Coast": {"lat": (-26.9, -26.3), "lon": (152.8, 153.2)},
}


def _fetch_and_parse_gtfs(url: str) -> gtfs_realtime_pb2.FeedMessage | None:
    """Helper to fetch and parse GTFS-RT data."""
    content = fetch_gtfs_rt(url) # Your existing fetch function
    if not content:
        return None
    
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(content)
    return feed

def get_realtime_vehicles() -> pd.DataFrame:
    """Fetch real-time vehicle positions from GTFS-RT API."""
    feed = _fetch_and_parse_gtfs(SEQ_VEHICLE_POSITIONS_URL)
    if not feed:
        return pd.DataFrame()
    
    vehicles = [
        {
            "trip_id": entity.vehicle.trip.trip_id,
            "route_id": entity.vehicle.trip.route_id,
            "vehicle_id": entity.vehicle.vehicle.label,
            "lat": entity.vehicle.position.latitude,
            "lon": entity.vehicle.position.longitude,
            "Timestamp": datetime.fromtimestamp(entity.vehicle.timestamp, BRISBANE_TZ).strftime('%Y-%m-%d %H:%M:%S')
        }
        for entity in feed.entity if entity.HasField("vehicle")
    ]
    return pd.DataFrame(vehicles)

def get_vehicle_updates() -> pd.DataFrame:
    """Merge vehicle positions and trip updates, and categorize by region."""
    vehicles_df = get_realtime_vehicles()
    updates_df = get_trip_updates()

    if vehicles_df.empty:
        return pd.DataFrame() # Return empty df to avoid errors downstream

    # Merge data
    veh_update = vehicles_df.merge(updates_df, on=["trip_id", "route_id"], how="left")
    veh_update["route_name"] = veh_update["route_id"].str.split("-").str[0]
    
    # --- Efficient Region Categorization ---
    conditions = [
        (veh_update["lat"].between(*bounds["lat"]) & veh_update["lon"].between(*bounds["lon"]))
        for region, bounds in REGION_BOUNDS.items()
    ]
    choices = list(REGION_BOUNDS.keys())
    
    veh_update["region"] = np.select(conditions, choices, default="Other")
    
    return veh_update
