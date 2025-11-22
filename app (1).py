
import streamlit as st
import pandas as pd
import re
from io import BytesIO

DEFAULT_PATH = "/mnt/data/COGS Details.xlsx"

st.set_page_config(page_title="SKU Splitter", layout="wide")

st.title("SKU Splitter — Expand multi‑SKU cells into rows")
st.markdown("""
Upload an Excel (.xlsx) or CSV file that contains a column with combined SKUs (like `SKU sold`).
This app will split entries like `2× SKU A 1g, 1× SKU B 2g` into separate rows with `Order ID`, `SKU` and `Qty`.
""")

uploaded = st.file_uploader("Upload file (optional). If you don't upload, the default file will be used:", type=["xlsx","csv"])
use_default = False
if uploaded is None:
    st.info(f"No file uploaded — will try to load the default file at `{DEFAULT_PATH}` (useful if you already uploaded the file to the server).")
    use_default = True

sheet_col = st.text_input("Column name that contains the combined SKUs:", value="SKU sold")
order_col = st.text_input("Column name that contains the order id (leave blank to skip):", value="Order ID")
preview_rows = st.number_input("Preview rows to show after transform", min_value=5, max_value=1000, value=10)

def load_dataframe(uploaded, use_default):
    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                df = pd.read_csv(uploaded)
            else:
                df = pd.read_excel(uploaded)
        except Exception as e:
            st.error(f"Failed to read uploaded file: {e}")
            return None
    else:
        try:
            df = pd.read_excel(DEFAULT_PATH)
        except Exception as e:
            st.error(f"Failed to read default file at {DEFAULT_PATH}: {e}")
            return None
    return df

def split_skus(df, sku_col, order_col=None):
    rows = []
    pattern = re.compile(r'(\\d+)\\s*[x×]\\s*(.*?)(?=(?:\\s*\\d+\\s*[x×])|$)', flags=re.I)
    for idx, r in df.iterrows():
        order_val = r[order_col] if (order_col and order_col in df.columns) else None
        text = str(r[sku_col]) if sku_col in df.columns else ""
        if not text or text.lower() in ("nan","none"):
            # keep an empty/skipped row or continue
            continue
        matches = pattern.findall(text)
        if not matches:
            # fallback: if no match found, try to extract leading qty if present like "1x SKU..."
            alt = re.findall(r'(\\d+)\\s*[x×]\\s*(.*)', text, flags=re.I)
            if alt:
                matches = alt
            else:
                # if still no match, treat whole cell as one SKU with qty=1
                matches = [("1", text.strip())]
        for qty, sku in matches:
            # Clean SKU text: strip trailing commas/spaces
            clean_sku = sku.strip().rstrip(",")
            row = {}
            if order_col and order_col in df.columns:
                row["Order ID"] = order_val
            row["SKU"] = clean_sku
            try:
                row["Qty"] = float(qty)
            except:
                row["Qty"] = qty
            rows.append(row)
    out = pd.DataFrame(rows)
    return out

df = load_dataframe(uploaded, use_default)
if df is None:
    st.stop()

st.subheader("Source data preview")
st.dataframe(df.head(5))

if st.button("Transform / Split SKUs"):
    if sheet_col not in df.columns:
        st.error(f"Column '{sheet_col}' not found in the file. Available columns: {list(df.columns)}")
    else:
        out = split_skus(df, sheet_col, order_col if order_col in df.columns else None)
        st.success("Transformed!")
        st.subheader("Transformed preview")
        st.dataframe(out.head(preview_rows))

        # Prepare downloads: CSV and Excel
        csv_bytes = out.to_csv(index=False).encode("utf-8")
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            out.to_excel(writer, index=False, sheet_name="SKU_Split")
        excel_data = excel_buffer.getvalue()

        st.download_button("Download CSV", data=csv_bytes, file_name="SKU_Split.csv", mime="text/csv")
        st.download_button("Download Excel", data=excel_data, file_name="SKU_Split.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.markdown("### Notes / Tips")
        st.markdown("""
        - The parser looks for patterns like `1x`, `1×`, `2x`, `2×` (case-insensitive) followed by the SKU text.
        - If no qty/x pattern is found in a cell, the whole cell will be treated as a single SKU with `Qty=1`.
        - If your SKU text sometimes contains the character `x` as part of the SKU name, please share a few examples and I can tune the parser further.
        - To run this app on your machine: `streamlit run app.py`
        """)

st.markdown("---")
st.markdown("Default file path used by this app (server-side):")
st.code(DEFAULT_PATH)
