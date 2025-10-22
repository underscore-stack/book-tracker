import sqlite3
import requests

DB_FILE = "books.db"

def fetch_openlibrary_id(isbn):
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
    r = requests.get(url)
    if r.status_code != 200:
        return None

    data = r.json()
    entry = data.get(f"ISBN:{isbn}")
    if not entry:
        return None

    # Attempt to extract a works-style ID (e.g., from the URL)
    identifiers = entry.get("identifiers", {})
    olids = identifiers.get("openlibrary", [])
    if olids:
        return olids[0].replace("/works/", "").replace("/books/", "")
    
    # fallback: extract from URL if available
    if "url" in entry and "/works/" in entry["url"]:
        return entry["url"].split("/works/")[1].strip("/")
    
    return None

def backfill_openlibrary_ids():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, title, isbn FROM books WHERE (openlibrary_id IS NULL OR openlibrary_id = '') AND isbn IS NOT NULL AND isbn != ''")
        rows = cursor.fetchall()

        updated = 0
        for book_id, title, raw_isbn in rows:
            isbn_raw = raw_isbn.strip().split(",")[0]
            isbn = isbn_raw if len(isbn_raw) > 10 else isbn_raw.zfill(10)

            olid = fetch_openlibrary_id(isbn)
            if olid:
                print(f"✅ {title} → {isbn} → {olid}")
                cursor.execute("UPDATE books SET openlibrary_id = ? WHERE id = ?", (olid, book_id))
                updated += 1
            else:
                print(f"❌ {title} → {isbn} → no OLID found")

        conn.commit()
        print(f"✅ Backfilled {updated} OpenLibrary ID(s)")

if __name__ == "__main__":
    backfill_openlibrary_ids()
