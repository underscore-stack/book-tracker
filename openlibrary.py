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

