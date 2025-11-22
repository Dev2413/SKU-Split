import streamlit as st
import pandas as pd
import re
from io import BytesIO

# ---------- Page ----------
st.set_page_config(page_title="SKU Splitter — Robust (Safer)", layout="wide")
st.title("SKU Splitter — Safer comma-first splitting")
st.write("Split multi-SKU cells into separate rows. Safer parsing: split items by commas/semicolons first, "
         "then extract leading qty. This avoids interpreting measurements like `3 X 4 Grams` as separate items.")

# ---------- Upload / server-file option ----------
uploaded = st.file_uploader("Upload CSV or Excel (.xlsx)", type=["csv", "xlsx"])
use_server_file = st.checkbox("Use server test file (for debugging only)", value=False)
# Path of the file you uploaded earlier on this server (for debug/testing on same machine)
SERVER_TEST_PATH = "/mnt/data/Order Report (Jan - Dec 2024).csv"
if use_server_file:
    st.info(f"Using server file: `{SERVER_TEST_PATH}` (only available if running on same machine/server).")

preview_rows = st.number_input("Preview rows to show:", min_value=5, max_value=1000, value=10)

# ---------- Helpers ----------
def try_read_file_obj(file_obj, is_server_path=False):
    try:
        if is_server_path:
            path = file_obj
            if path.lower().endswith(".csv"):
                return pd.read_csv(path, encoding="utf-8", low_memory=False)
            return pd.read_excel(path)
        else:
            name = file_obj.name.lower()
            if name.endswith(".csv"):
                return pd.read_csv(file_obj, encoding="utf-8", low_memory=False)
            return pd.read_excel(file_obj)
    except Exception as e:
        st.error(f"Failed to read file: {e}")
        return None

def parse_piece(piece_text):
    """
    Parse a single comma/semicolon-separated piece.
    Accept leading qty markers like '2x', '2×', '2 x', or leading number '2 '.
    If none found, assume qty=1 and return whole piece as SKU.
    """
    if not isinstance(piece_text, str):
        piece_text = str(piece_text)
    p = piece_text.strip().rstrip(",;")
    if p == "" or p.lower() in ("nan","none"):
        return []
    # leading quantity like '2x', '2×', '2 x'
    m = re.match(r'^\s*(\d+(?:\.\d+)?)\s*[x×]\s*(.+)$', p, flags=re.I)
    if m:
        qty = float(m.group(1))
        sku = m.group(2).strip()
        return [(qty, sku)]
    # leading plain number then space: '2 THCA Pack'
    m2 = re.match(r'^\s*(\d+(?:\.\d+)?)\s+(.+)$', p)
    if m2:
        qty = float(m2.group(1)); sku = m2.group(2).strip()
        return [(qty, sku)]
    # no leading qty -> qty 1
    return [(1.0, p)]

def parse_cell_safe(cell_text):
    """Split on commas/semicolons first, then parse each piece for leading qty."""
    if not isinstance(cell_text, str):
        cell_text = str(cell_text)
    text = cell_text.strip()
    if text == "" or text.lower() in ("nan","none"):
        return []
    # Primary split on comma or semicolon
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
    # Fallback: whole cell as single SKU qty=1
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
        cols = ["Order ID", "SKU", "Qty"]
        return out[[c for c in cols if c in out.columns]]
    return pd.DataFrame(columns=["Order ID","SKU","Qty"])

# ---------- Main UI logic ----------
df = None
if use_server_file:
    df = try_read_file_obj(SERVER_TEST_PATH, is_server_path=True)
elif uploaded:
    df = try_read_file_obj(uploaded, is_server_path=False)

if df is not None:
    st.subheader("Source preview")
    st.dataframe(df.head())

    # Column selection via dropdown (avoid casing/spacing typos)
    col_list = list(df.columns)
    default_sku = next((c for c in col_list if c.strip().lower() == "sku sold"), col_list[0])
    sku_col = st.selectbox("Select SKU column (exact):", options=col_list, index=col_list.index(default_sku))
    # optional order id
    order_candidates = [c for c in col_list if c.strip().lower() in ("order id","orderid","order_id","order")]
    order_col_choice = None
    if order_candidates:
        order_col_choice = st.selectbox("Select Order ID column (optional):", options=[None] + col_list,
                                        index=(col_list.index(order_candidates[0]) + 1))
    else:
        order_col_choice = st.selectbox("Select Order ID column (optional):", options=[None] + col_list, index=0)

    if st.button("Transform / Split SKUs"):
        out = split_skus(df, sku_col, order_col_choice if order_col_choice else None)
        if out.empty:
            st.warning("Transformation produced no rows. Showing debug SKU samples (first 50) to help tune parser.")
            st.subheader("Raw SKU samples (first 50)")
            st.write(df[sku_col].astype(str).head(50).to_list())
        else:
            st.success("Transformation complete!")
            st.subheader("Preview of transformed data")
            st.dataframe(out.head(preview_rows))

            # CSV download (always available)
            st.download_button("Download CSV", out.to_csv(index=False).encode("utf-8"),
                               "SKU_Split.csv", "text/csv")

            # Excel download: attempt only if openpyxl exists
            try:
                import openpyxl  # noqa: F401
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    out.to_excel(writer, index=False, sheet_name="SKU_Split")
                st.download_button("Download Excel", excel_buffer.getvalue(), "SKU_Split.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception:
                st.info("Excel download skipped because 'openpyxl' is not installed. Add 'openpyxl' to requirements.txt to enable .xlsx downloads.")
else:
    st.info("Upload a CSV/XLSX file or enable 'Use server test file' to begin.")
