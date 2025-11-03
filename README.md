# book-tracker

Logging all the books I have read.

Warning: this repository previously contained a plaintext "token" file. If you used that token, rotate it now.

Quickstart
1. Create a virtual environment:
   python -m venv .venv
   source .venv/bin/activate

2. Install dependencies:
   pip install -r requirements.txt

3. Create a `.env` file or export the token as an environment variable:
   export BOOKTRACKER_TOKEN="your-token-here"

4. Run the app:
   streamlit run app.py

Notes
- The SQLite DB file `books.db` is created/used at runtime. It's ignored by .gitignore to avoid committing data.
- Do NOT commit secrets. Use environment variables or a secret manager.

Contributing
- Run `black .` and `flake8` before opening a PR.
