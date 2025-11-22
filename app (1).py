import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="SKU Splitter — Safer Split", layout="wide")
st.title("SKU Splitter — Safer comma-first splitting")

uploaded = st.file_uploader("Upload CSV or Excel (.xlsx)", type=["csv", "xlsx"])
preview_rows = st.number_input("Preview rows to show:", min_value=5, max_value=1000, value=10)

def try_read(file):
    try:
        if file.name.lower().endswith(".csv"):
            return pd.read_csv(file)
        return pd.read_excel(file)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None

def parse_piece(piece_text):
    """
    Parse a single comma/semicolon-separated piece.
    Accept leading qty markers like '2x', '2×', '2 x', or leading number '2 '.
    If none found, assume qty=1 and return full piece as SKU.
    """
    if not isinstance(piece_text, str):
        piece_text = str(piece_text)
    p = piece_text.strip().rstrip(",;")
    if p == "" or p.lower() in ("nan","none"):
        return []
    # Look for leading qty like '2x' or '2×' or '2 x'
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*[x×]\s*(.+)$', p, flags=re.I)
    if m:
        qty = float(m.group(1))
        sku = m.group(2).strip()
        return [(qty, sku)]
    # Look for leading plain number then space: '2 THCA Pack ...'
    m2 = re.match(r'^\s*(\d+(?:\.\d+)?)\s+(.+)$', p)
    if m2:
        qty = float(m2.group(1))
        sku = m2.group(2).strip()
        return [(qty, sku)]
    # No leading qty -> qty = 1, whole piece is SKU
    return [(1.0, p)]

def parse_cell_safe(cell_text):
    """
    Primary: split on commas or semicolons to separate actual items.
    Then parse each piece for leading qty.
    """
    if not isinstance(cell_text, str):
        cell_text = str(cell_text)
    text = cell_text.strip()
    if text == "" or text.lower() in ("nan","none"):
        return []
    # Primary split on comma or semicolon (these are the usual explicit separators)
    pieces = re.split(r'\s*[;,]\s*', text)
    out = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        parsed = parse_piece(piece)
        for qty, sku in parsed:
            out.append((qty, sku))
    if out:
        return out
    # final fallback (shouldn't happen): whole cell as one sku qty=1
    return [(1.0, text)]

def split_skus(df, sku_col, order_col=None):
    rows = []
    for _, r in df.iterrows():
        text = r.get(sku_col, "")
        parsed = parse_cell_safe(text)
        if not parsed:
            continue
        for qty, sku in parsed:
            row = {"SKU": sku, "Qty": qty}
            if order_col and order_col in df.columns:
                row["Order ID"] = r.get(order_col)
            rows.append(row)
    if rows:
        out = pd.DataFrame(rows)
        # reorder columns
        cols = ["Order ID", "SKU", "Qty"]
        out = out[[c for c in cols if c in out.columns]]
        return out
    return pd.DataFrame(columns=["Order ID","SKU","Qty"])

# ---------- UI ----------
if uploaded:
    df = try_read(uploaded)
    if df is None:
        st.stop()
    st.subheader("Source preview")
    st.dataframe(df.head())

    # dropdowns (avoid manual typos)
    col_list = list(df.columns)
    sku_col = st.selectbox("Select SKU column (exact):", options=col_list, index=col_list.index("SKU Sold") if "SKU Sold" in col_list else 0)
    order_col_choice = None
    if any(c.lower() in ("order id","orderid","order_id","order") for c in col_list):
        default_order = next((c for c in col_list if c.lower() in ("order id","orderid","order_id","order")), None)
        # let user optionally pick order id column (first option None)
        order_col_choice = st.selectbox("Select Order ID column (optional):", options=[None] + col_list, index=(col_list.index(default_order)+1) if default_order else 0)

    if st.button("Transform / Split SKUs"):
        out = split_skus(df, sku_col, order_col_choice)
        if out.empty:
            st.warning("Transformation produced no rows. Showing raw SKU samples to debug.")
            st.subheader("Raw SKU samples (first 50)")
            st.write(df[sku_col].astype(str).head(50).to_list())
        else:
            st.success("Transformation complete!")
            st.subheader("Preview of transformed data")
            st.dataframe(out.head(preview_rows))
            # CSV download (always)
            st.download_button("Download CSV", out.to_csv(index=False).encode("utf-8"), "SKU_Split.csv", "text/csv")
            # Excel optional
            try:
                import openpyxl  # noqa: F401
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    out.to_excel(writer, index=False, sheet_name="SKU_Split")
                st.download_button("Download Excel", excel_buffer.getvalue(), "SKU_Split.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Excel download skipped because 'openpyxl' is not installed. CSV is available.")
else:
    st.info("Upload a CSV or XLSX file to begin.")
