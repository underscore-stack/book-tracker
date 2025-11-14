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

# ---------- Sidebar filters only ----------
st.sidebar.header("Filter Library")

years = sorted({b.get("date_finished", "")[:4] for b in books if b.get("date_finished")}, reverse=True)
months = sorted({b.get("date_finished", "")[5:7] for b in books if b.get("date_finished")})
authors = sorted({b.get("author", "") for b in books if b.get("author")})
titles = sorted({b.get("title", "") for b in books if b.get("title)})
#titles = sorted({b.get("title", "") for b in books if b.get("title")})

st.write("Loaded books:", len(books))
st.write("Years:", years)
st.write("Months:", months)
st.write("Authors (sample):", authors[:5])
st.write("Titles (sample):", titles[:5])
