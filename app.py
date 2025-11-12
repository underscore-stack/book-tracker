# app.py — confirmed no expanders anywhere

import os
import time
from datetime import datetime
from collections import defaultdict
import streamlit as st
from db_google import get_all_books
from covers_google import get_cached_or_drive_cover
from charts_view import show_charts  
from enrichment import enrich_book_metadata

st.set_page_config(page_title="Book Tracker", layout="wide")
def local_css(file_name: str):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Load global stylesheet
local_css("styles.css")

st.title("📚 Book Tracker")

# ---------------------------------
# ADD BOOK SECTION (streamlined UI)
# ---------------------------------
import requests
from operator import itemgetter
from datetime import datetime
import time

DATE_FORMATS = ["%Y", "%b %d, %Y", "%B %d, %Y", "%Y-%m-%d", "%m/%d/%Y", "%B %Y", "%b %Y"]
COVER_SIZE = "M"
MAX_LIMIT = 1000
SLEEP_TIME = 0.35
TOP_RESULTS = 10


def _parse_ol_date(date_str):
    if not date_str:
        return datetime(1, 1, 1)
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(str(date_str).strip(), fmt)
        except ValueError:
            continue
    return datetime(9999, 12, 31)


def _get_cover_url_from_edition_key(edition_key, size=COVER_SIZE):
    if not edition_key:
        return ""
    olid_value = str(edition_key).split("/")[-1]
    return f"https://covers.openlibrary.org/b/olid/{olid_value}-{size}.jpg"


def _first_isbn(ed):
    for fld in ("isbn_13", "isbn13", "isbn_10", "isbn10"):
        v = ed.get(fld)
        if isinstance(v, list) and v:
            return str(v[0])
        if isinstance(v, str) and v.strip():
            return v.strip()
    ids = ed.get("identifiers", {})
    if isinstance(ids, dict):
        for fld in ("isbn_13", "isbn_10"):
            v = ids.get(fld)
            if isinstance(v, list) and v:
                return str(v[0])
    return ""


@st.cache_data(show_spinner=False, ttl=300)
def ol_search_works(q: str):
    url = f"https://openlibrary.org/search.json?q={requests.utils.quote(q)}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    docs = data.get("docs", [])
    out = []
    for d in docs[:TOP_RESULTS * 2]:
        out.append({
            "work_id": (d.get("key") or "").split("/")[-1],
            "title": d.get("title") or d.get("title_suggest") or "Untitled",
            "author": ", ".join(d.get("author_name", []) or []) or "Unknown",
            "first_publish_year": d.get("first_publish_year") or "",
        })
    return out[:TOP_RESULTS]


@st.cache_data(show_spinner=True, ttl=300)
def ol_fetch_editions_sorted(work_id: str):
    base = "https://openlibrary.org"
    offset = 0
    all_editions = []
    total_size = float("inf")

    while offset < total_size:
        url = f"{base}/works/{work_id}/editions.json?limit={MAX_LIMIT}&offset={offset}"
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        payload = r.json()
        entries = payload.get("entries", []) or []
        if not entries:
            break
        all_editions.extend(entries)
        total_size = payload.get("size", 0) or 0
        offset += len(entries)
        time.sleep(SLEEP_TIME)

    english_key = {"key": "/languages/eng"}
    filtered = []
    for ed in all_editions:
        langs = ed.get("languages")
        is_english = langs and english_key in langs
        unspecified = langs is None or len(langs) == 0
        if is_english or unspecified:
            ed["_sort_date"] = _parse_ol_date(ed.get("publish_date"))
            filtered.append(ed)

    filtered_sorted = sorted(filtered, key=itemgetter("_sort_date"))

    norm = []
    for ed in filtered_sorted[:TOP_RESULTS]:
        edition_key = ed.get("key")
        cover_url = _get_cover_url_from_edition_key(edition_key)
        publishers = ed.get("publishers") or []
        if isinstance(publishers, list):
            publisher = ", ".join(publishers)
        else:
            publisher = str(publishers or "")
        norm.append({
            "title": ed.get("title") or "Untitled",
            "publish_date": ed.get("publish_date") or "",
            "pages": ed.get("number_of_pages") or None,
            "publisher": publisher,
            "isbn": _first_isbn(ed),
            "edition_key": edition_key,
            "cover_url": cover_url,
        })
    return norm


# ---- STATE ----
st.session_state.setdefault("ol_results", [])
st.session_state.setdefault("ol_selected_work", None)
st.session_state.setdefault("ol_editions", [])
st.session_state.setdefault("last_added_id", None)

# ---- UI ----
st.markdown("### ➕ Add a Book")
add_book_container = st.container()
with add_book_container:
    st.markdown('<div id="add-book-area">', unsafe_allow_html=True)
    
with st.form("book_search_form"):
    query = st.text_input("Search OpenLibrary (title or author)", key="add_query", placeholder="e.g., The Dead Zone")
    submitted = st.form_submit_button("Search")  # pressing Enter also submits

if submitted and query.strip():
    try:
        st.session_state["ol_results"] = ol_search_works(query.strip())
        st.session_state["ol_selected_work"] = None
        st.session_state["ol_editions"] = []
    except Exception as e:
        st.error(f"OpenLibrary search failed: {e}")

# ---- Results: Works ----
if st.session_state["ol_results"] and not st.session_state["ol_selected_work"]:
    st.markdown("<h4 style='margin-top:0.5em'>Top Matches</h4>", unsafe_allow_html=True)
    with st.container():
        st.markdown(
            "<div style='max-width:50%; font-size:0.9em;'>",
            unsafe_allow_html=True,
        )
        for i, w in enumerate(st.session_state["ol_results"]):
            key_suffix = f"{w['work_id']}_{i}"
            cols = st.columns([5, 3, 2, 1])
            cols[0].markdown(f"**{w['title']}**")
            cols[1].markdown(w["author"])
            cols[2].markdown(str(w["first_publish_year"] or ""))
            if cols[3].button("Select", key=f"sel_work_{key_suffix}"):
                st.session_state["ol_selected_work"] = w
                try:
                    st.session_state["ol_editions"] = ol_fetch_editions_sorted(w["work_id"])
                except Exception as e:
                    st.error(f"Fetching editions failed: {e}")
                    st.session_state["ol_editions"] = []
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

# ---- Results: Editions ----
if st.session_state["ol_selected_work"]:
    w = st.session_state["ol_selected_work"]
    st.markdown(
        f"<h5 style='margin-top:1em'>Selected Work: <em>{w['title']}</em> — {w['author']}</h5>",
        unsafe_allow_html=True,
    )
    eds = st.session_state.get("ol_editions", [])
    if not eds:
        st.info("No editions found.")
    else:
        st.markdown("<div style='max-width:50%; font-size:0.9em;'>", unsafe_allow_html=True)
        for j, ed in enumerate(eds):
            uniq = f"{w['work_id']}_{j}"
            cols = st.columns([1, 5, 3, 2, 1.5])
            with cols[0]:
                if ed["cover_url"]:
                    st.image(ed["cover_url"], width=50)
            cols[1].markdown(f"**{ed['title']}**  \n📅 {ed.get('publish_date','')}")
            cols[2].markdown(ed.get("publisher", ""))
            cols[3].markdown(f"📖 {ed.get('pages') or '—'}  \n🔢 {ed.get('isbn') or ''}")

            if cols[4].button("Add", key=f"add_ed_{uniq}"):
                from db_google import add_book
                
                # --- Normalize values before insert ---
                pub_year = (ed.get("publish_date") or "")[:4]
                try:
                    pub_year = int(pub_year) if pub_year else ""
                except ValueError:
                    pass
                
                pages = ed.get("pages")
                try:
                    pages = int(pages) if pages else ""
                except ValueError:
                    pass
                
                date_finished = datetime.now().strftime("%Y-%m").strip()
                book_data = {
                    "title": ed.get("title") or w["title"],
                    "author": w.get("author", ""),
                    "publisher": ed.get("publisher", ""),
                    "pub_year": pub_year,
                    "pages": pages,
                    "genre": "",
                    "author_gender": "",
                    "fiction_nonfiction": "",
                    "tags": "",
                    "date_finished": date_finished,
                    "cover_url": ed.get("cover_url", ""),
                    "openlibrary_id": w["work_id"],
                    "isbn": ed.get("isbn", ""),
                    "word_count": (ed.get("pages") or 0) * 250 if ed.get("pages") else "",
                }
                try:
                    add_book(book_data)
                    st.success(f"Added: {book_data['title']} ({date_finished})")

                    # close search state and store ID
                    st.session_state["ol_results"] = []
                    st.session_state["ol_selected_work"] = None
                    st.session_state["ol_editions"] = []
                    st.session_state["last_added_id"] = book_data["isbn"] or book_data["title"]

                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to add book: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------------------
# If last_added_id exists, open library
# -------------------------------------
if st.session_state.get("last_added_id"):
    # When returning to library view, highlight or open the new addition
    st.markdown(
        f"<script>window.location.hash='#{st.session_state['last_added_id']}'</script>",
        unsafe_allow_html=True,
    )
st.markdown('</div>', unsafe_allow_html=True)

# ---------- Load data ----------
try:
    books = get_all_books()
except Exception as e:
    st.error(f"⚠️ Could not load books: {e}")
    st.stop()

if not books:
    st.info("No books found in your Google Sheet.")
    st.stop()
    
# ---------- Session for detail view ----------
if "selected_book" not in st.session_state:
    st.session_state["selected_book"] = None
    
# ---------- Library ----------
st.header("📖 Library")

MONTHS = {
    "01": "January","02": "February","03": "March","04": "April",
    "05": "May","06": "June","07": "July","08": "August",
    "09": "September","10": "October","11": "November","12": "December"
}

# Group by year/month
grouped = defaultdict(lambda: defaultdict(list))
for b in books:
    d = b.get("date_finished", "")
    if d and "-" in d:
        y, m = d.split("-")[:2]
        grouped[y][m].append(b)

# Find most recent
try:
    mr = max(
        datetime.strptime(b["date_finished"], "%Y-%m")
        for b in books if b.get("date_finished") and "-" in b["date_finished"]
    )
    RECENT_Y, RECENT_M = str(mr.year), mr.strftime("%m")
except Exception:
    RECENT_Y = RECENT_M = None

# Helper toggle (no expanders)
def toggle(label: str, key: str, default=False):
    if key not in st.session_state:
        st.session_state[key] = default
    cols = st.columns([0.05, 0.95])
    with cols[0]:
        symbol = "▼" if st.session_state[key] else "▶"
        if st.button(symbol, key=f"btn_{key}", help="Expand / collapse"):
            st.session_state[key] = not st.session_state[key]
            st.rerun()
    with cols[1]:
        st.markdown(f"**{label}**")
    st.markdown("<hr style='margin:2px 0;'>", unsafe_allow_html=True)

# ---------- Library structure ----------
for y in sorted(grouped.keys(), reverse=True):
    year_total = sum(len(v) for v in grouped[y].values())
    y_key = f"year_{y}"
    toggle(f"📅 {y} ({year_total} books)", y_key, default=(y == RECENT_Y))

    if st.session_state[y_key]:
        for m in sorted(grouped[y].keys(), reverse=True):
            m_key = f"month_{y}_{m}"
            month_books = grouped[y][m]
            label = f"{MONTHS.get(m, m)} ({len(month_books)} books)"
            toggle(label, m_key, default=(y == RECENT_Y and m == RECENT_M))

            if st.session_state[m_key]:
                for idx, b in enumerate(month_books):
                    unique = f"{y}_{m}_{idx}_{b.get('id','x')}"
                    detail_key = f"detail_open_{unique}"
            
                    if detail_key not in st.session_state:
                        st.session_state[detail_key] = False
            
                    cols = st.columns([1, 5])
                    with cols[0]:
                        cover = get_cached_or_drive_cover(b)
                        if isinstance(cover, str) and os.path.exists(cover):
                            st.image(cover, width=60)
                        else:
                            st.caption("No cover")
            
                    with cols[1]:
                        title = b.get("title", "Untitled")
                        author = b.get("author", "Unknown")
            
                        # make the title look like a hyperlink but act as a toggle button
                        link_label = f"{title}"
                        if st.button(link_label, key=f"titlebtn_{unique}", help="Show / hide details"):
                            st.session_state[detail_key] = not st.session_state[detail_key]
                            st.rerun()
                        st.caption(f"*{author}*")
            
                    # --- Inline detail block ---
                    if st.session_state[detail_key]:
                        with st.container():
                            st.markdown("---")
                            st.markdown(f"### {title}")
                            st.caption(f"by {author}")
                    
                            cols_d = st.columns([1, 3])
                            with cols_d[0]:
                                if cover and os.path.exists(cover):
                                    st.image(cover, width=180)
                            with cols_d[1]:
                                st.markdown(f"**Publisher:** {b.get('publisher','')}")
                                st.markdown(f"**Publication Year:** {b.get('pub_year','')}")
                                st.markdown(f"**Pages:** {b.get('pages','')}")
                                st.markdown(f"**Genre:** {b.get('genre','')}")
                                st.markdown(f"**Fiction / Non-fiction:** {b.get('fiction_nonfiction','')}")
                                st.markdown(f"**Author Gender:** {b.get('author_gender','')}")
                                st.markdown(f"**Tags:** {b.get('tags','')}")
                                st.markdown(f"**Date Finished:** {b.get('date_finished','')}")
                                st.markdown(f"**ISBN:** {b.get('isbn','')}")
                                st.markdown(f"**Word Count:** {b.get('word_count','')}")
                                st.markdown(f"**OpenLibrary ID:** {b.get('openlibrary_id','')}")
                    
                            # --- New enrichment button ---
                            if st.button("🔍 Enrich Metadata", key=f"enrich_{detail_key}"):
                                from enrichment import enrich_book_metadata
                    
                                with st.spinner("Contacting ChatGPT to fill in missing info..."):
                                    existing = {
                                        "publisher": b.get("publisher"),
                                        "pub_year": b.get("pub_year"),
                                        "pages": b.get("pages"),
                                        "genre": b.get("genre"),
                                        "fiction_nonfiction": b.get("fiction_nonfiction"),
                                        "author_gender": b.get("author_gender"),
                                        "tags": b.get("tags"),
                                        "isbn": b.get("isbn"),
                                        "cover_url": b.get("cover_url"),
                                    }
                    
                                    enriched = enrich_book_metadata(
                                        b.get("title"),
                                        b.get("author"),
                                        b.get("isbn"),
                                        existing=existing,
                                    )
                    
                                if "error" in enriched:
                                    st.error(f"Enrichment failed: {enriched['error']}")
                                else:
                                    # merge and update Google Sheet
                                    for k, v in enriched.items():
                                        if v and not b.get(k):  # fill only missing
                                            b[k] = v
                    
                                    from db_google import update_book_metadata_full
                                    try:
                                        update_book_metadata_full(
                                            b.get("id"),
                                            b.get("title"),
                                            b.get("author"),
                                            b.get("publisher"),
                                            b.get("pub_year"),
                                            b.get("pages"),
                                            b.get("genre"),
                                            b.get("author_gender"),
                                            b.get("fiction_nonfiction"),
                                            b.get("tags"),
                                            b.get("date_finished"),
                                            b.get("openlibrary_id"),
                                            b.get("isbn")                                           
                                        )
                                        st.success("✅ Missing metadata filled and saved.")
                                        st.session_state[detail_key] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Could not update Google Sheet: {e}")
                    
                            if st.button("Hide details", key=f"hide_{unique}"):
                                st.session_state[detail_key] = False
                                st.rerun()
    



show_charts(books)
