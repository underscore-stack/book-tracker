# db.py — Cockroach version (patch)
import os
import psycopg2
import psycopg2.extras

def _safe_int(v):
    try:
        return int(v) if v not in (None, "", "NULL") else None
    except Exception:
        return None

def _safe_word_count(pages):
    p = _safe_int(pages)
    return p * 250 if p else None

def get_connection():
    # Prefer Streamlit secrets; fall back to env var
    dsn = None
    try:
        import streamlit as st
        dsn = st.secrets["cockroach"]["dsn"]
    except Exception:
        dsn = os.getenv("COCKROACH_DB_URL")

    if not dsn:
        raise RuntimeError("Cockroach DSN not set. Put it in st.secrets['cockroach']['dsn'] or COCKROACH_DB_URL.")

    conn = psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET application_name = 'book-tracker';")
        cur.execute("SET search_path = public;")
    return conn

def add_book(book_data):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            INSERT INTO books (
                title, author, publisher, pub_year, pages, genre,
                author_gender, fiction_nonfiction, tags,
                date_finished, cover_url, openlibrary_id, isbn, word_count
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            book_data.get("title"),
            book_data.get("author"),
            book_data.get("publisher"),
            _safe_int(book_data.get("pub_year")),
            _safe_int(book_data.get("pages")),
            book_data.get("genre"),
            book_data.get("author_gender"),
            book_data.get("fiction_nonfiction"),
            book_data.get("tags"),
            book_data.get("date_finished"),
            book_data.get("cover_url"),
            book_data.get("openlibrary_id"),
            book_data.get("isbn"),
            _safe_word_count(book_data.get("pages")),
        ))

def get_all_books():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            SELECT *
            FROM books
            ORDER BY id DESC;
        """)
        return cur.fetchall()

def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages, genre, gender, fiction, tags, date_finished, isbn, openlibrary_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""
            UPDATE books SET
                title=%s, author=%s, publisher=%s, pub_year=%s, pages=%s, genre=%s,
                author_gender=%s, fiction_nonfiction=%s, tags=%s, date_finished=%s,
                isbn=%s, openlibrary_id=%s, word_count=%s
            WHERE id=%s
        """, (
            title, author, publisher,
            _safe_int(pub_year), _safe_int(pages), genre,
            gender, fiction, tags, date_finished,
            isbn, openlibrary_id,
            _safe_word_count(pages),
            book_id,
        ))

def delete_book(book_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM books WHERE id=%s", (book_id,))

