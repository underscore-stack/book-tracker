from openai import OpenAI
import os
import json
import re
from openlibrary import fetch_detailed_metadata

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def enrich_book_metadata(title, author, isbn=None):
    # 1. Try OpenLibrary enrichment first
    try:
        if isbn:
            ol_data = fetch_detailed_metadata(isbn=isbn)
            if ol_data:
                # If OpenLibrary has decent metadata, use it
                if any(ol_data.get(k) for k in ["publisher", "pages", "genre", "subjects"]):
                    enriched = {
                        "publisher": ol_data.get("publisher", ""),
                        "pub_year": None,  # Not available from OL API by default
                        "pages": ol_data.get("pages"),
                        "genre": ol_data.get("genre", ""),
                        "fiction_nonfiction": (
                            "Fiction" if "fiction" in ",".join(ol_data.get("subjects", [])).lower() else "Non-fiction"
                        ) if ol_data.get("subjects") else "",
                        "author_gender": "",
                        "tags": ol_data.get("subjects", [])[:5]
                    }
                    return enriched
    except Exception as e:
        print(f"⚠️ OpenLibrary enrichment failed: {e}")

    # 2. Fallback to GPT if OpenLibrary doesn’t help
    prompt = f"""
Please return metadata for the book:
- Title: {title}
- Author: {author}
- ISBN: {isbn or 'N/A'}

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

        # Strip code fences
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse GPT response: {e}\nRaw: {text}"}
    except Exception as e:
        return {"error": str(e)}
