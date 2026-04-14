# Text to SQL

Ask plain-English questions about your Excel data. Powered by Gemini + SQLite.

## Setup

```bash
pip install -r requirements.txt
streamlit run app.py
```

Enter your Gemini API key in the sidebar when the app opens.

## Usage

1. Paste your **Gemini API key** in the sidebar
2. Upload an **.xlsx** file
3. Type a question like:
   - *How many rows are there?*
   - *What is the average salary?*
   - *Show me the top 5 names by age*
4. Click **Run** — see the SQL query and the answer
