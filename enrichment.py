from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
import streamlit as st
import google.generativeai as genai
from datetime import datetime
from openlibrary_local import fetch_detailed_metadata

def clean_gpt_json(text: str) -> str:
    """Strip markdown-style code fences and stray backticks before parsing."""
    if not text:
        return "{}"
    # Remove triple backtick code fences like ```json ... ```
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    # Remove stray single backticks
    text = text.replace("`", "")
    return text


def enrich_book_metadata(title, author, isbn, existing=None):

    try:
        api_key = st.secrets["gemini"]["api_key"]
        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-flash-latest")

        missing_fields = [k for k, v in (existing or {}).items() if not v]
        prompt = f"""
        You are a book metadata specialist. Fill in ONLY missing metadata fields for:
        Title: {title}
        Author: {author}
        ISBN: {isbn}

        Existing metadata:
        {existing}

        Provide a JSON object with fields: publisher, pub_year, pages, genre, fiction_nonfiction, author_gender, tags.
        Do not repeat existing values.
        """

        response = model.generate_content(prompt)
        text = response.text.strip()

        # Try to extract a JSON object safely
        import json, re
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {"error": "No JSON found in Gemini response"}

        enriched = json.loads(match.group(0))
        return enriched

    except Exception as e:
        return {"error": f"Gemini enrichment failed: {e}"}

    # 3️⃣ Merge with existing (preserve existing non-empty fields)
    final = {
        "publisher": existing.get("publisher") or enriched.get("publisher"),
        "pub_year": existing.get("pub_year") or enriched.get("pub_year"),
        "pages": existing.get("pages") or enriched.get("pages"),
        "genre": existing.get("genre") or enriched.get("genre"),
        "fiction_nonfiction": existing.get("fiction_nonfiction") or enriched.get("fiction_nonfiction"),
        "author_gender": existing.get("author_gender") or enriched.get("author_gender"),
        "tags": existing.get("tags") or enriched.get("tags"),
        "isbn": existing.get("isbn") or enriched.get("isbn"),
        "cover_url": existing.get("cover_url") or enriched.get("cover_url"),
    }

    return final



