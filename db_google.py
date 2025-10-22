import gspread
from google.oauth2.service_account import Credentials as SACreds
import streamlit as st

# Define the scopes for Google Sheets + Drive
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file"
]

# --- AUTHENTICATION ---
def _get_client():
    creds = SACreds.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    return gspread.authorize(creds)

# --- CONFIG ---
SHEET_NAME = "booktracker"
HEADERS = [
    "id", "title", "author", "publisher", "pub_year", "pages",
    "genre", "author_gender", "fiction_nonfiction", "tags",
    "date_finished", "cover_url", "openlibrary_id", "isbn", "word_count"
]

def _get_sheet():
    gc = _get_client()
    try:
        sh = gc.open(SHEET_NAME)
    except gspread.SpreadsheetNotFound:
        sh = gc.create(SHEET_NAME)
        sh.share(st.secrets["gcp_service_account"]["client_email"], perm_type="user", role="writer")
        sh.sheet1.append_row(HEADERS)
    return sh.sheet1


# --- CRUD FUNCTIONS ---
def get_all_books():
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    # ensure numeric word count
    for r in rows:
        r["word_count"] = int(r["word_count"]) if r.get("word_count") else None
    return rows

def add_book(book):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    new_id = len(rows) + 1
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
                              gender, fiction, tags, date_finished, isbn, openlibrary_id):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, start=2):  # +1 header, +1 gspread index starts at 1
        if str(r["id"]) == str(book_id):
            sheet.update(f"A{i}:N{i}", [[
                book_id, title, author, publisher, pub_year, pages,
                genre, gender, fiction, tags, date_finished, r["cover_url"],
                openlibrary_id, isbn, r.get("word_count", "")
            ]])
            break

def delete_book(book_id):
    sheet = _get_sheet()
    rows = sheet.get_all_records()
    for i, r in enumerate(rows, start=2):
        if str(r["id"]) == str(book_id):
            sheet.delete_rows(i)
            break
