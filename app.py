# app.py — Clean library (no nested expanders) + charts call

import os
from datetime import datetime
from collections import defaultdict
import streamlit as st

from db_google import get_all_books
from covers_google import get_cached_or_drive_cover
from charts_view import show_charts  # keep your charts module separate

# ---------- Page ----------
st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

# ---------- Data ----------
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
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}

# Group by year/month quickly
grouped = defaultdict(lambda: defaultdict(list))
for b in books:
    d = b.get("date_finished", "")
    if d and "-" in d:
        y, m = d.split("-")[:2]
        grouped[y][m].append(b)

# Find most recent YM
try:
    most_recent = max(
        datetime.strptime(b["date_finished"], "%Y-%m")
        for b in books
        if b.get("date_finished") and "-" in b["date_finished"]
    )
    recent_y = str(most_recent.year)
    recent_m = most_recent.strftime("%m")
except Exception:
    recent_y = recent_m = None

# Toggle helpers (no expanders)
def toggle_row(label: str, state_key: str, default_open: bool = False):
    if state_key not in st.session_state:
        st.session_state[state_key] = default_open
    cols = st.columns([0.05, 0.95])
    with cols[0]:
        arrow = "▼" if st.session_state[state_key] else "▶"
        if st.button(arrow, key=f"btn_{state_key}", help="Expand / collapse"):
            st.session_state[state_key] = not st.session_state[state_key]
            st.rerun()
    with cols[1]:
        st.markdown(f"**{label}**")
    st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)

# Render years and months with toggle buttons
for y in sorted(grouped.keys(), reverse=True):
    year_total = sum(len(v) for v in grouped[y].values())
    y_key = f"year_{y}"
    toggle_row(f"📅 {y} ({year_total} books)", y_key, default_open=(y == recent_y))

    if st.session_state[y_key]:
        for m in sorted(grouped[y].keys(), reverse=True):
            month_books = grouped[y][m]
            m_key = f"month_{y}_{m}"
            month_label = f"{MONTHS.get(m, m)} ({len(month_books)} books)"
            toggle_row(month_label, m_key, default_open=(y == recent_y and m == recent_m))

            if st.session_state[m_key]:
                # Render book rows only when the month is open
                for b in month_books:
                    cols = st.columns([1, 5])
                    with cols[0]:
                        cover = get_cached_or_drive_cover(b)
                        if isinstance(cover, str) and os.path.exists(cover):
                            st.image(cover, width=60)
                        else:
                            st.caption("No cover")
                    with cols[1]:
                        title = b.get("title", "Untitled")
                        author = b.get("author", "Unknown")
                        publisher = b.get("publisher", "")
                        pub_year = b.get("pub_year", "")
                        pages = b.get("pages", "")
                        st.markdown(f"**{title}**  \n*{author}*")
                        st.caption(f"{publisher} — {pub_year} — {pages} pages")

# ---------- Charts ----------
# If your charts module still uses st.expander, it’s fine because we use no expanders above.
# If you prefer zero expanders everywhere, switch the expander in charts_view to a container/checkbox.
show_charts(books)
