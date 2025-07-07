# db.py (Supabase version)
from supabase import create_client
import os

# Supabase credentials (use env vars in production)
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://your-project-id.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or "your-anon-public-key"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def add_book(book_data):
    response = supabase.table("books").insert(book_data).execute()
    if response.error:
        print("❌ Error adding book:", response.error)
    else:
        print("✅ Book added")

def get_all_books():
    response = supabase.table("books").select("*").order("date_finished", desc=True).execute()
    if response.error:
        print("❌ Error fetching books:", response.error)
        return []
    return response.data

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
    response = supabase.table("books").update(update_data).eq("id", book_id).execute()
    if response.error:
        print("❌ Error updating book:", response.error)
    else:
        print("✅ Book updated")

def delete_book(book_id):
    response = supabase.table("books").delete().eq("id", book_id).execute()
    if response.error:
        print("❌ Error deleting book:", response.error)
    else:
        print("✅ Book deleted")
