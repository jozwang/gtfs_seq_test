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
    # --- LIVE CLOCK (Corrected Version) ---
    initial_time = datetime.now(BRISBANE_TZ)
    tz_string = BRISBANE_TZ.zone
    
    # Define the HTML and JS for the clock
    clock_html = f"""
    <div style="text-align: center;">
        <p style="font-size: 0.8rem; margin-bottom: 0px; color: rgba(49, 51, 63, 0.6);">Current Time</p>
        <h1 id="clock" style="font-weight: 600; font-size: 1.75rem; color: rgb(49, 51, 63); letter-spacing: -0.025rem; margin-top: 0px;">
            {initial_time.strftime('%I:%M:%S %p')} 
        </h1>
        <p style="font-size: 1rem; margin-top: 0.2rem;">{initial_time.strftime('%A, %d %B %Y')}</p>
    </div>
    <script>
    function updateClock() {{
        const clockElement = document.getElementById('clock');
        if (clockElement) {{
            const options = {{
                timeZone: '{tz_string}',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: true
            }};
            const timeString = new Date().toLocaleTimeString('en-AU', options);
            clockElement.innerHTML = timeString;
        }}
    }}
    // Update the clock every second
    setInterval(updateClock, 1000);
    </script>
    """
    st.markdown(clock_html, unsafe_allow_html=True)


# --- Map rendering ---
# (The rest of the script remains the same)
