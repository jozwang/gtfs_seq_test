import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
from sqlalchemy import create_engine
from gtfs_realtime import get_vehicle_updates

# --- Configuration ---
SUPABASE_URL = st.secrets.get("SUPABASE_URL")
SEQ_VIEW_NAME = "seq_gtfs_static"

# --- Get SQLAlchemy engine ---
def get_sqlalchemy_engine():
    try:
        return create_engine(SUPABASE_URL)
    except Exception as e:
        st.error(f"Database connection error: {e}")
        return None

# --- Load GTFS view data from Supabase ---
@st.cache_data(show_spinner=False)
def load_seq_gtfs_static():
    engine = get_sqlalchemy_engine()
    if engine is None:
        return pd.DataFrame()
    try:
        df = pd.read_sql(f"SELECT * FROM {SEQ_VIEW_NAME}", con=engine)
        df["shape_pt_lat"] = df["shape_pt_lat"].astype(float)
        df["shape_pt_lon"] = df["shape_pt_lon"].astype(float)
        df["shape_pt_sequence"] = df["shape_pt_sequence"].astype(int)
        return df
    except Exception as e:
        st.error(f"Failed to load data from {SEQ_VIEW_NAME}: {e}")
        return pd.DataFrame()

# --- Get shapes for a route and direction ---
def get_route_shapes(route_id, direction_id, shapes_df):
    route_shapes = shapes_df[
        (shapes_df["route_id"] == route_id) &
        (shapes_df["direction_id"] == str(direction_id))
    ]
    return route_shapes.sort_values(by=["shape_id", "shape_pt_sequence"]) if not route_shapes.empty else pd.DataFrame()

# --- Plot map ---
def plot_map(vehicles_df, route_shapes=None):
    if vehicles_df.empty:
        map_center = [-27.5, 153.0]
    else:
        map_center = [vehicles_df["lat"].mean(), vehicles_df["lon"].mean()]

    m = folium.Map(location=map_center, zoom_start=12)

    # Vehicle markers
    for _, row in vehicles_df.iterrows():
        color = "green" if row["status"] == "On Time" else "orange" if row["status"] == "Delayed" else "red"
        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=folium.Icon(color=color, icon="bus", prefix="fa"),
            popup=f"Vehicle {row['vehicle_id']} on Route {row['route_id']}"
        ).add_to(m)
        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=folium.DivIcon(html=f'<div style="font-size: 12px; font-weight: bold; color: black;">{row["vehicle_id"]} - stop {row["Stop Sequence"]}</div>')
        ).add_to(m)

    # Route polylines
    if route_shapes is not None and not route_shapes.empty:
        for shape_id, group in route_shapes.groupby("shape_id"):
            coords = group[["shape_pt_lat", "shape_pt_lon"]].values.tolist()
            if coords:
                folium.PolyLine(
                    locations=coords,
                    color="red",
                    weight=3,
                    tooltip=f"Shape {shape_id}"
                ).add_to(m)

    folium_static(m)

# --- App setup ---
st.set_page_config(layout="wide")
st.title("GTFS Realtime Vehicle & Route Viewer")

# --- Load data ---
shapes_view_df = load_seq_gtfs_static()
vehicles_df = get_vehicle_updates()

# --- Initialise session state ---
if "selected_region" not in st.session_state:
    st.session_state.selected_region = "Gold Coast"
if "selected_route" not in st.session_state:
    st.session_state.selected_route = "All Routes"

# --- Sidebar Filters ---
st.sidebar.title("🚍 Filters")

region_options = sorted(vehicles_df["region"].unique())
st.sidebar.selectbox(
    "Select Region",
    region_options,
    index=region_options.index(st.session_state.selected_region),
    key="selected_region"
)

filtered_df = vehicles_df[vehicles_df["region"] == st.session_state.selected_region]

route_options = ["All Routes"] + sorted(filtered_df["route_name"].unique())
st.sidebar.selectbox(
    "Select Route",
    route_options,
    index=route_options.index(st.session_state.selected_route) if st.session_state.selected_route in route_options else 0,
    key="selected_route"
)

# --- Display logic ---
if st.session_state.selected_route == "All Routes":
    display_df = filtered_df

    status_options = ["All Statuses"] + sorted(display_df["status"].unique())
    selected_status = st.sidebar.selectbox("Select Status", status_options, index=0)
    if selected_status != "All Statuses":
        display_df = display_df[display_df["status"] == selected_status]

    plot_map(display_df)
else:
    route_id = filtered_df[filtered_df["route_name"] == st.session_state.selected_route]["route_id"].iloc[0]
    filtered_vehicles = filtered_df[filtered_df["route_id"] == route_id]

    if filtered_vehicles.empty:
        st.warning(f"No vehicles currently active on route {st.session_state.selected_route}")
        plot_map(filtered_vehicles)
    else:
        directions = shapes_view_df[shapes_view_df["route_id"] == route_id]["direction_id"].unique()
        if len(directions) > 0:
            selected_direction = st.sidebar.radio(
                "Select Direction",
                options=sorted(directions),
                format_func=lambda d: "Outbound" if d == "0" else "Inbound"
            )
            filtered_vehicles = filtered_vehicles[filtered_vehicles["direction_id"] == selected_direction]
            route_shapes = get_route_shapes(route_id, selected_direction, shapes_view_df)
            plot_map(filtered_vehicles, route_shapes)
        else:
            st.warning("No direction info available for this route.")
            plot_map(filtered_vehicles)

# --- Refresh Button ---
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.vehicles_df = get_vehicle_updates()

# --- Data Table ---
st.write("Vehicle Data:")
st.dataframe(filtered_vehicles if st.session_state.selected_route != "All Routes" else display_df)
