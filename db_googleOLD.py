# db_google.py
import os
import json
import datetime
from typing import List, Dict, Any

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import streamlit as st

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def _get_creds():
    sa_info = st.secrets["gcp_service_account"]
    return Credentials.from_service_account_info(sa_info, scopes=SCOPES)

def _sheet():
    creds = _get_creds()
    gc = gspread.authorize(creds)
    sheet_id = st.secrets["booktracker"]["sheet_id"]
    sh = gc.open_by_key(sheet_id)
    ws = sh.worksheet("books")
    return ws

def _drive():
    creds = _get_creds()
    return build("drive", "v3", credentials=creds)

def _ensure_header(ws):
    header = ws.row_values(1)
    needed = [
        "id","title","author","publisher","pub_year","pages","genre",
        "author_gender","fiction_nonfiction","tags","date_finished",
        "cover_url","openlibrary_id","isbn","word_count"
    ]
    if header != needed:
        ws.clear()
        ws.append_row(needed)

def get_all_books() -> List[Dict[str, Any]]:
    ws = _sheet()
    _ensure_header(ws)
    rows = ws.get_all_records()
    # sort newest first
    rows.sort(key=lambda r: int(r["id"]) if str(r.get("id","")).isdigit() else 0, reverse=True)
    return rows

def _next_id(ws):
    vals = ws.col_values(1)[1:]  # skip header
    ints = [int(v) for v in vals if v.isdigit()]
    return (max(ints) + 1) if ints else 1

def add_book(book: Dict[str, Any]) -> None:
    ws = _sheet()
    _ensure_header(ws)
    next_id = _next_id(ws)
    book["id"] = next_id
    # Fill missing numeric or optional fields
    for key in ("pub_year","pages","word_count"):
        if not book.get(key):
            book[key] = ""
    if book.get("pages") and not book.get("word_count"):
        book["word_count"] = int(book["pages"]) * 250
    row = [
        book.get("id"),
        book.get("title",""), book.get("author",""), book.get("publisher",""),
        book.get("pub_year",""), book.get("pages",""), book.get("genre",""),
        book.get("author_gender",""), book.get("fiction_nonfiction",""),
        book.get("tags",""), book.get("date_finished",""), book.get("cover_url",""),
        book.get("openlibrary_id",""), book.get("isbn",""), book.get("word_count","")
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")

def update_book_metadata_full(book_id: int, title, author, publisher, pub_year, pages, genre,
                              gender, fiction, tags, date_finished, isbn, openlibrary_id):
    ws = _sheet()
    _ensure_header(ws)
    all_rows = ws.get_all_records()
    for i, r in enumerate(all_rows, start=2):
        if str(r.get("id")) == str(book_id):
            ws.update(f"A{i}:O{i}", [[
                book_id, title, author, publisher, pub_year or "", pages or "", genre, gender,
                fiction, tags, date_finished, r.get("cover_url",""), openlibrary_id, isbn,
                int(pages)*250 if pages else r.get("word_count","")
            ]], value_input_option="USER_ENTERED")
            return

def delete_book(book_id: int):
    ws = _sheet()
    _ensure_header(ws)
    all_rows = ws.get_all_records()
    for i, r in enumerate(all_rows, start=2):
        if str(r.get("id")) == str(book_id):
            ws.delete_rows(i)
            return

