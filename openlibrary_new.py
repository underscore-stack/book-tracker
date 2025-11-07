# openlibrary_new.py
import requests
import time
from datetime import datetime
from operator import itemgetter

DATE_FORMATS = ['%Y', '%b %d, %Y', '%B %d, %Y', '%Y-%m-%d', '%m/%d/%Y', '%B %Y', '%b %Y']
COVER_SIZE = "M"
MAX_LIMIT = 1000
SLEEP_TIME = 0.3
OUTPUT_LIMIT = 10

def parse_ol_date(date_str):
    if not date_str:
        return datetime(1, 1, 1)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return datetime(9999, 12, 31)

def get_cover_url(edition_key, size=COVER_SIZE):
    if not edition_key:
        return ""
    olid = edition_key.split('/')[-1]
    return f"https://covers.openlibrary.org/b/olid/{olid}-{size}.jpg"

def fetch_author_name(author_key):
    if not author_key:
        return ""
    try:
        r = requests.get(f"https://openlibrary.org{author_key}.json", timeout=8)
        r.raise_for_status()
        return r.json().get("name", "")
    except Exception:
        return ""

def search_works(query):
    """Return up to 10 works from the OpenLibrary search endpoint."""
    url = f"https://openlibrary.org/search.json?q={requests.utils.quote(query)}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    data = r.json()
    docs = data.get("docs", [])[:10]
    results = []
    for d in docs:
        results.append({
            "work_id": d.get("key", "").split("/")[-1],
            "title": d.get("title", ""),
            "author": ", ".join(d.get("author_name", [])) if d.get("author_name") else "",
            "first_publish_year": d.get("first_publish_year"),
            "cover_url": f"https://covers.openlibrary.org/b/id/{d.get('cover_i')}-M.jpg" if d.get("cover_i") else "",
        })
    return results

def fetch_editions_for_work(work_id):
    """Paginated fetch of all editions for a given work_id; return top 10 English/unspecified sorted chronologically."""
    base_url = f"https://openlibrary.org/works/{work_id}/editions.json"
    offset, total, all_editions = 0, float('inf'), []
    while offset < total:
        url = f"{base_url}?limit={MAX_LIMIT}&offset={offset}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        data = r.json()
        entries = data.get("entries", [])
        if not entries:
            break
        all_editions.extend(entries)
        total = data.get("size", 0)
        offset += len(entries)
        time.sleep(SLEEP_TIME)

    english_key = {"key": "/languages/eng"}
    filtered = []
    for ed in all_editions:
        langs = ed.get("languages")
        if langs is None or english_key in langs:
            ed["_sort_date"] = parse_ol_date(ed.get("publish_date"))
            filtered.append(ed)

    sorted_ed = sorted(filtered, key=itemgetter("_sort_date"))[:OUTPUT_LIMIT]
    editions = []
    for e in sorted_ed:
        authors = []
        for a in e.get("authors", []):
            nm = fetch_author_name(a.get("key"))
            if nm:
                authors.append(nm)
            time.sleep(0.05)
        editions.append({
            "title": e.get("title", ""),
            "publish_date": e.get("publish_date", ""),
            "publisher": ", ".join(e.get("publishers", [])) if e.get("publishers") else "",
            "pages": e.get("number_of_pages") or e.get("pagination", ""),
            "isbn": (e.get("isbn_13") or e.get("isbn_10") or [None])[0] if isinstance(e.get("isbn_13") or e.get("isbn_10"), list) else None,
            "authors": ", ".join(authors),
            "cover_url": get_cover_url(e.get("key")),
            "edition_url": f"https://openlibrary.org{e.get('key')}" if e.get("key") else "",
        })
    return editions
