# openlibrary.py
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
            "publisher": book.get("publisher", [""])[0],
            "pub_year": book.get("first_publish_year", None),
            "pages": book.get("number_of_pages_median", None),
            "genre": "",
            "cover_url": (
                f"http://covers.openlibrary.org/b/id/{book['cover_i']}-M.jpg"
                if book.get("cover_i") and isinstance(book["cover_i"], int)
                else ""
            ),
            "openlibrary_id": book.get("key", "").replace("/works/", ""),
            "isbn": book.get("isbn", [""])[0]
        })
    return books
