# db.py (Neon + psycopg2)
import os
import psycopg2
import psycopg2.extras

NEON_DB_URL = os.getenv("NEON_DB_URL")

def get_connection():
    return psycopg2.connect(NEON_DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)

def safe_bigint(value):
    """Convert to int (for BIGINT) or return None."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

def add_book(book_data):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            pages_val = safe_bigint(book_data.get("pages"))
            pub_year_val = safe_bigint(book_data.get("pub_year"))

            if "id" in book_data:
                # Used during migration to preserve original IDs
                cursor.execute("""
                    INSERT INTO books (
                        id, title, author, publisher, pub_year, pages, genre,
                        author_gender, fiction_nonfiction, tags,
                        date_finished, cover_url, openlibrary_id, isbn, word_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    book_data["id"],
                    book_data.get("title"),
                    book_data.get("author"),
                    book_data.get("publisher"),
                    pub_year_val,
                    pages_val,
                    book_data.get("genre"),
                    book_data.get("author_gender"),
                    book_data.get("fiction_nonfiction"),
                    book_data.get("tags"),
                    book_data.get("date_finished"),
                    book_data.get("cover_url"),
                    book_data.get("openlibrary_id"),
                    book_data.get("isbn"),
                    pages_val * 250 if pages_val else None
                ))
            else:
                # Normal path: let Neon auto-assign id
                cursor.execute("""
                    INSERT INTO books (
                        title, author, publisher, pub_year, pages, genre,
                        author_gender, fiction_nonfiction, tags,
                        date_finished, cover_url, openlibrary_id, isbn, word_count
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    book_data.get("title"),
                    book_data.get("author"),
                    book_data.get("publisher"),
                    pub_year_val,
                    pages_val,
                    book_data.get("genre"),
                    book_data.get("author_gender"),
                    book_data.get("fiction_nonfiction"),
                    book_data.get("tags"),
                    book_data.get("date_finished"),
                    book_data.get("cover_url"),
                    book_data.get("openlibrary_id"),
                    book_data.get("isbn"),
                    pages_val * 250 if pages_val else None
                ))


def get_all_books():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM books ORDER BY id DESC;")
            return cursor.fetchall()
          
def update_book_metadata_full(book_id, title, author, publisher, pub_year, pages,
                              genre, gender, fiction, tags, date_finished, isbn, openlibrary_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            pages_val = safe_bigint(pages)
            pub_year_val = safe_bigint(pub_year)

            cursor.execute("""
                UPDATE books SET
                    title = %s,
                    author = %s,
                    publisher = %s,
                    pub_year = %s,
                    pages = %s,
                    genre = %s,
                    author_gender = %s,
                    fiction_nonfiction = %s,
                    tags = %s,
                    date_finished = %s,
                    isbn = %s,
                    openlibrary_id = %s,
                    word_count = %s
                WHERE id = %s;
            """, (
                title,
                author,
                publisher,
                pub_year_val,
                pages_val,
                genre,
                gender,
                fiction,
                tags,
                date_finished,
                isbn,
                openlibrary_id,
                pages_val * 250 if pages_val else None,
                book_id
            ))

def delete_book(book_id):
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM books WHERE id = %s", (book_id,))





