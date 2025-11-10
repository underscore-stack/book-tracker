# app.py — Clean, minimal library + analytics view

import os
from datetime import datetime
from collections import defaultdict
import streamlit as st
from covers_google import get_cached_or_drive_cover
from db_google import get_all_books
from charts_view import show_charts

# --- Page setup ---
st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

# --- Load books ---
try:
    books = get_all_books()
except Exception as e:
    st.error(f"⚠️ Could not load books: {e}")
    st.stop()

if not books:
    st.info("No books found in your Google Sheet.")
    st.stop()

# --- Library view ---
st.header("📖 Library")

months = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}

# Group books by year/month
grouped = defaultdict(lambda: defaultdict(list))
for b in books:
    date_str = b.get("date_finished", "")
    if not date_str or "-" not in date_str:
        continue
    year, month = date_str.split("-")[:2]
    grouped[year][month].append(b)

# Find most recent month
try:
    most_recent = max(
        datetime.strptime(b["date_finished"], "%Y-%m")
        for b in books
        if b.get("date_finished") and "-" in b["date_finished"]
    )
    most_recent_year = str(most_recent.year)
    most_recent_month = most_recent.strftime("%m")
except Exception:
    most_recent_year = most_recent_month = None

# Render grouped accordions
for year in sorted(grouped.keys(), reverse=True):
    year_total = sum(len(v) for v in grouped[year].values())
    with st.expander(f"📅 {year} ({year_total} books)", expanded=(year == most_recent_year)):
        for month_code in sorted(grouped[year].keys(), reverse=True):
            month_books = grouped[year][month_code]
            month_name = months.get(month_code, month_code)
            month_label = f"{month_name} ({len(month_books)} books)"

            is_recent = (year == most_recent_year and month_code == most_recent_month)

            with st.expander(month_label, expanded=is_recent):
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

# --- Charts (imported separately) ---
show_charts(books)
