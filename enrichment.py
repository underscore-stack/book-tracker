from dotenv import load_dotenv
load_dotenv()

import os
import json
import re
from openai import OpenAI
from openlibrary_local import fetch_detailed_metadata

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


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


def enrich_book_metadata(title, author, isbn=None, existing=None):
    existing = existing or {}
    enriched = {}

    # 1️⃣ Try OpenLibrary first
    try:
        if isbn:
            ol_data = fetch_detailed_metadata(isbn=isbn)
            if ol_data and any(ol_data.get(k) for k in ["publisher", "pages", "subjects"]):
                enriched = {
                    "publisher": ol_data.get("publisher", ""),
                    "pub_year": None,  # Not always available
                    "pages": ol_data.get("pages"),
                    "genre": ol_data.get("genre", ""),
                    "fiction_nonfiction": (
                        "Fiction"
                        if "fiction" in ",".join(ol_data.get("subjects", [])).lower()
                        else "Non-fiction"
                    )
                    if ol_data.get("subjects")
                    else "",
                    "author_gender": "",
                    "tags": ol_data.get("subjects", [])[:5],
                    "cover_url": ol_data.get("cover_url", ""),
                }
    except Exception as e:
        print(f"⚠️ OpenLibrary enrichment failed: {e}")

    # 2️⃣ If missing core fields, use GPT enrichment
    if not enriched.get("publisher") or not enriched.get("pages"):
        prompt = f"""
Please return metadata for the book:
- Title: {title}
- Author: {author}

Respond with *only raw JSON* (no backticks, no Markdown formatting) matching this structure:

{{
  "publisher": "",
  "pub_year": null,
  "pages": null,
  "genre": "",
  "fiction_nonfiction": "",
  "author_gender": "",
  "tags": []
}}
"""
        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful book metadata enrichment assistant."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.4,
            )
            text = response.choices[0].message.content.strip()
            print("🔍 GPT RAW RESPONSE:\n", text)

            # Always sanitize before parsing
            cleaned = clean_gpt_json(text)

            try:
                gpt_data = json.loads(cleaned)
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parse failed ({e}). Cleaned text:\n{cleaned}")
                gpt_data = {}

            enriched = {**enriched, **gpt_data}

        except Exception as e:
            print(f"⚠️ GPT enrichment failed: {e}")
            enriched.setdefault("error", str(e))

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
