# openlibrary_local.py
import requests
import os
import re

COVERS_DIR = "covers"

if not os.path.exists(COVERS_DIR):
    os.makedirs(COVERS_DIR)

def search_books(query):
    """
    Search OpenLibrary for a title or author and return a list of simplified book dicts.
    Always tries to include an ISBN if present.
    """
    url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ OpenLibrary search failed: {r.status_code}")
            return []
        docs = r.json().get("docs", [])
    except Exception as e:
        print(f"⚠️ OpenLibrary connection error: {e}")
        return []

    books = []
    for b in docs:
        # Pick first valid ISBN (preferring 13-digit)
        isbn = ""
        if "isbn" in b and isinstance(b["isbn"], list):
            isbn_list = sorted(b["isbn"], key=lambda x: len(x), reverse=True)
            isbn = isbn_list[0]
        if not isbn:
            # Try alternate keys (some records use isbn_10 / isbn_13)
            if "isbn_13" in b:
                isbn = b["isbn_13"][0]
            elif "isbn_10" in b:
                isbn = b["isbn_10"][0]
        
        cover_url = f"https://covers.openlibrary.org/b/id/{b['cover_i']}-M.jpg" if b.get("cover_i") else ""
        books.append({
            "title": b.get("title", ""),
            "author": ", ".join(b.get("author_name", [])),
            "openlibrary_id": b.get("key", "").replace("/works/", ""),
            "isbn": isbn,
            "cover_url": cover_url,
            "first_publish_year": b.get("first_publish_year")
        })

    return books


def save_cover(cover_url, isbn=None, olid=None):
    """
    Download a cover image and store it under covers/<isbn_or_olid>.jpg.
    Returns an absolute file path usable by Kivy, or "" on failure.
    Skips download if the cover already exists locally.
    """
    if not cover_url:
        print("⚠️  No cover URL, skipping download")
        return ""

    # Prefer ISBN > OLID > 'unknown' for filename
    identifier = isbn or olid or "unknown"

    os.makedirs(COVERS_DIR, exist_ok=True)
    path = os.path.join(COVERS_DIR, f"{identifier}.jpg")
    abs_path = os.path.abspath(path)

    # ✅ Skip if already exists
    if os.path.exists(path):
        print(f"🟢 Using cached cover for {identifier} at {abs_path}")
        return abs_path

    try:
        print(f"🔽 Downloading cover for {identifier} from {cover_url}")
        r = requests.get(cover_url, timeout=10)
        if r.status_code == 200 and r.content:
            with open(path, "wb") as f:
                f.write(r.content)
            print(f"✅ Saved cover to {abs_path}")
            return abs_path
        else:
            print(f"⚠️  Cover request failed: {r.status_code}")
    except Exception as e:
        print(f"⚠️  Error saving cover for {identifier}: {e}")

    return ""


def fetch_detailed_metadata(olid=None, isbn=None):
    """
    Fetch publisher, page count, and subjects from OpenLibrary.
    Works with either OLID or ISBN.
    """
    if isbn:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        key = f"ISBN:{isbn}"
    elif olid:
        url = f"https://openlibrary.org/api/books?bibkeys=OLID:{olid}&format=json&jscmd=data"
        key = f"OLID:{olid}"
    else:
        return {}

    try:
        import requests
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return {}
        data = r.json().get(key, {})
    except Exception as e:
        print(f"⚠️ fetch_detailed_metadata failed: {e}")
        return {}

    return {
        "publisher": data.get("publishers", [{}])[0].get("name", ""),
        "pages": data.get("number_of_pages"),
        "isbn": isbn,
        "subjects": [s["name"] for s in data.get("subjects", [])],
    }


def fetch_editions_for_work(olid):
    """
    Fetch up to 5 unique English-language editions for a given OpenLibrary work ID (OLID).
    Returns a list of dicts with title, author, isbn, publish_date, publisher, cover_url, and openlibrary_id.
    """
    if not olid:
        return []

    url = f"https://openlibrary.org/works/{olid}/editions.json?limit=50"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            print(f"⚠️ Editions request failed: {r.status_code}")
            return []
        data = r.json()
    except Exception as e:
        print(f"⚠️ Error fetching editions: {e}")
        return []

    editions = []
    seen_isbns = set()  # ✅ avoid duplicates by ISBN

    for e in data.get("entries", []):
        isbn = ""
        if "isbn_13" in e and e["isbn_13"]:
            isbn = e["isbn_13"][0]
        elif "isbn_10" in e and e["isbn_10"]:
            isbn = e["isbn_10"][0]
        if not isbn or isbn in seen_isbns:
            continue
        seen_isbns.add(isbn)

        cover_url = ""
        if e.get("covers"):
            cover_url = f"https://covers.openlibrary.org/b/id/{e['covers'][0]}-M.jpg"

        publisher = e.get("publishers", [""])[0] if e.get("publishers") else ""

        editions.append({
            "title": e.get("title", "(no title)"),
            "author": ", ".join(a.get("name", "") for a in e.get("authors", [])) if e.get("authors") else "",
            "isbn": isbn,
            "publish_date": e.get("publish_date", "Unknown"),
            "publisher": publisher,
            "cover_url": cover_url,
            # ✅ add openlibrary_id for UI
            "openlibrary_id": e.get("key", "").replace("/books/", "")
        })

    # Sort oldest → newest by year
    def parse_date(d):
        import re
        m = re.search(r"\d{4}", d or "")
        return int(m.group(0)) if m else 9999

    editions.sort(key=lambda e: parse_date(e["publish_date"]))
    return editions[:5]

