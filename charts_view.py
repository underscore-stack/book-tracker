# charts_view.py
import altair as alt
import pandas as pd
import streamlit as st


def show_charts(books: list):
    """Display reading analytics given a list of book dicts."""
    if not books:
        st.info("No books to visualize.")
        return

    df = pd.DataFrame(books)
    df["ym"] = pd.to_datetime(df["date_finished"], format="%Y-%m", errors="coerce")
    df["pages"] = pd.to_numeric(df["pages"], errors="coerce")
    df["word_count"] = pd.to_numeric(df["word_count"], errors="coerce")
    df = df.dropna(subset=["ym"])

    df["year"] = df["ym"].dt.year
    df["month"] = df["ym"].dt.strftime("%b")
    df["month_num"] = df["ym"].dt.month
    df["month"] = pd.Categorical(
        df["month"],
        categories=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        ordered=True
    )

    st.header("📊 Reading Analytics")

    with st.expander("📈 Show Charts", expanded=True):
        # Pages per month
        pages_by_month = df.groupby(["year", "month_num"], observed=True)["pages"].sum().reset_index()
        chart_pages = alt.Chart(pages_by_month).mark_line(point=True).encode(
            x=alt.X("month_num:Q", axis=alt.Axis(title="Month", tickMinStep=1)),
            y=alt.Y("pages:Q", title="Pages Read"),
            color="year:N",
            tooltip=["year:N", "pages:Q"]
        ).properties(title="Pages Read per Month by Year")

        # Books per month
        books_by_month = df.groupby(["year", "month_num"], observed=True).size().reset_index(name="count")
        chart_books = alt.Chart(books_by_month).mark_bar().encode(
            x=alt.X("month_num:Q", axis=alt.Axis(title="Month")),
            y=alt.Y("count:Q", title="Books Read"),
            color="year:N",
            tooltip=["year:N", "count:Q"]
        ).properties(title="Books Read per Month")

        # Fiction vs Non-fiction
        pie_f = df["fiction_nonfiction"].value_counts().reset_index()
        pie_f.columns = ["fiction_nonfiction", "count"]
        pie_chart_f = alt.Chart(pie_f).mark_arc(innerRadius=40).encode(
            theta="count:Q", color="fiction_nonfiction:N", tooltip=["fiction_nonfiction", "count"]
        ).properties(title="Fiction vs Non-fiction")

        # Author gender
        pie_g = df["author_gender"].value_counts().reset_index()
        pie_g.columns = ["author_gender", "count"]
        pie_chart_g = alt.Chart(pie_g).mark_arc(innerRadius=40).encode(
            theta="count:Q", color="author_gender:N", tooltip=["author_gender", "count"]
        ).properties(title="Author Gender Breakdown")

        # Display
        st.altair_chart(chart_pages, use_container_width=True)
        st.altair_chart(chart_books, use_container_width=True)
        c1, c2 = st.columns(2)
        with c1: st.altair_chart(pie_chart_f, use_container_width=True)
        with c2: st.altair_chart(pie_chart_g, use_container_width=True)
