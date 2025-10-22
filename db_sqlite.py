# db_sqlite.py
import sqlite3
import os

DB_FILE = "books.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            author TEXT,
            publisher TEXT,
            pub_year INTEGER,
            pages INTEGER,
            genre TEXT,
            author_gender TEXT,
            fiction_nonfiction TEXT,
            tags TEXT,
            date_finished TEXT,
            cover_url TEXT,
            openlibrary_id TEXT,
            isbn TEXT,
            word_count INTEGER
        )
        """)
        conn.commit()

def _safe_int(v):
    try:
        return int(v) if v not in (None, "", "NULL") else None
    except Exception:
        return None

def _safe_word_count(pages):
    p = _safe_int(pages)
    return p * 250 if p else None

def add_book(book_data):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO books (
                title, author, publisher, pub_year, pages, genre,
                author_gender, fiction_nonfiction, tags,
                date_finished, cover_url, openlibrary_id, isbn, word_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        conn.commit()

def get_all_books():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books ORDER BY id DESC")
        return [dict(r) for r in cur.fetchall()]

def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages, genre,
                              gender, fiction, tags, date_finished, isbn, openlibrary_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            UPDATE books SET
                title=?, author=?, publisher=?, pub_year=?, pages=?, genre=?,
                author_gender=?, fiction_nonfiction=?, tags=?, date_finished=?,
                isbn=?, openlibrary_id=?, word_count=?
            WHERE id=?
        """, (
            title, author, publisher,
            _safe_int(pub_year), _safe_int(pages), genre,
            gender, fiction, tags, date_finished,
            isbn, openlibrary_id,
            _safe_word_count(pages),
            book_id
        ))
        conn.commit()

def delete_book(book_id):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM books WHERE id=?", (book_id,))
        conn.commit()
