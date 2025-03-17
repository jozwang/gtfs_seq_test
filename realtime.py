import requests
import pandas as pd
import streamlit as st
from google.transit import gtfs_realtime_pb2

# GTFS-RT URL (TransLink - Bus)
GTFS_RT_VEHICLE_POSITIONS_URL = "https://gtfsrt.api.translink.com.au/api/realtime/SEQ/VehiclePositions/Bus"

def get_realtime_data(route_id=None):
    """Fetch and parse GTFS-RT vehicle positions. If route_id is provided, filter by that route."""
    feed = gtfs_realtime_pb2.FeedMessage()
    response = requests.get(GTFS_RT_VEHICLE_POSITIONS_URL)

    if response.status_code != 200:
        return pd.DataFrame(), "Failed to fetch real-time data"

    feed.ParseFromString(response.content)

    vehicles = []
    routes = set()  # To collect unique ro
