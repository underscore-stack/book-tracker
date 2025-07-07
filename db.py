# db.py (Supabase version)
from supabase import create_client
import os

# Supabase credentials (use env vars in production)
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://your-project-id.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "your-anon-public-key"

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
        response = supabase.table("books").select("*").order("date_finished", desc=True).execute()
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
