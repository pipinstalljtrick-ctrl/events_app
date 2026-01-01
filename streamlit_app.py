"""
Local Events Dashboard (ZIP-based)
Aggregates events from Meetup (scrape), Eventbrite, and Ticketmaster
with inputs for ZIP code, radius, and date range; shows calendar, list, map, and details.
"""

import streamlit as st
from datetime import datetime, timedelta
import folium
from streamlit_folium import st_folium
import pandas as pd
from typing import List
import textwrap
import calendar as cal_module
from urllib.parse import quote_plus

from events_service import aggregate_events, Event
from dotenv import load_dotenv
import os

st.set_page_config(
    page_title="Local Events Calendar",
    page_icon="📅",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    :root {
        --bg: #fafafa;
        --card-bg: #ffffff;
        --text: #111111;
        --muted: #777777;
        --accent: #ff3366;
        --ring1: #ff9a9e;
        --ring2: #fad0c4;
    }
    * { box-sizing: border-box; }
    body { background: var(--bg); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    .block-container { padding-top: 0.25rem; padding-left: 8px; padding-right: 8px; max-width: 100%; }
    h1, h2, h3, p { color: var(--text); }

    /* Top nav hidden to remove cut-off banner */
    .ig-nav { display:none; }
    .ig-brand { font-weight: 800; letter-spacing: 0.8px; font-size: 20px; display:flex; align-items:center; gap:10px; }
    .ig-actions { display:flex; gap:10px; }
    .cigarette { width: 42px; height: 20px; }
    .cigarette .body { fill: #e6e6e6; }
    .cigarette .tip { fill: var(--accent); }
    .cigarette .smoke { stroke: var(--muted); stroke-width: 2; fill: none; opacity: 0.6; }
    .brand-title { display:flex; align-items:center; gap:14px; font-weight:900; font-size: clamp(24px, 5vw, 40px); letter-spacing:1.2px; margin: 10px 0 16px; }
    .brand-title .wordmark { background: linear-gradient(90deg, var(--accent), var(--ring1)); -webkit-background-clip: text; background-clip: text; color: transparent; }
    .brand-title .cigarette { width: clamp(44px, 7vw, 68px); height: clamp(18px, 3vw, 26px); filter: drop-shadow(0 2px 4px rgba(0,0,0,0.12)); }

    /* Stories row */
    .stories { display:flex; gap:12px; overflow-x:auto; padding:8px 4px; }
    .stories .stButton>button { border-radius:999px; width:64px; height:64px; padding:0; border: 3px solid; border-color: var(--ring1); background: var(--card-bg); box-shadow: 0 2px 6px rgba(0,0,0,0.08); font-weight:700; color: var(--text); }
    .story-label { text-align:center; font-size:12px; color: var(--muted); margin-top:4px; }

    /* Feed card */
    .post { background: var(--card-bg); border-radius:12px; box-shadow: 0 3px 8px rgba(0,0,0,0.06); overflow:hidden; margin: 12px 0; border: 1px solid #eee; }
    .post-img { width:100%; height: clamp(160px, 35vh, 280px); object-fit:cover; background: linear-gradient(135deg, #e0e0e0, #f0f0f0); }
    .post-body { padding:12px; }
    .post-title { font-size: clamp(14px, 2.5vw, 16px); font-weight:700; overflow-wrap:anywhere; }
    .pill { display:inline-block; padding:4px 8px; border-radius:999px; background:#f6f6f6; color: var(--muted); font-size: clamp(10px, 1.8vw, 12px); margin-right:6px; }
    .post-actions { display:flex; justify-content:flex-end; padding:8px 12px; border-top:1px solid #f0f0f0; }
    .link { color: var(--accent); font-weight:600; text-decoration:none; }

    /* Compact controls */
        .stButton>button { padding: 0.5rem 0.8rem; font-size: 1rem; min-height: 44px; }
    .stTabs { margin-top: 0.25rem; }
    h2, h3 { margin: 0.25rem 0; }

    /* Tabs wrap when cramped */
    .stTabs [role="tablist"] { display:flex; flex-wrap: wrap; gap:8px; }
    .stTabs [role="tab"] { flex: 1 1 140px; }

        /* iPhone/iOS mobile optimizations */
        @media (max-width: 480px) {
            /* Stack Streamlit columns */
            [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; display: block !important; }
            /* Non-sticky nav on mobile */
            .ig-nav { position: static; padding: 6px 8px; }
            /* Larger touch targets */
            .stButton>button { padding: 0.7rem 1rem; font-size: 1.05rem; min-height: 48px; }
            /* Card/image sizing */
            .post-img { height: clamp(140px, 30vh, 220px); }
            .pill { font-size: 11px; padding: 3px 6px; }
            /* Brand sizing on mobile */
            .brand-title { letter-spacing:0.8px; gap:10px; }
            /* Tabs can scroll if needed */
            .stTabs [role="tablist"] { overflow-x: auto; white-space: nowrap; }
        }
</style>
""", unsafe_allow_html=True)

load_dotenv()

@st.cache_data(ttl=7200)
def get_events(zip_code: str, radius_miles: int, start_date: datetime, end_date: datetime, tm_key: str) -> List[Event]:
    return aggregate_events(zip_code, radius_miles, start_date, end_date, tm_key)

st.markdown("""
<div class="ig-nav">
    <div class="ig-brand">
        EventMax
        <svg class="cigarette" viewBox="0 0 64 24" aria-hidden="true">
            <rect class="body" x="2" y="8" width="46" height="8" rx="4" />
            <rect class="tip" x="48" y="8" width="14" height="8" rx="4" />
            <path class="smoke" d="M12 6 C 20 2, 28 2, 34 6" />
        </svg>
    </div>
    <div class="ig-actions">📍 🔍 ❤️</div>
    <div></div>
</div>
""", unsafe_allow_html=True)

# Inline brand header directly above inputs
st.markdown("""
<div class="brand-title">
    <span class="wordmark">EventMax</span>
    <svg class="cigarette" viewBox="0 0 64 24" aria-hidden="true">
        <rect class="body" x="2" y="8" width="46" height="8" rx="4" />
        <rect class="tip" x="48" y="8" width="14" height="8" rx="4" />
        <path class="smoke" d="M12 6 C 20 2, 28 2, 34 6" />
    </svg>
</div>
""", unsafe_allow_html=True)

colA, colB = st.columns([2,1])
with colA:
    zip_code = st.text_input("ZIP Code", value="01907")
with colB:
    radius = st.slider("Radius (miles)", min_value=1, max_value=25, value=15)

tm_key = os.getenv("TICKETMASTER_API_KEY", "")

refresh = st.button("🔄 Refresh events")
if refresh:
    st.cache_data.clear()

# Month navigation state
def _add_months(dt: datetime, n: int) -> datetime:
    y = dt.year + ((dt.month - 1 + n) // 12)
    m = ((dt.month - 1 + n) % 12) + 1
    return datetime(y, m, 1)

if 'view_month' not in st.session_state:
    now = datetime.now()
    st.session_state.view_month = datetime(now.year, now.month, 1)

# Month navigation (arrows)
nav_left, nav_center, nav_right = st.columns([1, 6, 1])
with nav_left:
    prev_clicked = st.button("◀", key="prev_month", help="Previous month", use_container_width=True)
with nav_right:
    next_clicked = st.button("▶", key="next_month", help="Next month", use_container_width=True)

if prev_clicked:
    st.session_state.view_month = _add_months(st.session_state.view_month, -1)
    st.session_state.selected_day = None
if next_clicked:
    st.session_state.view_month = _add_months(st.session_state.view_month, +1)
    st.session_state.selected_day = None

# Load events for month-only range (default behavior)
start_date_api = st.session_state.view_month
last_day = cal_module.monthrange(start_date_api.year, start_date_api.month)[1]
end_date_api = datetime(start_date_api.year, start_date_api.month, last_day)
events = get_events(zip_code, radius, start_date_api, end_date_api, tm_key)

st.divider()

if not events:
    st.warning("⚠️ No events found. Try refreshing soon.")
    st.stop()

selected_year = st.session_state.view_month.year
selected_month = st.session_state.view_month.month
month_label = datetime(selected_year, selected_month, 1).strftime('%B %Y')
with nav_center:
    st.subheader(f"📆 {month_label}")

month_events = [e for e in events if e.date.year == selected_year and e.date.month == selected_month]

# Group events by day
events_by_day = {}
for evt in month_events:
    day = evt.date.day
    if day not in events_by_day:
        events_by_day[day] = []
    events_by_day[day].append(evt)

# Calendar grid data
cal = cal_module.monthcalendar(selected_year, selected_month)

# Initialize session state for selected day
if 'selected_day' not in st.session_state:
    st.session_state.selected_day = None

# Date dropdown instead of calendar grid
available_days = sorted(events_by_day.keys())
selected_choice = st.selectbox(
    "Select date",
    [None] + available_days,
    format_func=lambda d: (
        "All Month" if d is None else f"{datetime(selected_year, selected_month, d).strftime('%a, %b %d')} ({len(events_by_day[d])})"
    ),
    index=0,
    key="selected_day",
)

# Display events for selected day or all month events
if st.session_state.selected_day and st.session_state.selected_day in events_by_day:
    selected_events = events_by_day[st.session_state.selected_day]
    day_date = datetime(selected_year, selected_month, st.session_state.selected_day)
    st.subheader(f"📌 Events on {day_date.strftime('%A, %B %d, %Y')}")
else:
    selected_events = month_events
    st.subheader(f"📅 All Events in {datetime(selected_year, selected_month, 1).strftime('%B %Y')}")

# Stories-style quick day selector removed per request

    if selected_events:
        # Sort by price: cheapest first; unknown price last
        def _price_key(e):
            pm = getattr(e, 'price_min', None)
            return pm if pm is not None else float('inf')
        sorted_events = sorted(selected_events, key=_price_key)
        tab1, tab2, tab3 = st.tabs(["📰 Feed", "🗺️ Map", "📊 Table"])
        with tab1:
                        for evt in sorted_events:
                                img_html = f"<img class='post-img' src='{evt.image_url}' alt='event image'/>" if getattr(evt, 'image_url', '') else "<div class='post-img'></div>"
                                cur = getattr(evt, 'currency', '')
                                sym = '$' if cur == 'USD' else ''
                                price_label = ''
                                pm = getattr(evt, 'price_min', None)
                                px = getattr(evt, 'price_max', None)
                                if pm is not None and px is not None and px != pm:
                                        price_label = f"{sym}{pm:.0f}-{sym}{px:.0f}"
                                elif pm is not None:
                                        price_label = f"{sym}{pm:.0f}"
                                price_html = f"<span class='pill'>💲 {price_label}</span>" if price_label else ""
                                card_html = textwrap.dedent(f"""
                                <div class="post">
                                {img_html}
                                <div class="post-body">
                                <div class="post-title">{evt.title}</div>
                                <div style="margin-top:6px;">
                                <span class="pill">{evt.date.strftime('%b %d')}</span>
                                <span class="pill">{evt.date.strftime('%I:%M %p')}</span>
                                <span class="pill">{evt.location}</span>
                                {price_html}
                                </div>
                                </div>
                                <div class="post-actions">
                                <a class="link" href="https://www.google.com/search?q={quote_plus(' '.join([evt.title, evt.date.strftime('%b %d, %Y'), evt.location]).strip())}" target="_blank">View details</a>
                                </div>
                                </div>
                                """)
                                st.markdown(card_html, unsafe_allow_html=True)
        with tab2:
            m = folium.Map(location=[42.4825, -70.8800], zoom_start=13, tiles='OpenStreetMap')
            for evt in sorted_events:
                folium.Marker(
                    location=[evt.latitude, evt.longitude],
                    popup=folium.Popup(
                        f"""
                        <b>{evt.title}</b><br>
                        {evt.date.strftime('%b %d, %Y %I:%M %p')}<br>
                        {evt.location}<br>
                        <a href='https://www.google.com/search?q={quote_plus(' '.join([evt.title, evt.date.strftime('%b %d, %Y'), evt.location]).strip())}' target='_blank'>Search Event</a>
                        """,
                        max_width=250
                    ),
                    tooltip=evt.title,
                    icon=folium.Icon(color='red', icon='calendar')
                ).add_to(m)
            st_folium(m, use_container_width=True, height=480)
        with tab3:
            df_data = []
            for evt in sorted_events:
                cur = getattr(evt, 'currency', '')
                sym = '$' if cur == 'USD' else ''
                pm = getattr(evt, 'price_min', None)
                px = getattr(evt, 'price_max', None)
                if pm is not None and px is not None and px != pm:
                    price_text = f"{sym}{pm:.0f}-{sym}{px:.0f}"
                elif pm is not None:
                    price_text = f"{sym}{pm:.0f}"
                else:
                    price_text = ""
                df_data.append({
                    'Event': evt.title,
                    'Date': evt.date.strftime('%m/%d/%Y'),
                    'Time': evt.date.strftime('%I:%M %p'),
                    'Location': evt.location,
                    'Price': price_text,
                    'Link': f"[Search](https://www.google.com/search?q={quote_plus(' '.join([evt.title, evt.date.strftime('%b %d, %Y'), evt.location]).strip())})"
                })
            df = pd.DataFrame(df_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No events scheduled for this selection.")

st.divider()

# Footer
st.caption(f"🔄 Updated: {datetime.now().strftime('%I:%M %p on %B %d, %Y')} | Source: Ticketmaster")
