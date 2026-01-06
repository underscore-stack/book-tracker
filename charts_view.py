# charts_view.py
import altair as alt
import pandas as pd
import streamlit as st

def books_to_df(books):
    """
    Normalize books into a DataFrame with named columns.
    Handles: list[dict], list[sqlite3.Row], list[tuple], etc.
    """
    if books is None:
        return pd.DataFrame()
    if isinstance(books, pd.DataFrame):
        return books.copy()
    if not isinstance(books, (list, tuple)) or len(books) == 0:
        return pd.DataFrame()

    first = books[0]

    # list of dicts
    if isinstance(first, dict):
        return pd.DataFrame.from_records(books)

    # sqlite3.Row / mapping-ish
    try:
        return pd.DataFrame.from_records([dict(r) for r in books])
    except Exception:
        pass

    # last resort: sequence rows (tuples/lists)
    # IMPORTANT: this column list must match the SELECT order if you ever return tuples.
    columns = [
        "id", "title", "author", "publisher", "pub_year", "pages", "genre",
        "author_gender", "fiction_nonfiction", "tags", "date_finished",
        "cover_url", "openlibrary_id", "isbn", "word_count",
    ]
    return pd.DataFrame(list(books), columns=columns[:len(first)])


def show_charts(books: list):
    """Display reading analytics given a list of book dicts."""
    if not books:
        st.info("No books to visualize.")
        return

    df = books_to_df(books)
    df["ym"] = pd.to_datetime(df["date_finished"], format="%Y-%m", errors="coerce")
    df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
    df["word_count"] = pd.to_numeric(df["word_count"], errors="coerce")
    df = df.dropna(subset=["ym"])

    df["year"] = df["ym"].dt.year
    df["month_num"] = df["ym"].dt.month
    df["month"] = df["ym"].dt.strftime("%b")

    df = df.dropna(subset=["month_num"])
    df["month_num"] = df["month_num"].astype(int)

    df["month"] = pd.Categorical(
        df["month"],
        categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        ordered=True
    )

    st.header(f"📊 Reading Analytics ({len(books)} books)")

    with st.expander("📈 Show Charts", expanded=True):
        MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

        if df.empty:
            st.info("No data for charts yet.")
            return
    #pages by month
        pages_by_month = (
            df.groupby(["year", "month_num"], observed=True)["pages"]
              .sum()
              .reset_index()
        )
        pages_by_month["month"] = pages_by_month["month_num"].apply(lambda m: MONTHS[int(m) - 1])

        chart_pages = alt.Chart(pages_by_month).mark_line(point=True).encode(
            x=alt.X("month:N", sort=MONTHS, axis=alt.Axis(title="Month")),
            y=alt.Y("pages:Q", title="Pages Read"),
            color="year:N",
            tooltip=["year:N", "month:N", "pages:Q"],
        ).properties(title="Pages Read per Month by Year")

    #books by month
        books_by_month = (
            df.groupby(["year", "month_num"], observed=True)
              .size()
              .reset_index(name="count")
        )
        books_by_month["month"] = books_by_month["month_num"].apply(lambda m: MONTHS[int(m) - 1])

        chart_books = alt.Chart(books_by_month).mark_bar().encode(
            x=alt.X("month:N", sort=MONTHS, axis=alt.Axis(title="Month")),
            y=alt.Y("count:Q", title="Books Read"),
            color="year:N",
            tooltip=["year:N", "month:N", "count:Q"],
        ).properties(title="Books Read per Month")

    #books by year
        books_by_year = (
            df.groupby(["year"], observed=True)
              .size()
              .reset_index(name="count")
              .sort_values("year")
        )
        
        chart_books_year = alt.Chart(books_by_year).mark_bar().encode(
            x=alt.X("year:N", sort=None, axis=alt.Axis(title="Year")),
            y=alt.Y("count:Q", title="Books Read"),
            tooltip=["year:N", "count:Q"],
        ).properties(title="Books Read per Year")

    #type chart
        pie_f = df["fiction_nonfiction"].value_counts().reset_index()
        pie_f.columns = ["fiction_nonfiction", "count"]
        pie_chart_f = alt.Chart(pie_f).mark_arc(innerRadius=40).encode(
            theta="count:Q", color="fiction_nonfiction:N", tooltip=["Fiction vs Non-fiction", "count"]
        ).properties(title="Fiction vs Non-fiction")

    #gender chart
        pie_g = df["author_gender"].value_counts().reset_index()
        pie_g.columns = ["author_gender", "count"]
        pie_chart_g = alt.Chart(pie_g).mark_arc(innerRadius=40).encode(
            theta="count:Q", color="author_gender:N", tooltip=["Author Gender", "count"]
        ).properties(title="Author Gender Breakdown")

        st.altair_chart(chart_pages, use_container_width=True)
        st.altair_chart(chart_books, use_container_width=True)
        st.altair_chart(chart_books_year, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            st.altair_chart(pie_chart_f, use_container_width=True)
        with c2:
            st.altair_chart(pie_chart_g, use_container_width=True)

import pandas as pd
import streamlit as st

def show_extreme_books(books):
    """
    Compute and display longest/shortest books per year using the
    current (filtered) list of books.
    """

    # Convert to DataFrame
    df = books_to_df(books)
    
    if df.empty or "pages" not in df.columns:
        st.info("Not enough data to compute extremes (missing 'pages').")
        return
        
    # Clean up page counts
    df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
    df["year"] = df["date_finished"].str[:4]

    # Use only valid rows
    df_valid = df.dropna(subset=["pages", "year"])
    if df_valid.empty:
        st.info("Not enough data to compute longest/shortest books.")
        return

    # Helper: find book(s) matching the extreme of a given metric
    def get_extreme_books(df, func):
        grouped = df.groupby("year")["pages"].transform(func)
        result = df.loc[grouped == df["pages"]]
        # If multiple books tie, drop duplicates
        return (
            result.drop_duplicates("year")
                  .set_index("year")
        )

    longest = get_extreme_books(df_valid, "max")
    shortest = get_extreme_books(df_valid, "min")

    # Build summary table sorted by year
    years_sorted = sorted(df_valid["year"].unique())
    summary = pd.DataFrame(index=years_sorted)

    summary["Longest Book"] = longest.apply(
        lambda x: f"<b>{x['title']}</b> by {x['author']} ({int(x['pages'])} pages)",
        axis=1
    )

    summary["Shortest Book"] = shortest.apply(
        lambda x: f"<b>{x['title']}</b> by {x['author']} ({int(x['pages'])} pages)",
        axis=1
    )

    summary.index.name = None

    st.markdown("<h4 style='margin-top: 2em;'>📏 Longest and Shortest Books per Year</h4>",
                unsafe_allow_html=True)

    st.markdown(
        summary.to_html(
            escape=False,
            index_names=True,
            classes="custom-table",
            border=1,
        ),
        unsafe_allow_html=True,
    )

