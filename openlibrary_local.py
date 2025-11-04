# openlibrary_local.py
# Robust OpenLibrary helpers with English-preference filtering and debug/raw output.

from __future__ import annotations
import requests
import re
import json
from typing import Dict, Any, List, Optional, Tuple

OL_BASE = "https://openlibrary.org"
COVER_BASE = "https://covers.openlibrary.org/b"

# ---------------------------
# Utilities
# ---------------------------

def _http_get_json(url: str, timeout: int = 12) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
    """GET a URL and return (json_or_none, meta) where meta has url/status/raw_text on failure."""
    meta = {"url": url, "status": None, "raw": None}
    try:
        r = requests.get(url, timeout=timeout)
        meta["status"] = r.status_code
        ctype = r.headers.get("content-type", "")
        if r.ok and "json" in ctype:
            payload = r.json()
            meta["raw"] = payload
            return payload, meta
        else:
            # Try parse anyway; if fails, keep raw text for debugging
            try:
                payload = r.json()
                meta["raw"] = payload
                return payload, meta
            except Exception:
                meta["raw"] = r.text
                return None, meta
    except Exception as e:
        meta["raw"] = {"error": str(e)}
        return None, meta

def _extract_languages(ed: Dict[str, Any]) -> List[str]:
    langs = set()
    # editions often: {"languages":[{"key":"/languages/eng"}]}
    if isinstance(ed.get("languages"), list):
        for item in ed["languages"]:
            key = (item or {}).get("key", "")
            if isinstance(key, str) and "/languages/" in key:
                langs.add(key.rsplit("/", 1)[-1].lower())
    # sometimes single fields
    for k in ("language", "language_name"):
        v = ed.get(k)
        if isinstance(v, str) and v.strip():
            val = v.strip().lower()
            if "/languages/" in val:
                val = val.rsplit("/", 1)[-1]
            langs.add(val)
    return sorted(langs) if langs else []

def _normalize_cover_from_entry(ed: Dict[str, Any]) -> Optional[str]:
    # Prefer edition "covers": [bid]
    covers = ed.get("covers") or []
    if isinstance(covers, list) and covers:
        bid = covers[0]
        return f"{COVER_BASE}/id/{bid}-L.jpg"
    # Search API uses 'cover_i'
    if "cover_i" in ed and ed["cover_i"]:
        return f"{COVER_BASE}/id/{ed['cover_i']}-L.jpg"
    # Some editions carry 'cover' / 'cover_url' already
    if isinstance(ed.get("cover"), str):
        return ed["cover"]
    if isinstance(ed.get("cover_url"), str):
        return ed["cover_url"]
    return None

def _first_isbn(ed: Dict[str, Any]) -> Optional[str]:
    for fld in ("isbn_13", "isbn_10", "lccn", "oclc_numbers"):
        vals = ed.get(fld)
        if isinstance(vals, list) and vals:
            return str(vals[0])
        if isinstance(vals, str) and vals.strip():
            return vals.strip()
    return None

def _to_int_year(text: Any) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(18|19|20)\d{2}", str(text))
    return int(m.group(0)) if m else None

def _author_str(doc: Dict[str, Any]) -> str:
    # Search API: 'author_name' is a list
    names = doc.get("author_name") or []
    if isinstance(names, list) and names:
        return ", ".join(names)
    if isinstance(names, str):
        return names
    return doc.get("author") or ""

# ---------------------------
# Search works
# ---------------------------

def search_works(
    title: Optional[str] = None,
    author: Optional[str] = None,
    year: Optional[int] = None,
    limit: int = 10,
    prefer_lang: Tuple[str, ...] = ("eng", "en"),
    timeout: int = 12,
    debug: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Search OpenLibrary works. Returns (results, meta_if_debug).
    Results are normalized dicts:
      {work_key, title, author, first_publish_year, edition_count, cover_url, score}
    """
    params = []
    if title:  params.append(("title", title))
    if author: params.append(("author", author))
    # OpenLibrary supports 'language=eng' in /search.json, but results may still mix; we post-filter too.
    params.append(("limit", str(max(1, limit * 2))))  # overfetch, then filter/rank
    if year:
        params.append(("first_publish_year", str(year)))

    # Add a language hint to search
    params.append(("language", "eng"))

    qstr = "&".join([f"{k}={requests.utils.quote(v)}" for k, v in params])
    url = f"{OL_BASE}/search.json?{qstr}"
    payload, meta = _http_get_json(url, timeout=timeout)

    docs = (payload or {}).get("docs", []) if isinstance(payload, dict) else []
    normalized = []
    for d in docs:
        langs = d.get("language") or []  # e.g. ["eng","spa"]
        langs = [x.lower() for x in langs] if isinstance(langs, list) else []
        is_englishish = any(code in langs for code in prefer_lang) or ("english" in langs)

        norm = {
            "work_key": d.get("key"),                       # e.g. "/works/OL12345W"
            "title": d.get("title") or d.get("title_suggest") or "",
            "author": _author_str(d),
            "first_publish_year": d.get("first_publish_year"),
            "edition_count": d.get("edition_count"),
            "cover_url": _normalize_cover_from_entry(d),
            "languages": langs or None,
            "score": d.get("_score"),
            "is_englishish": is_englishish,
        }
        normalized.append(norm)

    # Prefer English-ish first, then by score, then by edition_count
    normalized.sort(key=lambda x: (
        1 if x.get("is_englishish") else 0,
        x.get("score") or 0,
        x.get("edition_count") or 0,
    ), reverse=True)

    # Trim to limit
    out = normalized[:limit]
    return (out, meta if debug else None)

# ---------------------------
# Editions for a work
# ---------------------------

def fetch_editions_for_work(
    work_olid: str,
    prefer_lang: Tuple[str, ...] = ("eng", "en"),
    limit: int = 50,
    fallback_to_all: bool = True,
    timeout: int = 12,
    debug: bool = False,
) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """
    Fetch editions for a Work OLID (e.g. "OL12345W").
    Returns (editions, meta_if_debug). Each edition:
      {title, publisher, publish_date, publish_year, pages, isbn, cover_url, edition_key, languages}
    - English editions preferred; if none, optionally returns unknown-language editions when fallback_to_all=True
    - Sorted by: has cover, has ISBN, newest publish_year
    - debug=True includes meta with 'url', 'status', 'raw'
    """
    work_olid = work_olid.replace("/works/", "").strip()
    url = f"{OL_BASE}/works/{work_olid}/editions.json?limit={max(10, limit)}"
    payload, meta = _http_get_json(url, timeout=timeout)

    entries = (payload or {}).get("entries", []) if isinstance(payload, dict) else []
    preferred: List[Dict[str, Any]] = []
    unknown: List[Dict[str, Any]] = []

    for ed in entries:
        langs = [l.lower() for l in _extract_languages(ed)]
        is_english = any(code in langs for code in prefer_lang) or ("english" in langs)

        norm = {
            "title": ed.get("title") or ed.get("full_title") or "",
            "publisher": ", ".join(ed.get("publishers", [])) if isinstance(ed.get("publishers"), list)
                         else (ed.get("publisher") or ""),
            "publish_date": ed.get("publish_date") or "",
            "publish_year": _to_int_year(ed.get("publish_date")),
            "pages": ed.get("number_of_pages"),
            "isbn": _first_isbn(ed),
            "cover_url": _normalize_cover_from_entry(ed),
            "edition_key": ed.get("key"),     # e.g. "/books/OL12345M"
            "languages": langs or None,
        }

        if is_english:
            preferred.append(norm)
        elif not langs:
            unknown.append(norm)

    results = preferred if preferred else (unknown if fallback_to_all else [])
    results.sort(key=lambda e: (
        1 if e.get("cover_url") else 0,
        1 if e.get("isbn") else 0,
        e.get("publish_year") or 0
    ), reverse=True)

    return (results[:limit], meta if debug else None)

# ---------------------------
# Detailed metadata for a single item
# ---------------------------

def fetch_detailed_metadata(
    isbn: Optional[str] = None,
    edition_olid: Optional[str] = None,
    work_olid: Optional[str] = None,
    timeout: int = 12,
    debug: bool = False,
) -> Tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Fetch detailed metadata for a single book via ISBN or OLID(s).
    Returns (data, meta_if_debug). Tries to include title, authors, publisher, pages, pub date/year,
    subjects, descriptions, covers, and links back to edition/work.
    Resolution order:
      1) ISBN -> /isbn/{isbn}.json (edition)
      2) edition_olid -> /books/{olid}.json
      3) work_olid -> /works/{olid}.json
    """
    meta_bundle = {"steps": []}

    def step(label, m):
        meta_bundle["steps"].append({label: m})

    # 1) ISBN → edition
    if isbn:
        url = f"{OL_BASE}/isbn/{isbn}.json"
        ed, m = _http_get_json(url, timeout=timeout)
        step("isbn_lookup", m)
        if ed:
            data, m2 = _hydrate_from_edition_json(ed, timeout=timeout)
            step("edition_hydrate", m2)
            return (data, meta_bundle if debug else None)

    # 2) Edition OLID
    if edition_olid:
        eo = edition_olid.replace("/books/", "").strip()
        url = f"{OL_BASE}/books/{eo}.json"
        ed, m = _http_get_json(url, timeout=timeout)
        step("edition_lookup", m)
        if ed:
            data, m2 = _hydrate_from_edition_json(ed, timeout=timeout)
            step("edition_hydrate", m2)
            return (data, meta_bundle if debug else None)

    # 3) Work OLID
    if work_olid:
        wo = work_olid.replace("/works/", "").strip()
        url = f"{OL_BASE}/works/{wo}.json"
        wk, m = _http_get_json(url, timeout=timeout)
        step("work_lookup", m)
        if wk:
            data = {
                "title": wk.get("title"),
                "description": _extract_description(wk.get("description")),
                "subjects": wk.get("subjects", []),
                "work_key": f"/works/{wo}",
                "covers": _covers_from_work(wk),
            }
            return (data, meta_bundle if debug else None)

    # Fallback empty
    return ({}, meta_bundle if debug else None)

def _hydrate_from_edition_json(ed_json: Dict[str, Any], timeout: int = 12) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Build a rich dict from an edition JSON; fetches author names and work info when available.
    Returns (data, meta) where meta aggregates each sub-request.
    """
    meta = {"subcalls": []}
    def note(label, m): meta["subcalls"].append({label: m})

    data = {
        "title": ed_json.get("title"),
        "subtitle": ed_json.get("subtitle"),
        "publish_date": ed_json.get("publish_date"),
        "publish_year": _to_int_year(ed_json.get("publish_date")),
        "number_of_pages": ed_json.get("number_of_pages"),
        "publishers": ed_json.get("publishers"),
        "identifiers": {k: v for k, v in ed_json.items() if "isbn" in k.lower()},
        "edition_key": ed_json.get("key"),
        "covers": _covers_from_edition(ed_json),
        "subjects": ed_json.get("subjects", []),
        "description": _extract_description(ed_json.get("description")),
    }

    # Authors
    author_names = []
    for a in ed_json.get("authors", []):
        key = (a or {}).get("key")  # e.g. "/authors/OL123A"
        if key:
            url = f"{OL_BASE}{key}.json"
            aj, m = _http_get_json(url, timeout=timeout)
            note("author", m)
            if aj and aj.get("name"):
                author_names.append(aj["name"])
    data["authors"] = author_names or None

    # Work (to fill description/subjects/covers if edition sparse)
    work_key = None
    works = ed_json.get("works") or []
    if works:
        work_key = (works[0] or {}).get("key")
    if work_key:
        url = f"{OL_BASE}{work_key}.json"
        wk, m = _http_get_json(url, timeout=timeout)
        note("work", m)
        if wk:
            data.setdefault("description", _extract_description(wk.get("description")))
            if not data.get("covers"):
                data["covers"] = _covers_from_work(wk)
            if not data.get("subjects"):
                data["subjects"] = wk.get("subjects", [])

    return data, meta

def _extract_description(desc_field: Any) -> Optional[str]:
    # description may be str or {"value": "..."}
    if isinstance(desc_field, str):
        return desc_field
    if isinstance(desc_field, dict):
        val = desc_field.get("value")
        if isinstance(val, str):
            return val
    return None

def _covers_from_edition(ed_json: Dict[str, Any]) -> List[str]:
    out = []
    covers = ed_json.get("covers") or []
    if isinstance(covers, list):
        for bid in covers:
            out.append(f"{COVER_BASE}/id/{bid}-L.jpg")
    # Some editions carry 'cover' or 'cover_i'
    if "cover_i" in ed_json and ed_json["cover_i"]:
        out.append(f"{COVER_BASE}/id/{ed_json['cover_i']}-L.jpg")
    return out

def _covers_from_work(wk_json: Dict[str, Any]) -> List[str]:
    out = []
    covers = wk_json.get("covers") or []
    if isinstance(covers, list):
        for bid in covers:
            out.append(f"{COVER_BASE}/id/{bid}-L.jpg")
    return out

# ---------------------------
# Handy demo / debugging usage
# ---------------------------

if __name__ == "__main__":
    # Simple quick test from CLI:
    results, meta = search_works(title="The Stand", author="Stephen King", limit=5, debug=True)
    print("SEARCH URL:", (meta or {}).get("url"))
    print("Top results:")
    for r in results:
        print("-", r["title"], "|", r.get("author"), "|", r.get("work_key"))
    if results:
        wk = (results[0]["work_key"] or "").split("/")[-1]
        eds, meta2 = fetch_editions_for_work(wk, debug=True)
        print("\nEDITIONS URL:", (meta2 or {}).get("url"))
        print("First 3 editions:")
        for e in eds[:3]:
            print("  *", e["title"], "|", e.get("publisher"), "|", e.get("publish_year"), "|", e.get("isbn"))
