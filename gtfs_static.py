import pandas as pd
import requests
import zipfile
import io
import streamlit as st
import pydeck as pdk

# GTFS Static Data URL
GTFS_ZIP_URL = "https://www.data.qld.gov.au/dataset/general-transit-feed-specification-gtfs-translink/resource/e43b6b9f-fc2b-4630-a7c9-86dd5483552b/download"

def download_gtfs():
    """Download GTFS ZIP file and return as an in-memory object."""
    try:
        response = requests.get(GTFS_ZIP_URL, timeout=10)
        response.raise_for_status()
        return zipfile.ZipFile(io.BytesIO(response.content))
    except requests.RequestException as e:
        st.error(f"Error downloading GTFS data: {e}")
        return None

def extract_file(zip_obj, filename):
    """Extract a file from GTFS ZIP archive and return as a DataFrame."""
    try:
        with zip_obj.open(filename) as file:
            return pd.read_csv(file, dtype=str, low_memory=False)
    except Exception as e:
        st.warning(f"Could not read {filename}: {e}")
        return pd.DataFrame()

def load_gtfs_data():
    """Load GTFS data and return routes, stops, trips, stop_times, and shapes."""
    zip_obj = download_gtfs()
    if not zip_obj:
        return None, None, None, None, None

    routes_df = extract_file(zip_obj, "routes.txt")
    stops_df = extract_file(zip_obj, "stops.txt")
    trips_df = extract_file(zip_obj, "trips.txt")
    stop_times_df = extract_file(zip_obj, "stop_times.txt")
    shapes_df = extract_file(zip_obj, "shapes.txt")

    return routes_df, stops_df, trips_df, stop_times_df, shapes_df

def get_route_shapes(route_id, direction, trips_df, shapes_df):
    """Retrieve shape points for a given route ID and direction."""
    trip_shapes = trips_df[(trips_df["route_id"] == route_id) & (trips_df["direction_id"] == str(direction))][["shape_id"]].drop_duplicates()
    shape_ids = trip_shapes["shape_id"].unique()

    if len(shape_ids) == 0:
        return pd.DataFrame()

    route_shapes = shapes_df[shapes_df["shape_id"].isin(shape_ids)]
    route_shapes = route_shapes.astype({"shape_pt_lat": "float", "shape_pt_lon": "float", "shape_pt_sequence": "int"})

    return route_shapes.sort_values(by=["shape_id", "shape_pt_sequence"])

def get_route_stops(route_id, direction, trips_df, stop_times_df, stops_df):
    """Retrieve stops for a given route ID and direction."""
    trip_ids = trips_df[(trips_df["route_id"] == route_id) & (trips_df["direction_id"] == str(direction))]["trip_id"].unique()
    stops_in_route = stop_times_df[stop_times_df["trip_id"].isin(trip_ids)]
    
    # Merge with stops data
    stops_in_route = stops_in_route.merge(stops_df, on="stop_id", how="left")
    stops_in_route = stops_in_route.astype({"stop_lat": "float", "stop_lon": "float"})

    return stops_in_route.drop_duplicates(subset=["stop_id"])

def plot_route_on_map(route_shapes, route_stops, route_color):
    """Plot route path and stops on a map using Pydeck."""
    if route_shapes.empty:
        st.warning("No shape data available for the selected route.")
        return

    # Line Layer for Route Path
    line_layer = pdk.Layer(
        "LineLayer",
        data=route_shapes,
        get_source_position=["shape_pt_lon", "shape_pt_lat"],
        get_target_position=["shape_pt_lon", "shape_pt_lat"],
        get_color=route_color,  # Unique color for the route
        get_width=4,
        auto_highlight=True,
        pickable=True
    )

    # Scatter Layer for Stops
    stop_layer = pdk.Layer(
        "ScatterplotLayer",
        data=route_stops,
        get_position=["stop_lon", "stop_lat"],
        get_color=[0, 0, 255],  # Blue color for stops
        get_radius=100,
        pickable=True,
        tooltip=True
    )

    view_state = pdk.ViewState(
        latitude=route_shapes["shape_pt_lat"].mean(),
        longitude=route_shapes["shape_pt_lon"].mean(),
        zoom=12,
        pitch=0
    )

    st.pydeck_chart(pdk.Deck(
        layers=[line_layer, stop_layer],
        initial_view_state=view_state,
        tooltip={"text": "{stop_name}"}
    ))

def generate_unique_color(route_id):
    """Generate a unique color based on route ID."""
    hash_code = hash(route_id) % 256
    return [hash_code, (hash_code * 3) % 256, (hash_code * 7) % 256]

# Streamlit App
st.title("Public Transport Route Visualisation")

# Load GTFS data
routes_df, stops_df, trips_df, stop_times_df, shapes_df = load_gtfs_data()

if routes_df is not None and not routes_df.empty:
    # Display routes using route short name
    routes_df["route_display"] = "Route " + routes_df["route_short_name"] + " (" + routes_df["route_id"] + ")"
    route_selection = st.selectbox("Select a Route", routes_df["route_id"], format_func=lambda x: routes_df.loc[routes_df["route_id"] == x, "route_display"].values[0])

    if route_selection and trips_df is not None:
        # Get available directions for the selected route
        directions = trips_df[trips_df["route_id"] == route_selection]["direction_id"].unique()
        direction_selection = st.radio("Select Direction", options=directions, format_func=lambda d: "Outbound" if d == "0" else "Inbound")

        if direction_selection is not None:
            route_shapes = get_route_shapes(route_selection, direction_selection, trips_df, shapes_df)
            route_stops = get_route_stops(route_selection, direction_selection, trips_df, stop_times_df, stops_df)
            route_color = generate_unique_color(route_selection)

            plot_route_on_map(route_shapes, route_stops, route_color)
else:
    st.error("Failed to load GTFS data.")