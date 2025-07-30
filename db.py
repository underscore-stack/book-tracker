# db.py (Supabase version using st.secrets)
import streamlit as st
from supabase import create_client

# Load secrets from .streamlit/secrets.toml or Streamlit Cloud
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def add_book(book_data):
    try:
        supabase.table("books").insert(book_data).execute()
        print("📦 Response:", response)
        print("✅ Book added")
    except Exception as e:
        print("❌ Error adding book:", e)

def get_all_books():
    try:
        response = supabase.table("books").select("*").order("id", desc=True).execute()
        return response.data
    except Exception as e:
        print("❌ Error fetching books:", e)
        return []

def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages, genre, gender, fiction, tags, date_finished, isbn, openlibrary_id):
    update_data = {
        "title": title,
        "author": author,
        "publisher": publisher,
        "pub_year": pub_year,
        "pages": pages,
        "genre": genre,
        "author_gender": gender,
        "fiction_nonfiction": fiction,
        "tags": tags,
        "date_finished": date_finished,
        "isbn": isbn,
        "openlibrary_id": openlibrary_id,
        "word_count": pages * 250 if pages else None
    }
    try:
        supabase.table("books").update(update_data).eq("id", book_id).execute()
        print("✅ Book updated")
    except Exception as e:
        print("❌ Error updating book:", e)

def delete_book(book_id):
    try:
        supabase.table("books").delete().eq("id", book_id).execute()
        print("✅ Book deleted")
    except Exception as e:
        print("❌ Error deleting book:", e)
