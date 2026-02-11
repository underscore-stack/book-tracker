import gspread
import os
import json
from google.oauth2.service_account import Credentials as SACreds
import streamlit as st
import time


# Define the scopes for Google Sheets + Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

@st.cache_resource(show_spinner=False)
def _get_client():
    # Try Streamlit secrets first, fall back to env var if needed.
    for _ in range(5):  # up to ~2.5 s total retry window
        service_info = st.secrets.get("gcp_service_account")
        if service_info:
            creds = SACreds.from_service_account_info(service_info, scopes=SCOPES)
            return gspread.authorize(creds)
        # Optional environment fallback
        env_json = os.environ.get("GCP_SERVICE_ACCOUNT_JSON")
        if env_json:
            creds = SACreds.from_service_account_info(json.loads(env_json), scopes=SCOPES)
            return gspread.authorize(creds)
        time.sleep(0.5)
    raise RuntimeError("⚠️ Could not find gcp_service_account in Streamlit secrets after retries.")


# --- CONFIG ---
SHEET_NAME = "booktracker"
HEADERS = [
    "id", "title", "author", "publisher", "pub_year", "pages",
    "genre", "author_gender", "fiction_nonfiction", "tags",
    "date_finished", "cover_url", "openlibrary_id", "isbn", "word_count"
]

# Put your real sheet ID here (the long string from its URL)
SHEET_ID = "1nnYvuKRAew48h6xXPgmQXxxgPzCjHMFiQwfBh0uQk7A"

def _get_sheet():
    gc = _get_client()
    sh = gc.open_by_key(SHEET_ID)
    return sh.sheet1


# --- CRUD FUNCTIONS ---
def get_all_books():
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    # ensure numeric word count
    for r in rows:
        r["word_count"] = int(r["word_count"]) if r.get("word_count") else None
    return list(reversed(rows))
    
def add_book(book):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    existing_ids = [int(r["id"]) for r in rows if str(r.get("id", "")).isdigit()]
    new_id = (max(existing_ids) + 1) if existing_ids else 1
    row = [
        new_id,
        book.get("title", ""),
        book.get("author", ""),
        book.get("publisher", ""),
        book.get("pub_year", ""),
        book.get("pages", ""),
        book.get("genre", ""),
        book.get("author_gender", ""),
        book.get("fiction_nonfiction", ""),
        book.get("tags", ""),
        book.get("date_finished", ""),
        book.get("cover_url", ""),
        book.get("openlibrary_id", ""),
        book.get("isbn", ""),
        book.get("word_count", "")
    ]
    sheet.append_row(row)
    return True

def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages, genre,
                              author_gender, fiction_nonfiction, tags, date_finished, openlibrary_id, isbn):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, start=2):
        print(f"Checking row {i}: sheet id={r.get('id')}  |  passed id={book_id}")
        if str(r["id"]) == str(book_id):
            cover_url = r.get("cover_url", "")
            word_count = r.get("word_count", "")

            # --- Normalize data types ---
            # Try to make years and pages numeric
            try:
                pub_year = int(pub_year) if pub_year else ""
            except ValueError:
                pass
            try:
                pages = int(pages) if pages else ""
            except ValueError:
                pass

            # date_finished should be text in YYYY-MM, but without an apostrophe
            if isinstance(date_finished, str):
                date_finished = date_finished.strip()

            values = [
                book_id, title, author, publisher, pub_year, pages,
                genre, author_gender, fiction_nonfiction, tags, date_finished,
                cover_url, openlibrary_id, isbn, word_count
            ]

            # --- Write to sheet ---
            # Use RAW to preserve numeric and date-like values properly
            sheet.update(
                f"A{i}",
                [values],
                value_input_option="RAW"  # prevents the apostrophe prefix
            )
            break



def delete_book(book_id):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, start=2):
        if str(r["id"]) == str(book_id):
            sheet.delete_rows(i)
            break
