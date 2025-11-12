# app.py — confirmed no expanders anywhere

import os
from datetime import datetime
from collections import defaultdict
import streamlit as st
from db_google import get_all_books
from covers_google import get_cached_or_drive_cover
from charts_view import show_charts  # keep commented until error gone

st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

# ---------- Load data ----------
try:
    books = get_all_books()
except Exception as e:
    st.error(f"⚠️ Could not load books: {e}")
    st.stop()

if not books:
    st.info("No books found in your Google Sheet.")
    st.stop()

# ---------- Library ----------
st.header("📖 Library")

MONTHS = {
    "01": "January","02": "February","03": "March","04": "April",
    "05": "May","06": "June","07": "July","08": "August",
    "09": "September","10": "October","11": "November","12": "December"
}

# Group by year/month
grouped = defaultdict(lambda: defaultdict(list))
for b in books:
    d = b.get("date_finished", "")
    if d and "-" in d:
        y, m = d.split("-")[:2]
        grouped[y][m].append(b)

# Find most recent
try:
    mr = max(
        datetime.strptime(b["date_finished"], "%Y-%m")
        for b in books if b.get("date_finished") and "-" in b["date_finished"]
    )
    RECENT_Y, RECENT_M = str(mr.year), mr.strftime("%m")
except Exception:
    RECENT_Y = RECENT_M = None

# Helper toggle (no expanders)
def toggle(label: str, key: str, default=False):
    if key not in st.session_state:
        st.session_state[key] = default
    cols = st.columns([0.05, 0.95])
    with cols[0]:
        symbol = "▼" if st.session_state[key] else "▶"
        if st.button(symbol, key=f"btn_{key}", help="Expand / collapse"):
            st.session_state[key] = not st.session_state[key]
            st.rerun()
    with cols[1]:
        st.markdown(f"**{label}**")
    st.markdown("<hr style='margin:2px 0;'>", unsafe_allow_html=True)

# Render library
for y in sorted(grouped.keys(), reverse=True):
    year_total = sum(len(v) for v in grouped[y].values())
    y_key = f"year_{y}"
    toggle(f"📅 {y} ({year_total} books)", y_key, default=(y == RECENT_Y))

    if st.session_state[y_key]:
        for m in sorted(grouped[y].keys(), reverse=True):
            m_key = f"month_{y}_{m}"
            month_books = grouped[y][m]
            label = f"{MONTHS.get(m, m)} ({len(month_books)} books)"
            toggle(label, m_key, default=(y == RECENT_Y and m == RECENT_M))

            if st.session_state[m_key]:
                for b in month_books:
                    cols = st.columns([1, 5])
                    with cols[0]:
                        cover = get_cached_or_drive_cover(b)
                        if isinstance(cover, str) and os.path.exists(cover):
                            st.image(cover, width=60)
                        else:
                            st.caption("No cover")
                    with cols[1]:
                        st.markdown(f"**{b.get('title','Untitled')}**  \n*{b.get('author','Unknown')}*")
                        st.caption(
                            f"{b.get('publisher','')} — {b.get('pub_year','')} — {b.get('pages','')} pages"
                        )

show_charts(books)
