import streamlit as st
import pandas as pd
import re
from io import BytesIO

st.set_page_config(page_title="SKU Splitter", layout="wide")

st.title("SKU Splitter — Expand multi-SKU cells into rows")
st.markdown("""
Upload an Excel (.xlsx) or CSV file that contains a column with combined SKUs (like **SKU sold**).
This app will split entries like `2× SKU A, 1× SKU B` into separate rows with:
- **Order ID**
- **SKU**
- **Qty**
""")

uploaded = st.file_uploader("Upload file:", type=["xlsx", "csv"])

sheet_col = st.text_input("Column name with combined SKUs:", value="SKU sold")
order_col = st.text_input("Column name with Order ID:", value="Order ID")
preview_rows = st.number_input("Number of rows to preview:", min_value=5, max_value=1000, value=10)


# ----------------------------
# SKU SPLITTER FUNCTION
# ----------------------------
def split_skus(df, sku_col, order_col=None):
    rows = []
    pattern = re.compile(r'(\d+)\s*[x×]\s*(.*?)(?=(?:\s*\d+\s*[x×])|$)', flags=re.I)

    for _, r in df.iterrows():
        order_val = r.get(order_col, None)
        text = str(r.get(sku_col, "")).strip()

        if not text or text.lower() in ("nan", "none"):
            continue

        matches = pattern.findall(text)

        # If no "1x" or "2×" pattern exists, treat full cell as one SKU
        if not matches:
            matches = [("1", text)]

        for qty, sku in matches:
            rows.append({
                "Order ID": order_val,
                "SKU": sku.strip().rstrip(","),
                "Qty": float(qty)
            })

    return pd.DataFrame(rows)


# ----------------------------
# UI LOGIC
# ----------------------------
if uploaded:
    try:
        if uploaded.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded)
        else:
            df = pd.read_csv(uploaded)

        st.subheader("Source Data Preview")
        st.dataframe(df.head())

        if st.button("Transform / Split SKUs"):
            out = split_skus(df, sheet_col, order_col)

            st.success("Transformation complete!")
            st.subheader("Preview of Transformed Data")
            st.dataframe(out.head(preview_rows))

            # Download buttons
            csv_bytes = out.to_csv(index=False).encode("utf-8")
            excel_buffer = BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                out.to_excel(writer, index=False, sheet_name="SKU_Split")

            st.download_button("Download CSV", csv_bytes, "SKU_Split.csv", "text/csv")
            st.download_button(
                "Download Excel",
                excel_buffer.getvalue(),
                "SKU_Split.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except Exception as e:
        st.error(f"Error reading file: {e}")

else:
    st.info("Please upload a file to begin.")
