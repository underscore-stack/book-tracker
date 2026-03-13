from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
import streamlit as st
import anthropic
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
    """
    Enriches book metadata using the Anthropic Claude API.
    Only fills missing fields from the 'existing' dict.

    Args:
        title: Book title
        author: Book author
        isbn: ISBN (optional)
        existing: Dict of existing metadata fields

    Returns:
        Dict with enriched metadata or {"error": "..."} on failure
    """
    existing = existing or {}

    try:
        # Get API key: env var takes priority over Streamlit secrets
        api_key = (
            os.environ.get("ANTHROPIC_API_KEY")
            or st.secrets.get("anthropic", {}).get("api_key")
        )

        # Initialize the Anthropic client
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()

        # Identify which fields are missing
        missing_fields = [k for k, v in existing.items() if not v]

        prompt = f"""You are a book metadata specialist. Fill in ONLY missing metadata fields for:
Title: {title}
Author: {author}
ISBN: {isbn}

Existing metadata:
{json.dumps(existing, indent=2)}

Missing fields that need filling: {', '.join(missing_fields) if missing_fields else 'none'}

Provide a JSON object with these fields (only fill in values for missing fields):
- publisher (string)
- pub_year (integer or null)
- pages (integer or null)
- genre (string)
- fiction_nonfiction (either "Fiction" or "Non-fiction")
- author_gender (one of: "Male", "Female", "Nonbinary", "Multiple", "Unknown", or empty string)
- tags (array of strings, max 5 relevant subject tags)

Do not repeat existing values. Return ONLY the JSON object, no other text."""

        # Call Claude API
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        # Extract text from response
        text = next(
            (block.text for block in response.content if block.type == "text"),
            ""
        ).strip()

        # Clean and parse JSON
        cleaned_text = clean_gpt_json(text)

        try:
            enriched = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse AI response as JSON: {e}\nRaw: {text}"}

        # Merge with existing (preserve existing non-empty fields)
        final = {
            "publisher": existing.get("publisher") or enriched.get("publisher", ""),
            "pub_year": existing.get("pub_year") or enriched.get("pub_year"),
            "pages": existing.get("pages") or enriched.get("pages"),
            "genre": existing.get("genre") or enriched.get("genre", ""),
            "fiction_nonfiction": existing.get("fiction_nonfiction") or enriched.get("fiction_nonfiction", ""),
            "author_gender": existing.get("author_gender") or enriched.get("author_gender", ""),
            "tags": existing.get("tags") or enriched.get("tags", []),
            "isbn": existing.get("isbn") or enriched.get("isbn", isbn),
            "cover_url": existing.get("cover_url") or enriched.get("cover_url", ""),
        }

        return final

    except Exception as e:
        return {"error": f"Claude enrichment failed: {e}"}


