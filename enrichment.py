from openai import OpenAI
import os
import json
import re
from openlibrary import fetch_detailed_metadata

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def enrich_book_metadata(title, author, isbn=None, existing=None):
    existing = existing or {}
    enriched = {}

    # 1. Try OpenLibrary
    try:
        if isbn:
            ol_data = fetch_detailed_metadata(isbn=isbn)
            if ol_data and any(ol_data.get(k) for k in ["publisher", "pages", "subjects"]):
                enriched = {
                    "publisher": ol_data.get("publisher", ""),
                    "pub_year": None,  # Not available from OL endpoint
                    "pages": ol_data.get("pages"),
                    "genre": ol_data.get("genre", ""),
                    "fiction_nonfiction": (
                        "Fiction" if "fiction" in ",".join(ol_data.get("subjects", [])).lower() else "Non-fiction"
                    ) if ol_data.get("subjects") else "",
                    "author_gender": "",
                    "tags": ol_data.get("subjects", [])[:5],
                    "cover_url": ol_data.get("cover_url", "")
                }
    except Exception as e:
        print(f"⚠️ OpenLibrary enrichment failed: {e}")

    # 2. If still missing core fields, fall back to GPT
    if not enriched.get("publisher") or not enriched.get("pages"):
        prompt = f"""
Please return metadata for the book:
- Title: {title}
- Author: {author}

Respond with this JSON:
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
                    {"role": "user", "content": prompt}
                ],
                temperature=0.4
            )
            text = response.choices[0].message.content.strip()
            print("🔍 GPT RAW RESPONSE:\n", text)

            if text.startswith("```"):
                text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
                text = re.sub(r"```$", "", text.strip())

            gpt_data = json.loads(text)
            enriched = {**enriched, **gpt_data}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse GPT response: {e}\nRaw: {text}"}
        except Exception as e:
            return {"error": str(e)}

    # 3. Merge with existing (preserve non-empty fields; exclude ISBN!)
    final = {
        "publisher": existing.get("publisher") if existing.get("publisher") else enriched.get("publisher", ""),
        "pub_year": existing.get("pub_year") if existing.get("pub_year") else enriched.get("pub_year"),
        "pages": existing.get("pages") if existing.get("pages") else enriched.get("pages"),
        "genre": existing.get("genre") if existing.get("genre") else enriched.get("genre", ""),
        "fiction_nonfiction": existing.get("fiction_nonfiction") if existing.get("fiction_nonfiction") else enriched.get("fiction_nonfiction", ""),
        "author_gender": existing.get("author_gender") if existing.get("author_gender") else enriched.get("author_gender", ""),
        "tags": existing.get("tags") if existing.get("tags") else enriched.get("tags", []),
        "isbn": existing.get("isbn") if existing.get("isbn") else enriched.get("isbn", ""),
        "cover_url": existing.get("cover_url") if existing.get("cover_url") else enriched.get("cover_url", "")
    }


    return final

