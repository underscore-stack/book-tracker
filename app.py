import streamlit as st
import pandas as pd
import altair as alt
import os
from datetime import datetime
from db_google import get_all_books, add_book, update_book_metadata_full, delete_book
from openlibrary_local import search_books, fetch_detailed_metadata, fetch_editions_for_work 
from covers_google import save_cover_to_drive as save_cover, get_cached_or_drive_cover
from enrichment import enrich_book_metadata

st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

try:
    books = get_all_books()
except Exception as e:
    st.warning(f"⚠️ Could not load books yet: {e}")
    books = []

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
    if "drive.google.com" in url and "id=" in url:
        import re
        file_id_match = re.search(r"id=([\w-]+)", url)
        if file_id_match:
            fid = file_id_match.group(1)
            return f"https://drive.google.com/thumbnail?id={fid}&sz=w800"
    return url

# Show success messages
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
        with st.expander(f"**{book['title']}** by {book['author']}"):
            if st.button("📚 View Editions", key=f"editions_{idx}"):
                st.session_state[f"selected_work_{idx}"] = book["openlibrary_id"]
        
            selected_work = st.session_state.get(f"selected_work_{idx}")
            if selected_work == book["openlibrary_id"]:
                editions = fetch_editions_for_work(book["openlibrary_id"])
                if editions:
                    for ed in editions:
                        with st.container():
                            cols = st.columns([1, 4])
                            with cols[0]:
                                if ed["cover_url"]:
                                    st.image(ed["cover_url"], width=80)
                            with cols[1]:
                                st.markdown(f"**Publisher:** {ed['publisher']}")
                                st.markdown(f"**Published:** {ed['publish_date']}")
                                st.markdown(f"**ISBN:** {ed['isbn']}")
                                if st.button("➕ Use This Edition", key=f"use_{idx}_{ed['openlibrary_id']}"):
                                    # Save editable fields to enriched
                                    st.session_state[f"enriched_{idx}"] = {
                                        "publisher": ed.get("publisher", ""),
                                        "pub_year": ed.get("publish_year"),
                                        "pages": ed.get("pages"),
                                        "genre": "",
                                        "author_gender": "",
                                        "fiction_nonfiction": "",
                                        "tags": []
                                    }
                                
                                    # Persist non-editable fields separately
                                    book["isbn"] = ed.get("isbn", "")
                                    st.session_state[f"isbn_{idx}"] = ed.get("isbn", "")
                                    st.session_state[f"cover_{idx}"] = ed.get("cover_url", "")

                                    # Also override displayed book info
                                    book["cover_url"] = ed.get("cover_url", "")
                                    book["publisher"] = ed.get("publisher", "")
                                    book["pub_year"] = ed.get("publish_year")
                                    book["pages"] = ed.get("pages")
                                    book["isbn"] = ed.get("isbn", "")
                                    st.success("✔️ Edition selected. You can now use the form below.")

                else:
                    st.warning("No English editions found.")

            # Show Enrich button
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
                    "cover_url": book.get("cover_url")
                }
                enriched = enrich_book_metadata(book["title"], book["author"], book.get("isbn"), existing=existing)

                if "error" in enriched:
                    st.error(f"Enrichment failed: {enriched['error']}")
                else:
                    st.session_state[f"enriched_{idx}"] = enriched

            # Get enrichment metadata if available
            meta = st.session_state.get(f"enriched_{idx}", {})

            # Start the form inside the expander
            with st.form(key=f"form_{idx}"):

                # Safely extract cover + isbn
                isbn_val = st.session_state.get(f"isbn_{idx}", book.get("isbn", ""))
                cover_src = st.session_state.get(f"cover_{idx}", book.get("cover_url", ""))

                # Cache or download cover if possible
                local_cover = get_cached_or_drive_cover({
                    "isbn": str(isbn_val).strip(),
                    "cover_url": str(cover_src).strip()
                })

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
                author_gender = st.selectbox("Author Gender", gender_options,
                    index=gender_options.index(meta.get("author_gender", "")) if meta.get("author_gender", "") in gender_options else 0)

                fiction_options = ["", "Fiction", "Non-fiction"]
                fiction = st.selectbox("Fiction or Non-fiction", fiction_options,
                    index=fiction_options.index(meta.get("fiction_nonfiction", "")) if meta.get("fiction_nonfiction", "") in fiction_options else 0)

                tags = st.text_input("Tags (comma-separated)", value=", ".join(meta.get("tags", [])))
                date = st.date_input("Date Finished")

                submitted = st.form_submit_button("Add this book")

                if submitted:
                    isbn_val = st.session_state.get(f"isbn_{idx}", book.get("isbn", ""))
                    cover_src = book.get("cover_url", "")

                    # ✅ Try saving the cover to Drive
                    from covers_google import save_cover_to_drive
                    drive_url = ""
                    if cover_src and isbn_val:
                        drive_url = save_cover_to_drive(cover_src, isbn_val)
                        if drive_url:
                            cover_src = drive_url  # replace original link
                        else:
                            print(f"⚠️ Failed to upload {isbn_val}, keeping original cover URL")

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
                        # ✅ Save Drive URL if available
                        "cover_url": cover_src,
                        "openlibrary_id": book.get("openlibrary_id", ""),
                        "isbn": isbn_val
                    }
                    book_data["word_count"] = book_data["pages"] * 250 if book_data["pages"] else None
                    add_book(book_data)
                    st.session_state.edit_message = f"Book '{book['title']}' added!"
                    st.rerun()


st.markdown('<div class="library-container">', unsafe_allow_html=True)

# --- Library Filters + View ---
st.header("📖 Your Library")
books = get_all_books()
filtered_books = []

if not books:
    st.info("No books saved yet.")
else:
    # Extract unique filter values
    dates = [b["date_finished"] for b in books if b.get("date_finished") and "-" in b["date_finished"]]
    years = sorted({d.split("-")[0] for d in dates})
    month_codes = sorted({d.split("-")[1] for d in dates if len(d.split("-")) > 1})
    months = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December"
    }


    # Session state defaults
    default_filters = {
        "selected_year": "All",
        "selected_month": "All",
        "fiction_filter": "All",
        "gender_filter": "All",
        "tag_filter": ""
    }
    for key, val in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # Sidebar filter controls
    st.sidebar.header("📊 Filter Your Library")
    if st.sidebar.button("🔄 Reset Filters"):
        for key, val in default_filters.items():
            st.session_state.selected_years = []
            st.session_state.selected_months = []
            st.session_state.fiction_filter = []
            st.session_state.gender_filter = []
            st.session_state.tag_filter = ""

    st.session_state.selected_years = st.sidebar.multiselect(
        "Year Finished", years
    )

    st.session_state.selected_months = st.sidebar.multiselect(
        "Month Finished", [months[m] for m in month_codes]
    )
    st.session_state.fiction_filter = st.sidebar.multiselect(
        "Fiction / Non-fiction", ["Fiction", "Non-fiction"]
    )
    gender_options = ["Male", "Female", "Nonbinary", "Multiple", "Unknown"]
    st.session_state.gender_filter = st.sidebar.multiselect(
        "Author Gender", gender_options
    )
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
                not search_query or
                search_query in (b.get("title") or "").lower() or
                search_query in (b.get("author") or "").lower()
            )
    
            if year_ok and month_ok and fiction_ok and gender_ok and tag_ok and search_ok:
                filtered_books.append(b)
    
        except Exception as e:
            st.warning(f"Skipping bad book entry: {b.get('title', 'Untitled')} — {e}")

    st.subheader(f"📚 Showing {len(filtered_books)} book(s)")

from datetime import datetime

st.markdown('</div>', unsafe_allow_html=True)


st.markdown("""
<style>
/* Month titles: plain text, same scale as year headings */
.month-title {
    font-size: 1.05rem !important;
    font-weight: 500;
    margin-top: 0.1rem !important;
    margin-bottom: 0rem !important;
    padding-left: 0.25rem;
    color: #333;
}

/* Tighten column block spacing */
div[data-testid="stHorizontalBlock"] {
    margin-bottom: 0.15rem !important;
}
/* 1️⃣ Reduce button min-height & remove extra padding */
button[kind="secondary"], div[data-testid="stHorizontalBlock"] button {
    min-height: unset !important;
    padding-top: 0.15rem !important;
    padding-bottom: 0.15rem !important;
    height: auto !important;
}

/* 2️⃣ Remove vertical gap ONLY for collapsed month titles */
div[data-testid="stVerticalBlock"].st-emotion-cache-wfksaw:has(p.month-title) {
    gap: 0 !important;
}

/* 3️⃣ Vertically center month titles next to arrows */
.month-title {
    display: flex;
    align-items: center;       /* vertical centering */
    height: 1.8rem;            /* matches reduced button height */
    margin-top: 0 !important;
    margin-bottom: 0 !important;
    font-size: 1rem !important;
    font-weight: 400 !important;
    padding-left: 0.3rem;
    color: #333;
}

/* 4️⃣ When expanded (month open), reapply small bottom margin for breathing room */
div[data-testid="stVerticalBlock"].st-emotion-cache-wfksaw:has(div[data-testid="stImage"]) {
    gap: 0.4rem !important;
}

/* 5️⃣ Fine-tune the overall vertical rhythm for book rows */
div[data-testid="stHorizontalBlock"] {
    margin-bottom: 0.15rem !important;
}
/* Shrink and align book rows */
.book-title {
    font-size: 0.95rem !important;
    line-height: 1.2 !important;
}
.book-author {
    font-size: 0.85rem !important;
    color: #666 !important;
    line-height: 1.1 !important;
}

/* Shrink the image cell padding */
div[data-testid="stImage"] {
    margin-top: 0.15rem !important;
    margin-bottom: 0.15rem !important;
}
/* Match month headers to year headers */
h4 {
    font-size: 1.1rem !important;
    margin-top: 0.3rem !important;
    margin-bottom: 0.2rem !important;
}
/* Tighten vertical spacing between month rows */
div[data-testid="stHorizontalBlock"] {
    margin-bottom: 0.25rem !important;
}
.book-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.5rem;
    border-bottom: 1px solid #eee;
    cursor: pointer;
}
.book-info {
    flex-grow: 1;
    margin-left: 1rem;
}
.book-title {
    font-size: 18px;
    font-weight: bold;
    margin-bottom: 0.2rem;
}
.book-author {
    font-size: 14px;
    font-style: italic;
    color: #555;
    margin-bottom: 0.2rem;
}
.book-tags {
    font-size: 12px;
    color: #777;
}
.book-meta {
    font-size: 12px;
    color: #777;
    margin-top: 0.2rem;
}
.expanded-cover img {
    max-width: 80% !important;
}
.edit-delete-row button {
    margin-right: 0.5rem;
}
.custom-table {
    margin-left: auto;
    margin-right: auto;
    border-collapse: collapse;
    width: 75%;
    text-align: center;
    margin-bottom: 75px !important;
}
.custom-table th, .custom-table td {
    padding: 8px;
    border: 1px solid #ccc;
    text-align: center;
}
.custom-table th:first-child,
.custom-table td:first-child {
    text-align: center;
    white-space: nowrap;
}
/*size of expanded view cover
/*.library-container dic

/* Target the middle column in 3-column horizontal blocks */
.library-container div[data-testid="stHorizontalBlock"] > div.stColumn:nth-child(2) {
    flex: 1 1 50% !important;     /* width ratio */
    max-width: 50% !important;    /* prevents squeezing */
}

/* Optionally adjust first/last columns */
.library-container div[data-testid="stHorizontalBlock"] > div.stColumn:nth-child(1) {
    flex: 1 1 10% !important;
    max-width: 10% !important;
}
.library-container div[data-testid="stHorizontalBlock"] > div.stColumn:nth-child(3) {
    flex: 1 1 10% !important;
    max-width: 10% !important;
}
</style>
""", unsafe_allow_html=True)



#visualisations
if filtered_books:
    df = pd.DataFrame(filtered_books)[[
        "id", "title", "author", "publisher", "pub_year", "pages",
        "genre", "author_gender", "fiction_nonfiction", "tags",
        "date_finished", "cover_url", "openlibrary_id", "isbn", "word_count"
    ]]

    df["ym"] = pd.to_datetime(df["date_finished"], format="%Y-%m", errors="coerce")
    df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
    df = df.dropna(subset=["ym", "pages"])

    df["year"] = df["ym"].dt.year
    df["month"] = df["ym"].dt.strftime("%b")
    df["month_num"] = df["ym"].dt.month

    month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                   "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
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
            x=alt.X("month_num:Q", title="Month", scale=alt.Scale(domain=[1, 12]),
                    axis=alt.Axis(tickMinStep=1, values=list(range(1, 13)),
                                  labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]')),
            y=alt.Y("pages:Q", title="Pages Read"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", "month:N", "pages:Q"]
        )
        combined = (base.mark_line(point=True) +
                    base.transform_regression("month_num", "pages", groupby=["year"]).mark_line(strokeDash=[4, 2])
                    ).properties(title="Pages Read per Month by Year").interactive()

        # Books read per month
        books_by_month = (
            df.groupby(["year", "month", "month_num"], observed=True)
            .size()
            .reset_index(name="count")
            .dropna(subset=["month_num", "count"])
        )
        books_by_month = books_by_month[books_by_month["count"] > 0]

        chart_books = alt.Chart(books_by_month).mark_bar().encode(
            x=alt.X("month_num:Q", title="Month", scale=alt.Scale(domain=[1, 12]),
                    axis=alt.Axis(tickMinStep=1, values=list(range(1, 13)),
                                  labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]')),
            y=alt.Y("count:Q", title="Books Read"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", "month:N", "count:Q"]
        ).properties(title="Books Read per Month by Year")

        # Cumulative books read
        cum_books = books_by_month.sort_values(["year", "month_num"])
        cum_books["cumulative"] = cum_books.groupby("year")["count"].cumsum()

        chart_cum_books = alt.Chart(cum_books).mark_line(point=True).encode(
            x=alt.X("month_num:Q", title="Month", scale=alt.Scale(domain=[1, 12]),
                    axis=alt.Axis(tickMinStep=1, values=list(range(1, 13)),
                                  labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]')),
            y=alt.Y("cumulative:Q", title="Cumulative Books Read"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", "month:N", "cumulative:Q"]
        ).properties(title="Cumulative Books Read per Year")

        # Cumulative word count
        df["word_count"] = pd.to_numeric(df["word_count"], errors="coerce")
        df_valid_words = df.dropna(subset=["word_count", "ym"])
        df_valid_words["fake_date"] = df_valid_words["ym"].apply(lambda x: x.replace(year=2000))

        cum_words = (
            df_valid_words.groupby(["year", "fake_date"])
            .agg({"word_count": "sum"})
            .reset_index()
            .sort_values(["year", "fake_date"])
        )
        cum_words["cumulative"] = cum_words.groupby("year")["word_count"].cumsum()

        chart_cum_words = alt.Chart(cum_words).mark_line(interpolate="monotone").encode(
            x=alt.X(
                "month(fake_date):O",
                title="Month",
                sort=list(range(1, 13)),
                axis=alt.Axis(
                    labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]'
                )
            ),
            y=alt.Y("cumulative:Q", title="Cumulative Word Count"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", alt.Tooltip("fake_date:T", title="Date", format="%B"), "cumulative:Q"]
        ).properties(title="Cumulative Word Count (Jan–Dec, by Year)")


        # Fiction vs Non-fiction pie chart
        pie_data_f = df["fiction_nonfiction"].value_counts(normalize=False).reset_index()
        pie_data_f.columns = ["fiction_nonfiction", "count"]
        pie_data_f["percent"] = pie_data_f["count"] / pie_data_f["count"].sum() * 100
        
        base_f = alt.Chart(pie_data_f).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("fiction_nonfiction:N", title="Fiction/Non-fiction"),
            tooltip=["fiction_nonfiction:N", "count:Q"]  # only category + count
        )
        
        arc_f = base_f.mark_arc(innerRadius=30)
        text_f = base_f.mark_text(radius=75, fontSize=20, fontWeight="bold", fill="white").encode(
            text=alt.Text("percent:Q", format=".1f")
        ).transform_calculate(
            label="format(datum.percent, '.1f') + '%'"
        ).encode(text="label:N")
        
        pie_chart_f = (arc_f + text_f).properties(
            title={"text": "Fiction vs Non-fiction", "align": "center"}
        )
        
        
        # Author gender pie chart (omit 'Multiple')
        pie_data_g = df["author_gender"].value_counts(normalize=False).reset_index()
        pie_data_g.columns = ["author_gender", "count"]
        pie_data_g = pie_data_g[pie_data_g["author_gender"].str.lower() != "multiple"]  # filter out 'multiple'
        pie_data_g["percent"] = pie_data_g["count"] / pie_data_g["count"].sum() * 100
        
        base_g = alt.Chart(pie_data_g).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("author_gender:N", title="Gender"),
            tooltip=["author_gender:N", "count:Q"]
        )
        
        arc_g = base_g.mark_arc(innerRadius=30)
        text_g = base_g.mark_text(radius=75, fontSize=20, fontWeight="bold", fill="white").encode(
            text=alt.Text("percent:Q", format=".1f")
        ).transform_calculate(
            label="format(datum.percent, '.1f') + '%'"
        ).encode(text="label:N")
        
        pie_chart_g = (arc_g + text_g).properties(
            title={"text": "Gender Divide", "align": "center"}
        )


        # Display charts
        col1, col2 = st.columns(2)
        with col1:
            st.altair_chart(pie_chart_f, use_container_width=True)
        with col2:
            st.altair_chart(pie_chart_g, use_container_width=True)

        st.altair_chart(combined, use_container_width=True)
        st.altair_chart(chart_cum_words, use_container_width=True)
        st.altair_chart(chart_books, use_container_width=True)
        st.altair_chart(chart_cum_books, use_container_width=True)

else:
    st.info("No filtered books to display.")
    df = pd.DataFrame(columns=[
        "id", "title", "author", "publisher", "pub_year", "pages",
        "genre", "author_gender", "fiction_nonfiction", "tags",
        "date_finished", "cover_url", "openlibrary_id", "isbn", "word_count"
    ])


if not df.empty:
    try:
        # Ensure 'year' and 'pages' are numeric
        if "year" not in df.columns:
            df["ym"] = pd.to_datetime(df["date_finished"], format="%Y-%m", errors="coerce")
            df["year"] = df["ym"].dt.year

        df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
        df_valid = df.dropna(subset=["pages", "year"])
        df_valid["year"] = df_valid["year"].astype(int)

        def get_extreme_books(df, func):
            return (
                df.loc[df.groupby("year")["pages"].transform(func) == df["pages"]]
                .drop_duplicates("year")
                .set_index("year")
            )

        longest = get_extreme_books(df_valid, "max")
        shortest = get_extreme_books(df_valid, "min")

        summary = pd.DataFrame(index=sorted(df_valid["year"].unique()))
        summary["Longest Book"] = longest.apply(
            lambda x: f"<b>{x['title']}</b> by {x['author']} ({int(x['pages'])} pages)",
            axis=1
        )
        summary["Shortest Book"] = shortest.apply(
            lambda x: f"<b>{x['title']}</b> by {x['author']} ({int(x['pages'])} pages)",
            axis=1
        )
        summary.index.name = None

        st.markdown("<h4 style='margin-top: 2em;'>📏 Longest and Shortest Books per Year</h4>", unsafe_allow_html=True)
        st.markdown(
            summary.to_html(
                escape=False,
                index_names=True,
                classes="custom-table",
                border=1
            ),
            unsafe_allow_html=True
        )
    except Exception as e:
        st.error(f"Could not generate longest/shortest book table: {e}")

# --- Accordion Library View (grouped by year → month) ---
from collections import defaultdict
from datetime import datetime

months = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December"
}

filters_active = any([
    st.session_state.get("search_query"),
    st.session_state.get("selected_years"),
    st.session_state.get("selected_months"),
    st.session_state.get("fiction_filter"),
    st.session_state.get("gender_filter"),
    st.session_state.get("tag_filter"),
])

if filters_active:
    st.info("📋 Showing filtered results (accordion disabled).")
    books_to_show = filtered_books
else:
    books_to_show = filtered_books

if not books_to_show:
    st.info("No books match your criteria.")
else:
    grouped = defaultdict(lambda: defaultdict(list))
    for b in books_to_show:
        if not b.get("date_finished") or "-" not in b["date_finished"]:
            continue
        year, month = b["date_finished"].split("-")
        grouped[year][month].append(b)

# --- Cached cover lookup helper ---
@st.cache_data(show_spinner=False)
def get_cached_cover(isbn: str, cover_url: str):
    """
    Efficiently fetches or retrieves cached cover paths.
    Uses Streamlit caching to prevent repeated downloads or disk scans.
    """
    from covers_google import get_cached_or_drive_cover
    return get_cached_or_drive_cover({"isbn": isbn, "cover_url": cover_url})

for year in sorted(grouped.keys(), reverse=True):
    year_total = sum(len(v) for v in grouped[year].values())
    with st.expander(f"📅 {year} ({year_total} book{'s' if year_total != 1 else ''})",
                     expanded=(year == str(datetime.now().year))):

        # loop through months in reverse chronological order
        for month_code in sorted(grouped[year].keys(), reverse=True):
            month_books = grouped[year][month_code]
            month_name = months.get(month_code, month_code)
            month_label = f"{month_name} ({len(month_books)} book{'s' if len(month_books) != 1 else ''})"
        
            expanded_default = (
                year == str(datetime.now().year)
                and month_code == datetime.now().strftime("%m")
            )
        
            open_key = f"month_open_{year}_{month_code}"
            if open_key not in st.session_state:
                st.session_state[open_key] = expanded_default
        
            # --- Inline compact month header ---
            cols = st.columns([0.04, 0.96])
            with cols[0]:
                arrow = "▼" if st.session_state[open_key] else "▶"
                if st.button(arrow, key=f"toggle_{open_key}", help="Expand / collapse this month"):
                    st.session_state[open_key] = not st.session_state[open_key]
                    st.rerun()
            with cols[1]:
                st.markdown(
                    f"<p class='month-title'>{month_label}</p>",
                    unsafe_allow_html=True
                )
        
            # minimal spacing after header
            st.markdown("<div style='margin-top:-6px;'></div>", unsafe_allow_html=True)
        
            # --- Only render books if this month is open ---
            if not st.session_state[open_key]:
                st.markdown("<hr style='margin:4px 0;'>", unsafe_allow_html=True)
                continue
        
            # --- Lazy-load book list when open ---
            for b in month_books:
                book_id = b["id"]
                if f"edit_{book_id}" not in st.session_state:
                    st.session_state[f"edit_{book_id}"] = False
                if f"expanded_{book_id}" not in st.session_state:
                    st.session_state[f"expanded_{book_id}"] = False
        
                title = b.get("title", "")
                author = b.get("author", "")
                publisher = b.get("publisher", "")
                pub_year = b.get("pub_year", "")
                pages = b.get("pages", 0) or 0
                genre = b.get("genre", "")
                gender = b.get("author_gender", "")
                fiction = b.get("fiction_nonfiction", "")
                tags = b.get("tags", "")
                date_str = b.get("date_finished", "")
                cover_url = b.get("cover_url", "")
                openlibrary_id = b.get("openlibrary_id", "")
                isbn = b.get("isbn", "")
                word_count = b.get("word_count", "")
        
                try:
                    completed_date = datetime.strptime(date_str, "%Y-%m").strftime("%b-%Y")
                except:
                    completed_date = date_str
        
                cols = st.columns([1, 9, 1])
                with cols[0]:
                    local_cover = get_cached_cover(isbn, cover_url)
                    if local_cover and os.path.exists(local_cover):
                        st.image(local_cover, width=50)
                    else:
                        st.caption("No cover")
                with cols[1]:
                    st.markdown(f"<div class='book-title'>{title}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div class='book-author'>{author}</div>", unsafe_allow_html=True)
                with cols[2]:
                    if st.button("▶", key=f"expand_{book_id}_{year}_{month_code}"):
                        st.session_state[f"expanded_{book_id}"] = not st.session_state[f"expanded_{book_id}"]
        
                # --- Expanded book details ---
                if st.session_state[f"expanded_{book_id}"]:
                    layout_left, layout_right = st.columns([2, 1])
                    with layout_left:
                        st.markdown(f"**Completed date:** {completed_date}")
                        st.markdown(f"**Type:** {fiction}")
                        st.markdown(f"**Genre:** {genre}")
                        st.markdown(f"**Author Gender:** {gender}")
                        st.markdown(f"**Pages:** {pages}")
                        st.markdown(f"**Length (est.):** {word_count or '—'} words")
                        st.markdown(f"**Publisher:** {publisher}")
                        st.markdown(f"**ISBN:** {isbn}")
                        st.markdown(f"**OpenLibrary ID:** {openlibrary_id}")
                        st.markdown(f"**Tags:** {tags}")
        
                    with layout_right:
                        local_cover = get_cached_cover(isbn, cover_url)
                        if local_cover and os.path.exists(local_cover):
                            st.image(local_cover, use_container_width=True)
                        else:
                            st.caption("No cover available")
        
                    # --- Edit/Delete buttons ---
                    col1, col2 = st.columns([1, 1])
                    with col1:
                        if st.button("✏️ Edit Book", key=f"edit_btn_{book_id}_{year}_{month_code}"):
                            st.session_state[f"edit_{book_id}"] = True
                    with col2:
                        if st.button("🗑️ Delete Book", key=f"delete_{book_id}_{year}_{month_code}"):
                            delete_book(book_id)
                            st.session_state.deleted_message = f"Book '{title}' deleted"
                            st.rerun()



                        if st.session_state[f"edit_{book_id}"]:
                            with st.form(key=f"edit_form_{book_id}_{year}_{month_code}"):
                                meta = st.session_state.get(f"edit_enriched_{book_id}", {})

                                new_title = st.text_input("Title", value=title)
                                new_author = st.text_input("Author", value=author)
                                new_publisher = st.text_input("Publisher", value=meta.get("publisher", publisher))
                                new_pub_year = st.text_input("Publication Year", value=str(meta.get("pub_year", pub_year or "")))
                                new_pages = st.number_input("Pages", min_value=0, value=meta.get("pages", pages or 0), step=1)
                                new_genre = st.text_input("Genre", value=meta.get("genre", genre))

                                gender_options = ["", "Male", "Female", "Nonbinary", "Multiple", "Unknown"]
                                gender_index = gender_options.index(meta.get("author_gender", gender)) if meta.get("author_gender", gender) in gender_options else 0
                                new_gender = st.selectbox("Author Gender", gender_options, index=gender_index)

                                fiction_options = ["", "Fiction", "Non-fiction"]
                                fiction_index = fiction_options.index(meta.get("fiction_nonfiction", fiction)) if meta.get("fiction_nonfiction", fiction) in fiction_options else 0
                                new_fiction = st.selectbox("Fiction or Non-fiction", fiction_options, index=fiction_index)

                                new_tags = st.text_input("Tags (comma-separated)", value=", ".join(meta.get("tags", tags.split(",") if tags else [])))
                                new_date = st.date_input("Date Finished", value=datetime.strptime(date_str, "%Y-%m"))
                                new_isbn = st.text_input("ISBN", value=isbn)
                                new_olid = st.text_input("OpenLibrary ID", value=openlibrary_id)

                                submitted = st.form_submit_button("💾 Update Book")
                                enrich_clicked = st.form_submit_button("🔍 Enrich Metadata")

                                if enrich_clicked:
                                    existing = {
                                        "publisher": new_publisher,
                                        "pub_year": new_pub_year,
                                        "pages": new_pages,
                                        "genre": new_genre,
                                        "fiction_nonfiction": new_fiction,
                                        "author_gender": new_gender,
                                        "tags": [t.strip() for t in new_tags.split(",") if t.strip()],
                                        "isbn": new_isbn,
                                        "cover_url": cover_url
                                    }

                                    enriched = enrich_book_metadata(title, author, isbn, existing=existing)

                                    if "error" in enriched:
                                        st.warning(f"Enrichment failed: {enriched['error']}")
                                    else:
                                        st.session_state[f"edit_enriched_{book_id}"] = enriched
                                        st.rerun()

                                if submitted:
                                    update_book_metadata_full(
                                        book_id,
                                        new_title,
                                        new_author,
                                        new_publisher,
                                        int(new_pub_year) if new_pub_year else None,
                                        int(new_pages) if new_pages else None,
                                        new_genre,
                                        new_gender,
                                        new_fiction,
                                        new_tags,
                                        new_date.strftime("%Y-%m"),
                                        new_isbn,
                                        new_olid
                                    )
                                    st.session_state.edit_message = f"Book '{new_title}' updated!"
                                    st.session_state[f"edit_{book_id}"] = False
                                    st.rerun()









