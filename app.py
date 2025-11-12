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
    
# ---------- Session for detail view ----------
if "selected_book" not in st.session_state:
    st.session_state["selected_book"] = None
    
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

# ---------- Library structure ----------
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
                    book_id = b.get("id")
                    cols = st.columns([1, 5])
                    with cols[0]:
                        cover = get_cached_or_drive_cover(b)
                        if isinstance(cover, str) and os.path.exists(cover):
                            if st.button("🖼️", key=f"cover_btn_{book_id}", help="Open book details"):
                                st.session_state["selected_book"] = b
                                st.rerun()
                            st.image(cover, width=60)
                        else:
                            st.caption("No cover")
                    with cols[1]:
                        title = b.get("title", "Untitled")
                        author = b.get("author", "Unknown")
                        if st.button(title, key=f"title_btn_{book_id}", help="Open book details"):
                            st.session_state["selected_book"] = b
                            st.rerun()
                        st.caption(f"*{author}*")


# ---------- Book detail view ----------
if st.session_state["selected_book"]:
    b = st.session_state["selected_book"]
    st.divider()
    st.subheader(f"📖 {b.get('title','Untitled')}")
    st.caption(f"by {b.get('author','Unknown')}")

    cols = st.columns([1, 3])
    with cols[0]:
        cover = get_cached_or_drive_cover(b)
        if isinstance(cover, str) and os.path.exists(cover):
            st.image(cover, width=250)
        else:
            st.caption("No cover available")

    with cols[1]:
        st.markdown("### Book Details")
        st.markdown(f"**Publisher:** {b.get('publisher','')}")
        st.markdown(f"**Publication Year:** {b.get('pub_year','')}")
        st.markdown(f"**Pages:** {b.get('pages','')}")
        st.markdown(f"**Genre:** {b.get('genre','')}")
        st.markdown(f"**Fiction/Non-fiction:** {b.get('fiction_nonfiction','')}")
        st.markdown(f"**Author Gender:** {b.get('author_gender','')}")
        st.markdown(f"**Tags:** {b.get('tags','')}")
        st.markdown(f"**Date Finished:** {b.get('date_finished','')}")
        st.markdown(f"**ISBN:** {b.get('isbn','')}")
        st.markdown(f"**Word Count:** {b.get('word_count','')}")
        st.markdown(f"**OpenLibrary ID:** {b.get('openlibrary_id','')}")

    if st.button("⬅️ Back to Library"):
        st.session_state["selected_book"] = None
        st.rerun()

show_charts(books)
