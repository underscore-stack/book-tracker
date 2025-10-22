# covers_google.py
import io
import os
import hashlib
import requests
import gspread
import streamlit as st
from google.oauth2.service_account import Credentials as SACreds

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# OAuth imports
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials as UserCreds

global CACHE_DIR

CACHE_DIR = os.path.join(os.path.dirname(__file__), "covers_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

SCOPES_DRIVE = ["https://www.googleapis.com/auth/drive.file"]  # file-level scope is enough

def get_local_cover(url: str, isbn: str) -> str:
    """
    Download once, cache locally, and return the local path.
    If already cached, reuse it. Avoids re-downloading for Drive or OpenLibrary covers.
    """
    if not url:
        return ""

    # Normalize identifiers
    clean_isbn = str(isbn or "").strip()

    # Use ISBN if available; otherwise derive a stable hash from the base URL
    import re, hashlib, urllib.parse
    # Remove transient params (like sz=, export=, etc.)
    parsed = urllib.parse.urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    identifier = clean_isbn if clean_isbn else hashlib.sha1(base_url.encode()).hexdigest()[:12]

    path = os.path.join(CACHE_DIR, f"{identifier}.jpg")

    # ✅ Already cached → just return
    if os.path.exists(path) and os.path.getsize(path) > 0:
        # print(f"🟢 Using cached cover: {identifier}")
        return os.path.abspath(path)

    # Download only once
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
        print(f"📥 Cached cover for {identifier} → {path}")
    except Exception as e:
        print(f"⚠️ Failed to download cover for {identifier}: {e}")
        return ""

    return os.path.abspath(path)



def _sa_creds():
    return SACreds.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES_DRIVE
    )

def _user_creds():
    """
    Retrieves stored OAuth token or refreshes it silently if expired.
    Runs local flow only if token.json is missing or invalid.
    """
    token_path = "token.json"
    creds = None

    # Load existing token if it exists
    if os.path.exists(token_path):
        creds = UserCreds.from_authorized_user_file(token_path, SCOPES_DRIVE)
        # ✅ Automatically refresh if expired
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            try:
                creds.refresh(Request())
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
                print("🔄 Token refreshed silently.")
            except Exception as e:
                print("⚠️ Token refresh failed, will trigger new auth:", e)
                creds = None

    # If no valid creds, run full OAuth
    if not creds or not creds.valid:
        client_config = {
            "installed": {
                "client_id": st.secrets["oauth_client"]["client_id"],
                "client_secret": st.secrets["oauth_client"]["client_secret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://127.0.0.1:8765"]
            }
        }
        flow = InstalledAppFlow.from_client_config(client_config, SCOPES_DRIVE)
        creds = flow.run_local_server(host="127.0.0.1", port=8765, open_browser=True)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds


def _drive_service(creds):
    return build("drive", "v3", credentials=creds)

def _upload_with(creds, filename: str, data: bytes) -> str:
    drive = _drive_service(creds)
    folder_id = st.secrets["booktracker"]["covers_folder_id"]
    media = MediaIoBaseUpload(io.BytesIO(data), mimetype="image/jpeg", resumable=False)
    file = drive.files().create(
        body={"name": filename, "parents": [folder_id], "mimeType": "image/jpeg"},
        media_body=media,
        fields="id"
    ).execute()
    file_id = file["id"]
    # return an embeddable link; we’ll transform to thumbnail in the app
    return f"https://drive.google.com/uc?id={file_id}"

def save_cover_to_drive(cover_url: str, isbn: str) -> str:
    """Try service-account upload first, then fall back to OAuth (user-owned)."""
    if not cover_url or not isbn:
        return ""
    try:
        r = requests.get(cover_url, timeout=12)
        r.raise_for_status()
        content = r.content
    except Exception as e:
        print(f"⚠️ download failed for {isbn}: {e}")
        return ""

    # 1) try service account
    try:
        sa = _sa_creds()
        return _upload_with(sa, f"{isbn}.jpg", content)
    except HttpError as e:
        # If this is the quota error, fall back to OAuth
        if e.resp.status == 403 and "Service Accounts do not have storage quota" in str(e):
            print("ℹ️ Falling back to user OAuth for Drive upload (service account has no quota).")
            try:
                user = _user_creds()
                return _upload_with(user, f"{isbn}.jpg", content)
            except Exception as inner:
                print(f"⚠️ OAuth upload failed: {inner}")
                return ""
        else:
            print(f"⚠️ Service-account upload failed: {e}")
            return ""
    except Exception as e:
        print(f"⚠️ Upload error: {e}")
        return ""

def update_cover_url_in_sheet(isbn: str, local_path: str):
    """
    Do NOT overwrite remote cover URLs (e.g., Drive links) with local paths.
    Keeps the Sheet stable for multi-device use.
    """
    print(f"ℹ️ Cached locally for {isbn} at {local_path} (Sheet not updated).")


def get_cached_or_drive_cover(book: dict) -> str:
    """
    Returns a local cover path if cached or downloadable.
    Falls back to Drive/OpenLibrary URL if cache missing.
    """
    isbn = str(book.get("isbn", "")).strip()
    url = str(book.get("cover_url", "")).strip()

    # Case 1: local cache already exists
    local_path = os.path.join(CACHE_DIR, f"{isbn}.jpg")
    if os.path.exists(local_path):
        return local_path

    # Case 2: cover_url is a remote link — download and cache
    if url.startswith("http"):
        cached = get_local_cover(url, isbn)
        if cached:
            return cached

    # Case 3: fallback — return remote URL (for non-cached environments)
    return url

