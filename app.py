import streamlit as st
from db_google import get_all_books

st.set_page_config(page_title="Test Filters", layout="wide")
st.title("Test sidebar filters only")

# ---------- Load data ----------
try:
    books = get_all_books()
except Exception as e:
    st.error(f"⚠️ Could not load books: {e}")
    st.stop()

if not books:
    st.info("No books found in your Google Sheet.")
    st.stop()

# ---------------------------------
# Sidebar Filters
# ---------------------------------
st.sidebar.header("Filter Library")

years = sorted({b.get("date_finished", "")[:4] for b in books if b.get("date_finished")}, reverse=True)
months = sorted({b.get("date_finished", "")[5:7] for b in books if b.get("date_finished")})
authors = sorted({b.get("author", "") for b in books if b.get("author")})
titles = sorted({b.get("title", "") for b in books if b.get("title")})

f_years = st.sidebar.multiselect("Year finished", years)
f_months = st.sidebar.multiselect("Month finished", months)
f_authors = st.sidebar.multiselect("Author", authors)
f_titles = st.sidebar.multiselect("Title", titles)

f_genre = st.sidebar.text_input("Genre contains")
f_tags = st.sidebar.text_input("Tags contains")

f_type = st.sidebar.radio("Type", ["All", "Fiction", "Non-fiction"], index=0)
f_gender = st.sidebar.multiselect("Author gender", ["Male", "Female", "Other"])

apply_filters = st.sidebar.button("Apply Filters")

if "filtered_books" not in st.session_state:
    st.session_state["filtered_books"] = books

if apply_filters:
    filtered = []
    for b in books:
        df = b.get("date_finished", "") or ""
        yr = df[:4] if "-" in df else ""
        mo = df[5:7] if "-" in df else ""

        if f_years and yr not in f_years: continue
        if f_months and mo not in f_months: continue
        if f_authors and b.get("author","") not in f_authors: continue
        if f_titles and b.get("title","") not in f_titles: continue
        if f_genre and f_genre.lower() not in (b.get("genre") or "").lower(): continue
        if f_tags and f_tags.lower() not in (b.get("tags") or "").lower(): continue
        if f_type != "All" and (b.get("fiction_nonfiction") or "") != f_type: continue
        if f_gender:
            g = (b.get("author_gender") or "").capitalize()
            if g not in f_gender: continue

        filtered.append(b)

    st.session_state["filtered_books"] = filtered

books = st.session_state["filtered_books"]
