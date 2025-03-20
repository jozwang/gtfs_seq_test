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

def classify_region(lat, lon):
    """Classify a stop into Brisbane, Gold Coast, Sunshine Coast, or Other based on lat/lon."""
    lat, lon = float(lat), float(lon)
    if -28.2 <= lat <= -27.8 and 153.2 <= lon <= 153.5:
        return "Gold Coast"
    elif -27.7 <= lat <= -27.2 and 152.8 <= lon <= 153.5:
        return "Brisbane"
    elif -27.2 <= lat <= -26.3 and 152.8 <= lon <= 153.3:
        return "Sunshine Coast"
    else:
        return "Other"

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

    # Convert lat/lon to float and classify regions
    stops_df["stop_lat"] = stops_df["stop_lat"].astype(float)
    stops_df["stop_lon"] = stops_df["stop_lon"].astype(float)
    stops_df["region"] = stops_df.apply(lambda row: classify_region(row["stop_lat"], row["stop_lon"]), axis=1)

    return routes_df, stops_df, trips_df, stop_times_df, shapes_df

def get_routes_for_region(region, stops_df, trips_df, routes_df):
    """Get routes that have stops in the selected region."""
    stop_ids_in_region = stops_df[stops_df["region"] == region]["stop_id"].unique()
    trip_ids_in_region = stop_times_df[stop_times_df["stop_id"].isin(stop_ids_in_region)]["trip_id"].unique()
    route_ids_in_region = trips_df[trips_df["trip_id"].isin(trip_ids_in_region)]["route_id"].unique()
    
    return routes_df[routes_df["route_id"].isin(route_ids_in_region)]

def get_route_shapes(route_id, direction, trips_df, shapes_df):
    """Retrieve and structure shape points for a given route ID and direction."""
    trip_shapes = trips_df[(trips_df["route_id"] == route_id) & (trips_df["direction_id"] == str(direction))][["shape_id"]].drop_duplicates()
    shape_ids = trip_shapes["shape_id"].unique()

    if len(shape_ids) == 0:
        return pd.DataFrame()

    route_shapes = shapes_df[shapes_df["shape_id"].isin(shape_ids)]
    route_shapes = route_shapes.astype({"shape_pt_lat": "float", "shape_pt_lon": "float", "shape_pt_sequence": "int"})

    # Sort by shape_id and sequence
    route_shapes = route_shapes.sort_values(by=["shape_id", "shape_pt_sequence"])

    # Process each shape_id separately to create line segments
    line_segments = []
    
    for shape_id in shape_ids:
        shape_points = route_shapes[route_shapes["shape_id"] == shape_id].copy()
        
        # Create start-end coordinate pairs for LineLayer
        shape_points["next_lat"] = shape_points["shape_pt_lat"].shift(-1)
        shape_points["next_lon"] = shape_points["shape_pt_lon"].shift(-1)
        
        # Remove last row (no next point to connect)
        shape_points = shape_points.dropna(subset=["next_lat", "next_lon"])
        
        line_segments.append(shape_points)
    
    if not line_segments:
        return pd.DataFrame()
        
    # Combine all line segments
    return pd.concat(line_segments, ignore_index=True)

def get_route_stops(route_id, direction, trips_df, stop_times_df, stops_df):
    """Retrieve stops for a given route ID and direction."""
    # Get a representative trip for this route and direction
    trip_ids = trips_df[(trips_df["route_id"] == route_id) & (trips_df["direction_id"] == str(direction))]["trip_id"].unique()
    
    if len(trip_ids) == 0:
        return pd.DataFrame()
    
    # Take the first trip as representative
    rep_trip_id = trip_ids[0]
    
    # Get stops for this trip with their sequence
    trip_stops = stop_times_df[stop_times_df["trip_id"] == rep_trip_id].copy()
    trip_stops = trip_stops.sort_values(by="stop_sequence")
    
    # Merge with stops data to get coordinates
    stops_in_route = trip_stops.merge(stops_df, on="stop_id", how="left")
    stops_in_route = stops_in_route.astype({"stop_lat": "float", "stop_lon": "float", "stop_sequence": "int"})
    
    # Ensure stop_sequence is a string for the text layer
    stops_in_route["stop_sequence_text"] = stops_in_route["stop_sequence"].astype(str)
    
    return stops_in_route

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
        get_target_position=["next_lon", "next_lat"],
        get_color=route_color,
        get_width=4,
        auto_highlight=True,
        pickable=True
    )

    # Scatter Layer for Stops
    stop_layer = pdk.Layer(
        "ScatterplotLayer",
        data=route_stops,
        get_position=["stop_lon", "stop_lat"],
        get_color=[0, 0, 255],  # Blue for stops
        get_radius=100,
        pickable=True,
        tooltip=True
    )

    # Text Layer for Stop Sequence Numbers
    text_layer = pdk.Layer(
        "TextLayer",
        data=route_stops,
        get_position=["stop_lon", "stop_lat"],
        get_text="stop_sequence_text",  # Use the string version of stop_sequence
        get_size=16,
        get_color=[255, 255, 255],  # White text for contrast
        get_alignment_baseline="center",
        get_angle=0,
        pickable=False
    )
    
    view_state = pdk.ViewState(
        latitude=route_shapes["shape_pt_lat"].mean(),
        longitude=route_shapes["shape_pt_lon"].mean(),
        zoom=12,
        pitch=0
    )

    st.pydeck_chart(pdk.Deck(
        layers=[line_layer, stop_layer, text_layer],
        initial_view_state=view_state,
        tooltip={"text": "{stop_name} (Stop #{stop_sequence})"}
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
    # Region selection with default "Gold Coast"
    region_selection = st.selectbox("Select a Region", ["Gold Coast", "Brisbane", "Sunshine Coast", "Other"], index=0)

    # Filter routes by selected region
    region_routes_df = get_routes_for_region(region_selection, stops_df, trips_df, routes_df)

    if not region_routes_df.empty:
        # Display routes using route short name
        region_routes_df["route_display"] = "Route " + region_routes_df["route_short_name"] + " (" + region_routes_df["route_id"] + ")"
        route_selection = st.selectbox("Select a Route", region_routes_df["route_id"], format_func=lambda x: region_routes_df.loc[region_routes_df["route_id"] == x, "route_display"].values[0])

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
        st.warning("No routes available for the selected region.")
else:
    st.error("Failed to load GTFS data.")
