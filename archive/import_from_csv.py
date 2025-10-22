import csv
import sqlite3

DB_FILE = "books.db"
CSV_FILE = "books_import.csv"

def import_books():
    with sqlite3.connect(DB_FILE) as conn, open(CSV_FILE, newline='', encoding='windows-1252') as f:
        cursor = conn.cursor()
        reader = csv.DictReader(f)
        for row in reader:
            cursor.execute("""
                INSERT INTO books (
                    title, author, publisher, pub_year, pages,
                    genre, author_gender, fiction_nonfiction, tags,
                    date_finished, cover_url, openlibrary_id, isbn, word_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row.get("title"),
                row.get("author"),
                row.get("publisher"),
                int(row["pub_year"]) if row.get("pub_year") else None,
                int(row["pages"]) if row.get("pages") else None,
                row.get("genre", ""),
                row.get("author_gender"),
                row.get("fiction_nonfiction"),
                row.get("tags"),
                row.get("date_finished"),
                row.get("cover_url"),
                row.get("openlibrary_id", ""),
                row.get("isbn", ""),
                row.get("word_count", "")
            ))
        conn.commit()
        print("✅ Import complete")

if __name__ == "__main__":
    import_books()
