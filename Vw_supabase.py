import streamlit as st
import pandas as pd
import psycopg2
import pydeck as pdk

# --- Database connection ---
PG_HOST = "eegejlqdgahlmtjniupz.supabase.co"
PG_PORT = 5432
PG_DB = "postgres"
PG_USER = "postgres"
PG_PASSWORD = "Supa1base!"

@st.cache_data
def get_connection():
    return psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        sslmode="require"
    )

@st.cache_data
def load_table(name):
    conn = get_connection()
    df = pd.read_sql(f"SELECT * FROM {name}", conn)
    conn.close()
    return df

# --- Load data ---
routes_df = load_table("gtfs_routes")
stops_df = load_table("gtfs_stops")
trips_df = load_table("gtfs_trips")
shapes_df = load_table("gtfs_shapes")

# --- App interface ---
st.title("GTFS Route Visualisation")
region = st.selectbox("Select a Region", stops_df["region"].dropna().unique(), index=0)

# Filter stops by region and get corresponding route_ids
region_stop_ids = stops_df[stops_df["region"] == region]["stop_id"].unique()
trip_ids = trips_df[trips_df["trip_id"].isin(
    load_table("gtfs_stop_times")[load_table("gtfs_stop_times")["stop_id"].isin(region_stop_ids)]["trip_id"]
)]["trip_id"].unique()

region_routes = trips_df[trips_df["trip_id"].isin(trip_ids)]["route_id"].unique()
routes_to_show = routes_df[routes_df["route_id"].isin(region_routes)]

route_selection = st.selectbox("Select a Route", routes_to_show["route_id"])

# Get one shape_id for the selected route
selected_trip = trips_df[trips_df["route_id"] == route_selection].iloc[0]
shape_id = selected_trip["shape_id"]
route_shapes = shapes_df[shapes_df["shape_id"] == shape_id].copy()
route_shapes = route_shapes.sort_values("shape_pt_sequence")

# Map view
if not route_shapes.empty:
    shape_layer = pdk.Layer(
        "LineLayer",
        data=route_shapes,
        get_source_position=["shape_pt_lon", "shape_pt_lat"],
        get_target_position=["shape_pt_lon", "shape_pt_lat"].copy(),
        get_width=5,
        get_color=[0, 0, 255],
        pickable=True
    )

    midpoint = (route_shapes["shape_pt_lat"].mean(), route_shapes["shape_pt_lon"].mean())
    view_state = pdk.ViewState(
        latitude=midpoint[0],
        longitude=midpoint[1],
        zoom=11,
        pitch=0
    )

    st.pydeck_chart(pdk.Deck(
        layers=[shape_layer],
        initial_view_state=view_state,
        tooltip={"text": "Route ID: " + route_selection}
    ))
else:
    st.warning("No shape data found for selected route.")
