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

import requests

def _is_english(lang_list):
    # Accept missing language (lots of older recs), otherwise require ENG.
    if not lang_list:
        return True
    for l in lang_list:
        key = ""
        if isinstance(l, dict):
            key = l.get("key", "")
        elif isinstance(l, str):
            key = l
        if key.endswith("/eng"):
            return True
    return False

def _best_isbn(ed):
    for key in ("isbn_13", "isbn_10"):
        vals = ed.get(key)
        if isinstance(vals, list) and vals:
            return str(vals[0])
        if isinstance(vals, str) and vals.strip():
            return vals.strip()
    return ""

def _cover_from_edition(ed):
    """
    Priority:
      1) covers[] positive id → b/id/{id}-M.jpg
      2) edition OLID        → b/olid/{OLID}-M.jpg  (very reliable)
      3) first ISBN          → b/isbn/{isbn}-M.jpg
      4) return "" (no cover)
    Never return a URL if it would be '.../b/id/0-...'
    """
    # 1) explicit cover ids
    covers = ed.get("covers") or []
    if isinstance(covers, list) and covers:
        try:
            cid = int(covers[0])
            if cid > 0:
                return f"https://covers.openlibrary.org/b/id/{cid}-M.jpg"
        except Exception:
            pass

    # 2) OLID (edition key)
    olid = _edition_olid(ed)
    if olid:
        return f"https://covers.openlibrary.org/b/olid/{olid}-M.jpg"

    # 3) ISBN
    isbn = _best_isbn(ed)
    if isbn:
        return f"https://covers.openlibrary.org/b/isbn/{isbn}-M.jpg"

    # 4) nothing
    return ""

def _edition_olid(ed):
    # ed["key"] looks like "/books/OL12345M"
    k = ed.get("key", "")
    if isinstance(k, str) and k.startswith("/books/"):
        return k[len("/books/"):]
    return ""
    
def fetch_editions_for_work(olid: str, limit: int = 25):
    import requests
    if not olid:
        return []
    url = f"https://openlibrary.org/works/{olid}/editions.json?limit={limit}"
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        entries = r.json().get("entries", [])
    except Exception as e:
        print(f"⚠️ editions fetch failed for {olid}: {e}")
        return []

    out = []
    for ed in entries:
        if not _is_english(ed.get("languages")):
            continue

        # normalize publish year if present (best-effort)
        publish_date = ed.get("publish_date", "") or ""
        m = re.search(r"\b(1[89]\d{2}|20\d{2})\b", publish_date)
        publish_year = int(m.group(0)) if m else None

        out.append({
            "openlibrary_id": _edition_olid(ed),
            "title": ed.get("title") or "",
            "author": ", ".join(a.get("name", "") for a in ed.get("authors", []) if isinstance(a, dict)) or "",
            "publisher": ", ".join(ed.get("publishers", [])) if isinstance(ed.get("publishers"), list) else (ed.get("publishers") or ""),
            "publish_date": publish_date,
            "publish_year": publish_year,
            "pages": ed.get("number_of_pages"),
            "isbn": _best_isbn(ed),
            "cover_url": _cover_from_edition(ed),   # never a 0-id URL
        })
    return out




