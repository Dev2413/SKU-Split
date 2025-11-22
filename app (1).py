import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="SKU Splitter (robust)", layout="wide")
st.title("SKU Splitter — robust parser")

uploaded = st.file_uploader("Upload CSV or Excel (.xlsx)", type=["csv", "xlsx"])
sheet_col = st.text_input("Column name with combined SKUs:", value="SKU sold")
order_col = st.text_input("Column name with Order ID (optional):", value="Order ID")
preview_rows = st.number_input("Preview rows to show:", min_value=5, max_value=1000, value=10)

def try_read(file):
    try:
        if file.name.lower().endswith(".csv"):
            return pd.read_csv(file)
        else:
            return pd.read_excel(file)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None

def parse_cell(cell_text):
    if not isinstance(cell_text, str):
        cell_text = str(cell_text)
    text = cell_text.strip()
    if text == "" or text.lower() in ("nan", "none"):
        return []
    # Primary regex: find "2x SKU name" or "2× SKU name"
    pattern = re.compile(r'(\d+(?:\.\d+)?)\s*[x×]\s*(.*?)(?=(?:\s*\d+(?:\.\d+)?\s*[x×])|$)', flags=re.I | re.S)
    matches = pattern.findall(text)
    if matches:
        return [(float(q), s.strip().rstrip(",;")) for q, s in matches]
    # Fallback: split by comma/semicolon and try to extract qty
    pieces = re.split(r'\s*[;,]\s*', text)
    out = []
    for p in pieces:
        p = p.strip()
        if not p:
            continue
        m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*[x×]\s*(.*)$', p, flags=re.I)
        if m:
            out.append((float(m.group(1)), m.group(2).strip().rstrip(",;")))
            continue
        m2 = re.match(r'^\s*(\d+(?:\.\d+)?)\s+(.+)$', p)
        if m2:
            out.append((float(m2.group(1)), m2.group(2).strip().rstrip(",;")))
            continue
        out.append((1.0, p.rstrip(",;")))
    if out:
        return out
    return [(1.0, text)]

def split_skus(df, sku_col, order_col=None):
    rows = []
    for _, r in df.iterrows():
        text = r.get(sku_col, "")
        parsed = parse_cell(text)
        if not parsed:
            continue
        for qty, sku in parsed:
            row = {"SKU": sku, "Qty": qty}
            if order_col and order_col in df.columns:
                row["Order ID"] = r.get(order_col)
            rows.append(row)
    if rows:
        out = pd.DataFrame(rows)
        # reorder
        cols = ["Order ID", "SKU", "Qty"]
        out = out[[c for c in cols if c in out.columns]]
        return out
    return pd.DataFrame(columns=["Order ID","SKU","Qty"])

if uploaded:
    df = try_read(uploaded)
    if df is None:
        st.stop()

    st.subheader("Source preview")
    st.dataframe(df.head())

    # Show detected SKU-like columns
    candidates = [c for c in df.columns if 'sku' in c.lower() or 'item' in c.lower()]
    st.write("Detected candidate SKU-like columns:", candidates)

    if st.button("Transform / Split SKUs"):
        if sheet_col not in df.columns:
            st.error(f"Column '{sheet_col}' not found. Available columns: {list(df.columns)}")
        else:
            out = split_skus(df, sheet_col, order_col if order_col in df.columns else None)
            if out.empty:
                st.warning("Transformation produced no rows. Showing debug samples from the SKU column.")
                st.subheader("Raw SKU samples (first 30)")
                st.write(df[sheet_col].astype(str).head(30).to_list())
            else:
                st.success("Transformation complete")
                st.dataframe(out.head(preview_rows))

                # Always provide CSV download
                st.download_button("Download CSV", out.to_csv(index=False).encode("utf-8"), "SKU_Split.csv", "text/csv")

                # Try to provide Excel download, but don't crash if openpyxl missing
                try:
                    import openpyxl  # noqa: F401
                    excel_buffer = BytesIO()
                    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                        out.to_excel(writer, index=False, sheet_name="SKU_Split")
                    st.download_button("Download Excel", excel_buffer.getvalue(), "SKU_Split.xlsx",
                                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                except Exception:
                    st.info("Excel download skipped because 'openpyxl' is not installed in the environment. CSV is available.")

else:
    st.info("Upload a CSV or XLSX file to begin.")
