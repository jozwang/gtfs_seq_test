import streamlit as st
import pandas as pd
import psycopg2
import pydeck as pdk

# --- PostgreSQL Connection Setup ---
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

# --- Load Tables ---
routes_df = load_table("gtfs_routes")
stops_df = load_table("gtfs_stops")
trips_df = load_table("gtfs_trips")
stop_times_df = load_table("gtfs_stop_times")
shapes_df = load_table("gtfs_shapes")

# --- UI ---
st.title("GTFS Route Visualisation")
region = st.selectbox("Select a Region", stops_df["region"].dropna().unique(), index=0)

# --- Filter Routes by Region ---
region_stop_ids = stops_df[stops_df["region"] == region]["stop_id"].unique()
trip_ids = stop_times_df[stop_times_df["stop_id"].isin(region_stop_ids)]["trip_id"].unique()
route_ids = trips_df[trips_df["trip_id"].isin(trip_ids)]["route_id"].unique()
routes_to_show = routes_df[routes_df["route_id"].isin(route_ids)]

route_selection = st.selectbox("Select a Route", routes_to_show["route_id"])

# --- Direction Filter ---
directions = trips_df[trips_df["route_id"] == route_selection]["direction_id"].dropna().unique()
direction_selection = st.radio("Select Direction", options=directions, format_func=lambda d: "Outbound" if d == "0" else "Inbound")

# --- Select Representative Trip for Shape and Stops ---
selected_trip = trips_df[(trips_df["route_id"] == route_selection) & (trips_df["direction_id"] == str(direction_selection))].head(1)

if not selected_trip.empty:
    shape_id = selected_trip["shape_id"].values[0]
    trip_id = selected_trip["trip_id"].values[0]

    # --- Get Shape Data ---
    route_shapes = shapes_df[shapes_df["shape_id"] == shape_id].copy().sort_values("shape_pt_sequence")
    route_shapes["next_lat"] = route_shapes["shape_pt_lat"].shift(-1)
    route_shapes["next_lon"] = route_shapes["shape_pt_lon"].shift(-1)
    route_shapes = route_shapes.dropna(subset=["next_lat", "next_lon"])

    # --- Get Stops ---
    stop_times = stop_times_df[stop_times_df["trip_id"] == trip_id].copy().sort_values("stop_sequence")
    stop_times["stop_sequence_text"] = "Stop " + stop_times["stop_sequence"].astype(str)
    stops = stop_times.merge(stops_df, on="stop_id", how="left")

    # --- Layers ---
    line_layer = pdk.Layer(
        "LineLayer",
        data=route_shapes,
        get_source_position=["shape_pt_lon", "shape_pt_lat"],
        get_target_position=["next_lon", "next_lat"],
        get_color=[0, 0, 255],
        get_width=5,
        pickable=True
    )

    stop_layer = pdk.Layer(
        "ScatterplotLayer",
        data=stops,
        get_position=["stop_lon", "stop_lat"],
        get_radius=80,
        get_fill_color=[0, 0, 255],
        pickable=True
    )

    label_layer = pdk.Layer(
        "TextLayer",
        data=stops,
        get_position=["stop_lon", "stop_lat"],
        get_text="stop_sequence_text",
        get_size=14,
        get_color=[255, 255, 255],
        get_alignment_baseline="'center'",
        pickable=False
    )

    # --- View State ---
    view_state = pdk.ViewState(
        latitude=route_shapes["shape_pt_lat"].mean(),
        longitude=route_shapes["shape_pt_lon"].mean(),
        zoom=12,
        pitch=0
    )

    # --- Display Map ---
    st.pydeck_chart(pdk.Deck(
        layers=[line_layer, stop_layer, label_layer],
        initial_view_state=view_state,
        tooltip={"text": "{stop_name} (Stop #{stop_sequence})"}
    ))

else:
    st.warning("No trips found for selected route and direction.")
