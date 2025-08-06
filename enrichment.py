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
        "publisher": enriched.get("publisher") if not existing.get("publisher") else existing["publisher"],
        "pub_year": enriched.get("pub_year") if not existing.get("pub_year") else existing["pub_year"],
        "pages": existing["pages"] if existing.get("pages") is not None else enriched.get("pages"),
        "genre": enriched.get("genre") if not existing.get("genre") else existing["genre"],
        "fiction_nonfiction": enriched.get("fiction_nonfiction") if not existing.get("fiction_nonfiction") else existing["fiction_nonfiction"],
        "author_gender": enriched.get("author_gender") if not existing.get("author_gender") else existing["author_gender"],
        "tags": enriched.get("tags") if not existing.get("tags") else existing["tags"],
        "isbn": enriched.get("isbn") if not existing.get("isbn") else existing["isbn"],
        "cover_url": enriched.get("cover_url") if not existing.get("cover_url") else existing["cover_url"]
    }

    return final








