import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime
from db import add_book, get_all_books, update_book_metadata_full, delete_book
from openlibrary import search_books
from enrichment import enrich_book_metadata

st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")

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
            # Show Enrich button
            if st.button(f"🔍 Enrich", key=f"enrich_{idx}"):
                enriched = enrich_book_metadata(book["title"], book["author"], book.get("isbn"))
                if "error" in enriched:
                    st.error(f"Enrichment failed: {enriched['error']}")
                else:
                    st.session_state[f"enriched_{idx}"] = enriched

            # Get enrichment metadata if available
            meta = st.session_state.get(f"enriched_{idx}", {})

            # Start the form inside the expander
            with st.form(key=f"form_{idx}"):
                if book.get("cover_url") and book["cover_url"].startswith("http"):
                    st.image(book["cover_url"], width=120)
                else:
                    st.caption("No cover available")

                # Show metadata
                st.write(f"**Publisher:** {meta.get('publisher') or book.get('publisher', '')}")
                st.write(f"**Year:** {meta.get('pub_year') or book.get('pub_year', '')}")
                st.write(f"**Pages:** {meta.get('pages') or book.get('pages', '')}")
                st.write(f"**ISBN:** {book['isbn']}")
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
                    book_data = {
                        "title": book.get("title", ""),
                        "author": book.get("author", ""),
                        "publisher": meta.get("publisher") or book.get("publisher", ""),
                        "pub_year": book.get("pub_year"),
                        "pages": book.get("pages"),
                        "genre": "",
                        "author_gender": author_gender,
                        "fiction_nonfiction": fiction,
                        "tags": tags,
                        "date_finished": date.strftime("%Y-%m"),
                        "cover_url": book.get("cover_url", ""),
                        "openlibrary_id": book.get("openlibrary_id", ""),
                        "isbn": book.get("isbn", "")
                    }
                    add_book(book_data)
                    st.session_state.edit_message = f"Book '{book['title']}' added!"
                    st.rerun()



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

st.markdown("""
<style>
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
            x=alt.X("fake_date:T", title="Month", axis=alt.Axis(format="%b")),
            y=alt.Y("cumulative:Q", title="Cumulative Word Count"),
            color=alt.Color("year:N", title="Year"),
            tooltip=["year:N", alt.Tooltip("fake_date:T", title="Month", format="%B"), "cumulative:Q"]
        ).properties(title="Cumulative Word Count (Jan–Dec, by Year)")

        # Fiction vs Non-fiction pie chart
        pie_data_f = df["fiction_nonfiction"].value_counts().reset_index()
        pie_data_f.columns = ["fiction_nonfiction", "count"]
        base_f = alt.Chart(pie_data_f).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("fiction_nonfiction:N", title="Fiction/Non-fiction")
        )
        pie_chart_f = base_f.mark_arc(innerRadius=30).properties(title="Fiction vs Non-fiction") + \
                      base_f.mark_text(radius=75, fontSize=25, fontWeight="bold", fill="white").encode(text="count:Q")

        # Author gender pie chart
        pie_data_g = df["author_gender"].value_counts().reset_index()
        pie_data_g.columns = ["author_gender", "count"]
        base_g = alt.Chart(pie_data_g).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("author_gender:N", title="Gender")
        )
        pie_chart_g = base_g.mark_arc(innerRadius=30).properties(title="Gender Divide") + \
                      base_g.mark_text(radius=75, fontSize=25, fontWeight="bold", fill="white").encode(text="count:Q")

        # Display charts
        col1, col2 = st.columns(2)
        with col1:
            st.altair_chart(pie_chart_f, use_container_width=True)
        with col2:
            st.altair_chart(pie_chart_g, use_container_width=True)

        st.altair_chart(combined, use_container_width=True)
        st.altair_chart(chart_cum_words, use_container_width=True)

        col1, col2 = st.columns(2)
        with col1:
            st.altair_chart(chart_books, use_container_width=True)
        with col2:
            st.altair_chart(chart_cum_books, use_container_width=True)

if not df.empty:
    try:
        df_valid = df.dropna(subset=["pages", "year"])
        df_valid["pages"] = pd.to_numeric(df_valid["pages"], errors="coerce")
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




for b in filtered_books:
    book_id = b["id"]
    # Ensure session keys are initialized
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
        if cover_url.startswith("http"):
            st.image(cover_url, width=60)
        else:
            st.empty()

    with cols[1]:
        st.markdown(f"<div class='book-title'>{title}</div>", unsafe_allow_html=True)
        st.markdown(f"<div class='book-author'>{author}</div>", unsafe_allow_html=True)

    with cols[2]:
        if st.button("▶", key=f"expand_{book_id}"):
            st.session_state[f"expanded_{book_id}"] = not st.session_state[f"expanded_{book_id}"]

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
            if cover_url.startswith("http"):
                st.markdown(
                    f'<div class="expanded-cover"><img src="{cover_url}" style="max-width: 80%; height: auto;"></div>',
                    unsafe_allow_html=True,
                )
            else:
                st.caption("No cover available")

        if not st.session_state[f"edit_{book_id}"]:
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✏️ Edit Book", key=f"edit_btn_{book_id}"):
                    st.session_state[f"edit_{book_id}"] = True
            with col2:
                if st.button("🗑️ Delete Book", key=f"delete_{book_id}"):
                    delete_book(book_id)
                    st.session_state.deleted_message = f"Book '{title}' deleted"
                    st.rerun()

        if st.session_state[f"edit_{book_id}"]:
            with st.form(key=f"edit_form_{book_id}"):
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

                # Submit buttons
                submitted = st.form_submit_button("💾 Update Book")
                enrich_clicked = st.form_submit_button("🔍 Enrich Metadata")

                if enrich_clicked:
                    enriched = enrich_book_metadata(title, author, isbn)
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

