import requests

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
    
def get_editions_for_work(olid, language="eng"):
    url = f"https://openlibrary.org/works/{olid}/editions.json?limit=50"
    response = requests.get(url)
    if response.status_code != 200:
        return []

    results = response.json().get("entries", [])
    filtered = [
        e for e in results
        if language in e.get("languages", [{}])[0].get("key", "")
    ]

    def extract_year(date_str):
        try:
            return int(re.search(r"\d{4}", date_str).group())
        except:
            return None

    editions = []
    for e in filtered:
        editions.append({
            "title": e.get("title", ""),
            "publisher": e.get("publishers", [""])[0],
            "publish_date": e.get("publish_date", ""),
            "publish_year": extract_year(e.get("publish_date", "")),
            "cover_url": f"http://covers.openlibrary.org/b/id/{e['covers'][0]}-M.jpg"
                         if e.get("covers") else "",
            "isbn": e.get("isbn_10", [""])[0] if e.get("isbn_10") else e.get("isbn_13", [""])[0] if e.get("isbn_13") else "",
            "openlibrary_id": e.get("key", "").replace("/books/", "")
        })

    return sorted(editions, key=lambda x: x["publish_year"] or 9999)
    
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

