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
                "Timestamp": datetime.fromtimestamp(vehicle.timestamp, pytz.timezone('Australia/Brisbane')).strftime('%Y-%m-%d %H:%M:%S %Z') if vehicle.HasField("timestamp") else "Unknown"
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
        elif -28.2 <= lat <= -27.78 and 153.2 <= lon <= 153.6:
            return "Gold Coast"
        elif -26.9 <= lat <= -26.3 and 152.8 <= lon <= 153.2:
            return "Sunshine Coast"
        else:
            return "Other"
    
    veh_update["region"] = veh_update.apply(lambda row: categorize_region(row["lat"], row["lon"]), axis=1)
    
    return veh_update
