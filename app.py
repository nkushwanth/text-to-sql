import streamlit as st
import pandas as pd
import sqlite3
import google.generativeai as genai
import re

st.set_page_config(page_title="Text to SQL", page_icon="🗄️")
st.title("🗄️ Text to SQL")
st.caption("Upload multiple Excel files, ask questions across all of them.")

# ── Persistent in-memory SQLite connection ───────────────────────────────────
if "conn" not in st.session_state:
    st.session_state.conn = sqlite3.connect(":memory:", check_same_thread=False)

if "tables" not in st.session_state:
    # dict: table_name -> {"file": filename, "shape": (rows, cols), "columns": [...]}
    st.session_state.tables = {}

conn = st.session_state.conn

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")
    api_key = st.text_input("Gemini API Key", type="password", placeholder="AIza...")
    st.markdown("---")

    st.header("📂 Loaded Tables")
    if st.session_state.tables:
        for tname, meta in st.session_state.tables.items():
            st.markdown(f"**`{tname}`** — {meta['file']}  \n{meta['shape'][0]} rows × {meta['shape'][1]} cols")
        if st.button("🗑️ Clear all tables"):
            for tname in list(st.session_state.tables.keys()):
                conn.execute(f'DROP TABLE IF EXISTS "{tname}"')
            conn.commit()
            st.session_state.tables = {}
            st.rerun()
    else:
        st.info("No tables loaded yet.")

# ── File Upload ───────────────────────────────────────────────────────────────
st.subheader("📁 Upload Excel Files")
uploaded_files = st.file_uploader(
    "Add one or more Excel files",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
)

if uploaded_files:
    for uploaded_file in uploaded_files:
        base = re.sub(r"[^a-zA-Z0-9_]", "_", uploaded_file.name.rsplit(".", 1)[0])
        if base[0].isdigit():
            base = "t_" + base

        if base in st.session_state.tables:
            continue

        xls = pd.ExcelFile(uploaded_file)
        sheet_names = xls.sheet_names

        if len(sheet_names) > 1:
            sheet = st.selectbox(
                f"Sheet for **{uploaded_file.name}**", sheet_names, key=f"sheet_{base}"
            )
        else:
            sheet = sheet_names[0]

        df = pd.read_excel(uploaded_file, sheet_name=sheet)
        df.columns = [re.sub(r"[^a-zA-Z0-9_]", "_", str(c)) for c in df.columns]

        df.to_sql(base, conn, index=False, if_exists="replace")
        conn.commit()

        st.session_state.tables[base] = {
            "file": uploaded_file.name,
            "shape": df.shape,
            "columns": list(df.columns),
        }
        st.success(f"✅ Loaded **{uploaded_file.name}** → table `{base}`")

# ── Preview section ───────────────────────────────────────────────────────────
if st.session_state.tables:
    st.subheader("📋 Table Previews")
    tabs = st.tabs(list(st.session_state.tables.keys()))
    for tab, tname in zip(tabs, st.session_state.tables.keys()):
        with tab:
            meta = st.session_state.tables[tname]
            st.caption(f"File: {meta['file']} | {meta['shape'][0]} rows × {meta['shape'][1]} cols")
            preview = pd.read_sql_query(f'SELECT * FROM "{tname}" LIMIT 10', conn)
            st.dataframe(preview, use_container_width=True)

    # ── Schema string for Gemini ──────────────────────────────────────────────
    schema_lines = []
    for tname, meta in st.session_state.tables.items():
        col_str = ", ".join(meta["columns"])
        schema_lines.append(f'Table "{tname}" (from {meta["file"]}): {col_str}')
    full_schema = "\n".join(schema_lines)

    # ── Query ─────────────────────────────────────────────────────────────────
    st.subheader("💬 Ask a Question")
    st.caption("You can ask about any table or compare across tables.")
    user_query = st.text_input(
        "Your question",
        placeholder="e.g. How many rows in each file? / Compare totals between sales and returns",
    )

    if st.button("Run", type="primary") and user_query:
        if not api_key:
            st.error("Please enter your Gemini API key in the sidebar.")
        else:
            with st.spinner("Generating SQL..."):
                try:
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel("gemini-2.5-flash")

                    prompt = f"""You are an expert SQLite SQL generator.

Here are the available tables and their columns:
{full_schema}

Generate a single valid SQLite SQL query to answer this question:
"{user_query}"

Rules:
- Return ONLY the raw SQL query — no markdown, no backticks, no explanation.
- Always quote table names with double-quotes, e.g. SELECT * FROM "table_name".
- You may JOIN across tables if the question involves comparing or relating them.
- Use only columns that exist in the schema above.
"""
                    response = model.generate_content(prompt)
                    sql = response.text.strip()
                    sql = re.sub(r"^```[a-zA-Z]*\n?", "", sql)
                    sql = re.sub(r"```$", "", sql).strip()

                    st.subheader("🧾 Generated SQL")
                    st.code(sql, language="sql")

                    try:
                        result_df = pd.read_sql_query(sql, conn)
                        st.subheader("✅ Result")
                        if result_df.empty:
                            st.info("Query returned no results.")
                        elif result_df.shape == (1, 1):
                            val = result_df.iloc[0, 0]
                            st.metric(label=result_df.columns[0], value=val)
                        else:
                            st.dataframe(result_df, use_container_width=True)
                            st.caption(f"{len(result_df)} rows returned")
                    except Exception as e:
                        st.error(f"SQL execution error: {e}")

                except Exception as e:
                    st.error(f"Gemini API error: {e}")

else:
    st.info("👆 Upload one or more Excel files to get started.")
