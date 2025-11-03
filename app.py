import json
import os
import re
from collections import defaultdict
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from covers_google import get_cached_or_drive_cover, save_cover_to_drive
from db_google import add_book, delete_book, get_all_books, update_book_metadata_full
from enrichment import enrich_book_metadata
from openlibrary_local import (
    fetch_editions_for_work,
    fetch_editions_for_work_raw,
    fetch_detailed_metadata,
    search_books,
)

st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

def extract_book_fields(book):
    """Safely extract isbn and cover_url from any book-like object."""
    def safe_get(obj, key):
        # Try .key, then ['key'], else return empty string
        try:
            return getattr(obj, key)
        except AttributeError:
            try:
                return obj[key]
            except Exception:
                return ""

    return {
        "isbn": str(safe_get(book, "isbn") or "").strip(),
        "cover_url": str(safe_get(book, "cover_url") or "").strip(),
    }

def fix_drive_link(url: str) -> str:
    """Convert a Google Drive link to an embeddable thumbnail link."""
    if not url:
        return url
    if "drive.google.com" in url and "id=" in url:
        file_id_match = re.search(r"id=([\w-]+)", url)
        if file_id_match:
            fid = file_id_match.group(1)
            return f"https://drive.google.com/thumbnail?id={fid}&sz=w800"
    return url

# Load books (best-effort)
try:
    books = get_all_books()
except Exception as exc:  # pragma: no cover - runtime guard
    st.warning(f"⚠️ Could not load books yet: {exc}")
    books = []

# Show transient messages
if st.session_state.get("edit_message"):
    st.success(st.session_state.edit_message)
    st.session_state.edit_message = None

if st.session_state.get("deleted_message"):
    st.success(st.session_state.deleted_message)
    st.session_state.deleted_message = None

# --- Search section ---
st.header("🔎 Search for a book to add")
query = st.text_input("Enter book title or author")

if query:
    results = search_books(query)
    for idx, book in enumerate(results):
        with st.expander(f"**{book.get('title','Untitled')}** by {book.get('author','')}"):
            if st.button("📚 View Editions", key=f"editions_{idx}"):
                st.session_state[f"selected_work_{idx}"] = book.get("openlibrary_id")

            selected_work = st.session_state.get(f"selected_work_{idx}")
            if selected_work and selected_work == book.get("openlibrary_id"):
                # fetch editions
                editions = fetch_editions_for_work(book.get("openlibrary_id"))
                if editions:
                    for ed in editions:
                        with st.container():
                            cols = st.columns([1, 4])
                            with cols[0]:
                                cu = ed.get("cover_url", "")
                                if isinstance(cu, str) and cu.startswith("http") and "/b/id/0-" not in cu:
                                    st.image(cu, width=80)
                                else:
                                    st.caption("No cover")
                            with cols[1]:
                                st.markdown(f"**Publisher:** {ed.get('publisher','')}")
                                st.markdown(f"**Published:** {ed.get('publish_date','')}")
                                st.markdown(f"**ISBN:** {ed.get('isbn','')}")
                                if st.button("➕ Use This Edition", key=f"use_{idx}_{ed.get('openlibrary_id','')}"):
                                    # Save editable fields to enriched
                                    st.session_state[f"enriched_{idx}"] = {
                                        "publisher": ed.get("publisher", ""),
                                        "pub_year": ed.get("publish_year"),
                                        "pages": ed.get("pages"),
                                        "genre": "",
                                        "author_gender": "",
                                        "fiction_nonfiction": "",
                                        "tags": [],
                                    }

                                    # Persist non-editable fields separately
                                    st.session_state[f"isbn_{idx}"] = ed.get("isbn", "")
                                    st.session_state[f"cover_{idx}"] = ed.get("cover_url", "")

                                    # Also override displayed book info
                                    book["cover_url"] = ed.get("cover_url", "")
                                    book["publisher"] = ed.get("publisher", "")
                                    book["pub_year"] = ed.get("publish_year")
                                    book["pages"] = ed.get("pages")
                                    book["isbn"] = ed.get("isbn", "")
                                    st.success("✔️ Edition selected. You can now use the form below.")

                            # offer debug / raw view for this work
                            with st.expander("View editions"):
                                work_olid = book.get("openlibrary_id")
                                dbg = st.checkbox("Show raw OpenLibrary response", value=False, key=f"dbg_{work_olid}_{idx}")
                                if dbg:
                                    url, status, raw = fetch_editions_for_work_raw(work_olid, limit=50)
                                    st.write("**Request URL:**", url)
                                    st.write("**HTTP status:**", status)
                                    st.json(raw)
                                    st.download_button(
                                        "Download raw JSON",
                                        data=json.dumps(raw, indent=2),
                                        file_name=f"openlibrary_editions_{work_olid}.json",
                                        mime="application/json",
                                    )

                                ed_list, dbg_info = fetch_editions_for_work(work_olid, limit=50, debug=True)
                                if dbg:
                                    st.write("**Normalized fetch URL:**", dbg_info.get("url"))
                                    st.write("**Normalized HTTP status:**", dbg_info.get("status"))

                else:
                    st.warning("No English editions found.")

            # Enrich
            if st.button(f"🔍 Enrich", key=f"enrich_{idx}"):
                meta = st.session_state.get(f"enriched_{idx}", {})

                existing = {
                    "publisher": meta.get("publisher") or book.get("publisher"),
                    "pub_year": meta.get("pub_year") or book.get("pub_year"),
                    "pages": meta.get("pages") or book.get("pages"),
                    "isbn": book.get("isbn"),
                    "author_gender": meta.get("author_gender", ""),
                    "fiction_nonfiction": meta.get("fiction_nonfiction", ""),
                    "tags": meta.get("tags", []),
                    "cover_url": book.get("cover_url"),
                }
                enriched = enrich_book_metadata(book.get("title", ""), book.get("author", ""), book.get("isbn"), existing=existing)

                if "error" in enriched:
                    st.error(f"Enrichment failed: {enriched['error']}")
                else:
                    st.session_state[f"enriched_{idx}"] = enriched

            # Get enrichment metadata if available
            meta = st.session_state.get(f"enriched_{idx}", {})

            # Start the form inside the expander
            with st.form(key=f"form_{idx}"):
                isbn_val = st.session_state.get(f"isbn_{idx}", book.get("isbn", ""))
                cover_src = st.session_state.get(f"cover_{idx}", book.get("cover_url", ""))

                # Cache or download cover if possible
                local_cover = get_cached_or_drive_cover({"isbn": book.get("isbn", ""), "cover_url": book.get("cover_url", "")})

                if local_cover and os.path.exists(local_cover):
                    st.image(local_cover, use_container_width=True)
                else:
                    st.caption("No cover available")

                # Show metadata
                st.write(f"**Publisher:** {meta.get('publisher') or book.get('publisher', '')}")
                st.write(f"**Year:** {meta.get('pub_year') or book.get('pub_year', '')}")
                st.write(f"**Pages:** {meta.get('pages') or book.get('pages', '')}")
                st.write(f"**ISBN:** {st.session_state.get(f'isbn_{idx}', book.get('isbn', ''))}")
                st.write(f"**Genre:** {meta.get('genre', '')}")

                # Form inputs
                gender_options = ["", "Male", "Female", "Nonbinary", "Multiple", "Unknown"]
                author_gender = st.selectbox(
                    "Author Gender",
                    gender_options,
                    index=gender_options.index(meta.get("author_gender", "")) if meta.get("author_gender", "") in gender_options else 0,
                )

                fiction_options = ["", "Fiction", "Non-fiction"]
                fiction = st.selectbox(
                    "Fiction or Non-fiction",
                    fiction_options,
                    index=fiction_options.index(meta.get("fiction_nonfiction", "")) if meta.get("fiction_nonfiction", "") in fiction_options else 0,
                )

                raw_tags = meta.get("tags", [])
                # normalize to list[str]
                if raw_tags is None:
                    raw_tags = []
                elif isinstance(raw_tags, str):
                    raw_tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
                elif isinstance(raw_tags, (set, tuple)):
                    raw_tags = list(raw_tags)

                tags_default = ", ".join([str(t) for t in raw_tags])

                tags = st.text_input("Tags (comma-separated)", value=tags_default)
                date = st.date_input("Date Finished")

                submitted = st.form_submit_button("Add this book")

                if submitted:
                    isbn_val = st.session_state.get(f"isbn_{idx}", book.get("isbn", ""))
                    cover_src = book.get("cover_url", "")

                    # Try saving the cover to Drive
                    drive_url = ""
                    if cover_src and isbn_val:
                        drive_url = save_cover_to_drive(cover_src, isbn_val)
                        if drive_url:
                            cover_src = drive_url
                        else:
                            st.warning(f"Failed to upload cover for {isbn_val}; keeping original cover URL")

                    book_data = {
                        "title": book.get("title", ""),
                        "author": book.get("author", ""),
                        "publisher": meta.get("publisher") or book.get("publisher", ""),
                        "pub_year": meta.get("pub_year") or book.get("pub_year", ""),
                        "pages": meta.get("pages") or book.get("pages"),
                        "genre": meta.get("genre", ""),
                        "author_gender": author_gender,
                        "fiction_nonfiction": fiction,
                        "tags": tags,
                        "date_finished": date.strftime("%Y-%m"),
                        "cover_url": cover_src,
                        "openlibrary_id": book.get("openlibrary_id", ""),
                        "isbn": isbn_val,
                    }
                    book_data["word_count"] = book_data["pages"] * 250 if book_data["pages"] else None
                    add_book(book_data)
                    st.session_state.edit_message = f"Book '{book.get('title','Untitled')}' added!"
                    st.rerun()

# Library
st.markdown('<div class="library-container">', unsafe_allow_html=True)

st.header("📖 Your Library")
books = get_all_books()
filtered_books = []

if not books:
    st.info("No books saved yet.")
else:
    # Extract unique filter values
    dates = [b.get("date_finished") for b in books if b.get("date_finished") and "-" in b.get("date_finished")]
    years = sorted({d.split("-")[0] for d in dates})
    month_codes = sorted({d.split("-")[1] for d in dates if len(d.split("-")) > 1})
    months = {
        "01": "January",
        "02": "February",
        "03": "March",
        "04": "April",
        "05": "May",
        "06": "June",
        "07": "July",
        "08": "August",
        "09": "September",
        "10": "October",
        "11": "November",
        "12": "December",
    }

    # Session state defaults
    default_filters = {
        "selected_years": [],
        "selected_months": [],
        "fiction_filter": [],
        "gender_filter": [],
        "tag_filter": "",
        "search_query": "",
    }
    for key, val in default_filters.items():
        st.session_state.setdefault(key, val)

    # Sidebar filter controls
    st.sidebar.header("📊 Filter Your Library")
    if st.sidebar.button("🔄 Reset Filters"):
        for key, val in default_filters.items():
            st.session_state[key] = val

    st.session_state.selected_years = st.sidebar.multiselect("Year Finished", years)
    st.session_state.selected_months = st.sidebar.multiselect("Month Finished", [months[m] for m in month_codes if m in months])
    st.session_state.fiction_filter = st.sidebar.multiselect("Fiction / Non-fiction", ["Fiction", "Non-fiction"])
    gender_options = ["Male", "Female", "Nonbinary", "Multiple", "Unknown"]
    st.session_state.gender_filter = st.sidebar.multiselect("Author Gender", gender_options)
    st.sidebar.text_input("Tag contains...", key="tag_filter")
    st.sidebar.text_input("Search title or author", key="search_query")

    # Filter logic
    filtered_books = []
    for b in books:
        try:
            date_str = b.get("date_finished", "")
            if not date_str or "-" not in date_str:
                continue

            year, month = date_str.split("-")
            if month not in months:
                continue

            month_name = months[month]

            year_ok = not st.session_state.selected_years or year in st.session_state.selected_years
            month_ok = not st.session_state.selected_months or month_name in st.session_state.selected_months
            fiction_ok = not st.session_state.fiction_filter or b.get("fiction_nonfiction", "") in st.session_state.fiction_filter
            gender_ok = not st.session_state.gender_filter or b.get("author_gender", "") in st.session_state.gender_filter
            tag_ok = not st.session_state.tag_filter or st.session_state.tag_filter.lower() in (b.get("tags") or "").lower()
            search_query = st.session_state.get("search_query", "").strip().lower()
            search_ok = (
                not search_query
                or search_query in (b.get("title") or "").lower()
                or search_query in (b.get("author") or "").lower()
            )

            if year_ok and month_ok and fiction_ok and gender_ok and tag_ok and search_ok:
                filtered_books.append(b)

        except Exception as exc:
            st.warning(f"Skipping bad book entry: {b.get('title', 'Untitled')} — {exc}")

    st.subheader(f"📚 Showing {len(filtered_books)} book(s)")

st.markdown("</div>", unsafe_allow_html=True)

# Inline CSS (kept unchanged; consider moving to a static file)
st.markdown(
    """
<style>
/* (CSS omitted in this snippet for brevity — keep existing styles) */
</style>
""",
    unsafe_allow_html=True,
)

# Visualisations
if filtered_books:
    df = pd.DataFrame(filtered_books)[
        [
            "id",
            "title",
            "author",
            "publisher",
            "pub_year",
            "pages",
            "genre",
            "author_gender",
            "fiction_nonfiction",
            "tags",
            "date_finished",
            "cover_url",
            "openlibrary_id",
            "isbn",
            "word_count",
        ]
    ]

    df["ym"] = pd.to_datetime(df["date_finished"], format="%Y-%m", errors="coerce")
    df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
    df = df.dropna(subset=["ym", "pages"])  

    df["year"] = df["ym"].dt.year
    df["month"] = df["ym"].dt.strftime("%b")
    df["month_num"] = df["ym"].dt.month

    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    df["month"] = pd.Categorical(df["month"], categories=month_order, ordered=True)

    st.subheader("📈 Reading Analytics")

    with st.expander("📊 Show Analytics", expanded=True):
        # Pages per month + trendlines
        pages_by_month = (
            df.groupby(["year", "month", "month_num"], observed=True)
            .agg({"pages": "sum"})
            .reset_index()
            .dropna(subset=["month_num", "pages"])
        )
        pages_by_month = pages_by_month[pages_by_month["pages"] > 0]

        base = alt.Chart(pages_by_month).encode(
            x=alt.X(
                "month_num:Q",
                title="Month",
                scale=alt.Scale(domain=[1, 12]),
                axis=alt.Axis(
                    tickMinStep=1,
                    values=list(range(1, 13)),
                    labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]',
                ),
            ),
            y=alt.Y("pages:Q", title="Pages Read"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", "month:N", "pages:Q"],
        )
        combined = (
            base.mark_line(point=True)
            + base.transform_regression("month_num", "pages", groupby=["year"]).mark_line(strokeDash=[4, 2])
        ).properties(title="Pages Read per Month by Year").interactive()

        # Books read per month
        books_by_month = (
            df.groupby(["year", "month", "month_num"], observed=True)
            .size()
            .reset_index(name="count")
            .dropna(subset=["month_num", "count"])
        )
        books_by_month = books_by_month[books_by_month["count"] > 0]

        chart_books = (
            alt.Chart(books_by_month)
            .mark_bar()
            .encode(
                x=alt.X(
                    "month_num:Q",
                    title="Month",
                    scale=alt.Scale(domain=[1, 12]),
                    axis=alt.Axis(
                        tickMinStep=1,
                        values=list(range(1, 13)),
                        labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]',
                    ),
                ),
                y=alt.Y("count:Q", title="Books Read"),
                color=alt.Color("year:N", title="Year"),
                tooltip=["year:N", "month:N", "count:Q"],
            )
            .properties(title="Books Read per Month by Year")
        )

        # Cumulative books read
        cum_books = books_by_month.sort_values(["year", "month_num"])
        cum_books["cumulative"] = cum_books.groupby("year")["count"].cumsum()

        chart_cum_books = (
            alt.Chart(cum_books)
            .mark_line(point=True)
            .encode(
                x=alt.X(
                    "month_num:Q",
                    title="Month",
                    scale=alt.Scale(domain=[1, 12]),

