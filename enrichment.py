from openai import OpenAI
import os
import json
import re


client = OpenAI(api_key="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")

def enrich_book_metadata(title, author, isbn=None):
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

        # Remove Markdown code fences like ```json ... ```
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE)
            text = re.sub(r"```$", "", text.strip())

        return json.loads(text)
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse GPT response: {e}\nRaw: {text}"}
    except Exception as e:
        return {"error": str(e)}
