import requests
import re

def extract_page_count(ed):
    # Try number_of_pages first
    if ed.get("number_of_pages"):
        try:
            return int(ed["number_of_pages"])
        except:
            pass

    # Fallback to parsing pagination
    pagination = ed.get("pagination")
    if pagination:
        match = re.search(r"\d{2,4}", pagination)
        if match:
            return int(match.group())
    
    return None


def search_books(query):
    url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    response = requests.get(url)
    if response.status_code != 200:
        return []

    results = response.json().get("docs", [])
    books = []
    for book in results:
        books.append({
            "title": book.get("title"),
            "author": ", ".join(book.get("author_name", [])),
            "openlibrary_id": book.get("key", "").replace("/works/", ""),
            "isbn": book.get("isbn", [""])[0] if book.get("isbn") else "",
            "cover_url": (
                f"http://covers.openlibrary.org/b/id/{book['cover_i']}-M.jpg"
                if book.get("cover_i") else ""
            )
        })

    return books
    
import requests
import re

def get_editions_for_work(olid, language="eng"):
    url = f"https://openlibrary.org/works/{olid}/editions.json?limit=100"
    response = requests.get(url)
    if response.status_code != 200:
        return []

    entries = response.json().get("entries", [])

    def extract_year(date_str):
        try:
            return int(re.search(r"\d{4}", date_str).group())
        except:
            return None

    seen_isbns = set()
    editions = []

    for e in entries:
        # Filter by language
        langs = e.get("languages", [])
        if not any(language in l.get("key", "") for l in langs):
            continue

        # Must have ISBN
        isbn = (e.get("isbn_10") or e.get("isbn_13") or [])
        if not isbn:
            continue
        primary_isbn = isbn[0]
        if primary_isbn in seen_isbns:
            continue
        seen_isbns.add(primary_isbn)

        # Omit audiobooks
        format_str = str(e.get("physical_format", "")).lower()
        if "audio" in format_str or "cd" in format_str:
            continue

        editions.append({
            "title": e.get("title", ""),
            "publisher": e.get("publishers", [""])[0] if e.get("publishers") else "",
            "publish_date": e.get("publish_date", ""),
            "publish_year": extract_year(e.get("publish_date", "")),
            "pages": extract_page_count(ed),
            "cover_url": (
                f"http://covers.openlibrary.org/b/id/{e['covers'][0]}-M.jpg"
                if e.get("covers") and isinstance(e["covers"], list) and e["covers"]
                else ""
            ),
            "isbn": primary_isbn,
            "openlibrary_id": e.get("key", "").replace("/books/", "")
        })

    return sorted(editions, key=lambda x: x["publish_year"] if isinstance(x["publish_year"], int) else 9999)

    
def fetch_detailed_metadata(olid=None, isbn=None):
    if isbn:
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn}&format=json&jscmd=data"
        key = f"ISBN:{isbn}"
    elif olid:
        url = f"https://openlibrary.org/api/books?bibkeys=OLID:{olid}&format=json&jscmd=data"
        key = f"OLID:{olid}"
    else:
        return {}

    r = requests.get(url)
    if r.status_code != 200:
        return {}

    data = r.json().get(key, {})
    return {
        "publisher": data.get("publishers", [{}])[0].get("name", ""),
        "pages": data.get("number_of_pages"),
        "isbn": isbn,
        "subjects": [s["name"] for s in data.get("subjects", [])],
    }


