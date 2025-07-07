# db.py
import sqlite3

DB_FILE = "books.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
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
            );
        """)
        # Migration if column is missing (safe for reruns)
        try:
            cursor.execute("ALTER TABLE books ADD COLUMN word_count INTEGER")
        except sqlite3.OperationalError:
            pass  # Column already exists
        conn.commit()

def add_book(book_data):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        pages = book_data.get("pages") or 0
        word_count = int(pages) * 250 if pages else None
        book_data["word_count"] = word_count
        cursor.execute("""
            INSERT INTO books (
                title, author, publisher, pub_year, pages, genre,
                author_gender, fiction_nonfiction, tags,
                date_finished, cover_url, openlibrary_id, isbn, word_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, tuple(book_data.values()))
        conn.commit()
        
def get_all_books():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books ORDER BY date_finished DESC, id DESC;")
        return cursor.fetchall()

def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages,
                              genre, gender, fiction, tags, date_finished,
                              isbn, openlibrary_id):
    word_count = pages * 250 if pages else None

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE books
            SET
                title = ?,
                author = ?,
                publisher = ?,
                pub_year = ?,
                pages = ?,
                genre = ?,
                author_gender = ?,
                fiction_nonfiction = ?,
                tags = ?,
                date_finished = ?,
                isbn = ?,
                openlibrary_id = ?,
                word_count = ?
            WHERE id = ?
        """, (
            title, author, publisher, pub_year, pages, genre,
            gender, fiction, tags, date_finished,
            isbn, openlibrary_id, word_count, book_id
        ))
        conn.commit()



def delete_book(book_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM books WHERE id = ?", (book_id,))
        conn.commit()


