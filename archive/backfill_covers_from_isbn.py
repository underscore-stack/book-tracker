import sqlite3
import requests

DB_FILE = "books.db"

def fetch_cover_url(isbn):
    # OpenLibrary Covers API
    test_url = f"https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false"
    r = requests.get(test_url)
    if r.status_code == 200 and r.content and len(r.content) > 500:  # avoid 1x1 transparent fallback
        return test_url
    return None

def backfill_cover_images():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, title, isbn FROM books
            WHERE (cover_url IS NULL OR cover_url = '' OR cover_url = 'None')
              AND isbn IS NOT NULL AND isbn != ''
        """)
        rows = cursor.fetchall()

        updated = 0
        for book_id, title, raw_isbn in rows:
            if not raw_isbn:
                continue

            # Normalize ISBN: take first if comma-separated, pad if 10-digit
            isbn_raw = raw_isbn.strip().split(",")[0]
            isbn = isbn_raw if len(isbn_raw) > 10 else isbn_raw.zfill(10)

            url = fetch_cover_url(isbn)
            if url:
                print(f"✅ {title} → {isbn} → cover found")
                cursor.execute("UPDATE books SET cover_url = ? WHERE id = ?", (url, book_id))
                updated += 1
            else:
                print(f"❌ {title} → {isbn} → no cover found")

        conn.commit()
        print(f"✅ Backfilled {updated} cover(s)")

if __name__ == "__main__":
    backfill_cover_images()
