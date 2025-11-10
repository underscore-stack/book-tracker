import json
import os
import re
import uuid
import streamlit.components.v1 as components

from collections import defaultdict
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from covers_google import get_cached_or_drive_cover, save_cover_to_drive
from db_google import add_book, delete_book, get_all_books, update_book_metadata_full
from enrichment import enrich_book_metadata
from openlibrary_new import search_works, fetch_editions_for_work

def scroll_to_bottom():
    """Smooth scroll to bottom after selecting an edition."""
    js = """
    <script>
        window.scrollTo({top: document.body.scrollHeight, behavior: 'smooth'});
    </script>
    """
    components.html(js, height=0, width=0)


st.set_page_config(page_title="Book Tracker", layout="wide")
st.title("📚 Book Tracker")



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
        combinedCh = (
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
                    axis=alt.Axis(
                        tickMinStep=1,
                        values=list(range(1, 13)),
                        labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]',
                    ),
                ),
                y=alt.Y("cumulative:Q", title="Cumulative Books Read"),
                color=alt.Color("year:N", title="Year"),
                tooltip=["year:N", "month:N", "cumulative:Q"],
            )
            .properties(title="Cumulative Books Read per Year")
        )

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

        chart_cum_words = (
            alt.Chart(cum_words)
            .mark_line(interpolate="monotone")
            .encode(
                x=alt.X(
                    "month(fake_date):O",
                    title="Month",
                    sort=list(range(1, 13)),
                    axis=alt.Axis(labelExpr='{"1":"Jan","2":"Feb","3":"Mar","4":"Apr","5":"May","6":"Jun","7":"Jul","8":"Aug","9":"Sep","10":"Oct","11":"Nov","12":"Dec"}[datum.value]'),
                ),
                y=alt.Y("cumulative:Q", title="Cumulative Word Count"),
                color=alt.Color("year:N", title="Year"),
                tooltip=["year:N", alt.Tooltip("fake_date:T", title="Date", format="%B"), "cumulative:Q"],
            )
            .properties(title="Cumulative Word Count (Jan–Dec, by Year)")
        )

        # Fiction vs Non-fiction pie chart
        pie_data_f = df["fiction_nonfiction"].value_counts(normalize=False).reset_index()
        pie_data_f.columns = ["fiction_nonfiction", "count"]
        pie_data_f["percent"] = pie_data_f["count"] / pie_data_f["count"].sum() * 100

        base_f = alt.Chart(pie_data_f).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("fiction_nonfiction:N", title="Fiction/Non-fiction"),
            tooltip=["fiction_nonfiction:N", "count:Q"],
        )

        arc_f = base_f.mark_arc(innerRadius=30)
        text_f = (
            base_f.mark_text(radius=75, fontSize=20, fontWeight="bold", fill="white")
            .transform_calculate(label="format(datum.percent, '.1f') + '%'")
            .encode(text="label:N")
        )

        pie_chart_f = (arc_f + text_f).properties(title={"text": "Fiction vs Non-fiction", "align": "center"})

        # Author gender pie chart (omit 'Multiple')
        pie_data_g = df["author_gender"].value_counts(normalize=False).reset_index()
        pie_data_g.columns = ["author_gender", "count"]
        pie_data_g = pie_data_g[pie_data_g["author_gender"].str.lower() != "multiple"]
        pie_data_g["percent"] = pie_data_g["count"] / pie_data_g["count"].sum() * 100

        base_g = alt.Chart(pie_data_g).encode(
            theta=alt.Theta("count:Q", stack=True),
            color=alt.Color("author_gender:N", title="Gender"),
            tooltip=["author_gender:N", "count:Q"],
        )

        arc_g = base_g.mark_arc(innerRadius=30)
        text_g = (
            base_g.mark_text(radius=75, fontSize=20, fontWeight="bold", fill="white")
            .transform_calculate(label="format(datum.percent, '.1f') + '%'")
            .encode(text="label:N")
        )

        pie_chart_g = (arc_g + text_g).properties(title={"text": "Gender Divide", "align": "center"})

        # Display charts
        col1, col2 = st.columns(2)
        with col1:
            st.altair_chart(pie_chart_f, use_container_width=True)
        with col2:
            st.altair_chart(pie_chart_g, use_container_width=True)

        st.altair_chart(combinedCh, use_container_width=True)
        st.altair_chart(chart_cum_words, use_container_width=True)
        st.altair_chart(chart_books, use_container_width=True)
        st.altair_chart(chart_cum_books, use_container_width=True)

else:
    st.info("No filtered books to display.")
    df = pd.DataFrame(
        columns=[
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
    )



