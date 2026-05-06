import streamlit as st
import pandas as pd
import csv
from io import StringIO
from collections import Counter

st.set_page_config(page_title="Order Price Updater", layout="wide")
st.title("Order Price Updater")

uploaded_file = st.file_uploader("Upload TXT/CSV file", type=["txt", "csv"])

if uploaded_file:
    raw_bytes = uploaded_file.read()

    try:
        content = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw_bytes.decode("cp1256", errors="replace")

    lines = content.splitlines()

    if len(lines) < 2:
        st.error("File does not contain enough rows.")
        st.stop()

    title_line = lines[0]
    data_lines = lines[1:]

    rows = []
    skipped_rows = []

    for line_no, line in enumerate(data_lines, start=2):
        if not line.strip():
            continue

        try:
            parsed = next(csv.reader([line]))
            rows.append(parsed)
        except Exception as e:
            skipped_rows.append((line_no, str(e)))

    if not rows:
        st.error("No valid data rows found.")
        st.stop()

    max_cols = max(len(r) for r in rows)
    rows = [r + [""] * (max_cols - len(r)) for r in rows]

    df = pd.DataFrame(rows).fillna("").astype(str)

    # Column indexes
    PRICE_COL = 8          # Column I
    STOCK_COL = 2          # Column C
    ASSET_MANAGER_COL = 18 # Column S
    ORDER_COL = 20         # Column U

    required_cols = max(PRICE_COL, STOCK_COL, ASSET_MANAGER_COL, ORDER_COL) + 1

    if df.shape[1] < required_cols:
        st.error(f"File has only {df.shape[1]} columns. Expected at least {required_cols}.")
        st.stop()

    st.success(f"File loaded successfully. Rows: {len(df):,}")

    if skipped_rows:
        st.warning(f"{len(skipped_rows)} malformed rows were skipped.")

    invalid_values = ["", "None", "none", "NONE", "nan", "NaN", "NAN", "null", "NULL"]

    # Clean relevant columns
    df[ORDER_COL] = df[ORDER_COL].astype(str).str.strip()
    df[STOCK_COL] = df[STOCK_COL].astype(str).str.strip()
    df[PRICE_COL] = df[PRICE_COL].astype(str).str.strip()
    df[ASSET_MANAGER_COL] = df[ASSET_MANAGER_COL].astype(str).str.strip()

    valid_df = df[
        ~df[ORDER_COL].isin(invalid_values)
        & ~df[STOCK_COL].isin(invalid_values)
    ].copy()

    def get_mode_value(series):
        values = [
            str(x).strip()
            for x in series
            if str(x).strip() not in invalid_values
        ]

        if not values:
            return ""

        counts = Counter(values)
        return counts.most_common(1)[0][0]

    # Build one row per order
    orders = (
        valid_df
        .groupby(ORDER_COL, as_index=False)
        .agg({
            STOCK_COL: "first",
            PRICE_COL: "first",
            ASSET_MANAGER_COL: get_mode_value
        })
    )

    orders = orders.rename(columns={
        ORDER_COL: "Order Number",
        STOCK_COL: "Stock Name",
        PRICE_COL: "Current Price",
        ASSET_MANAGER_COL: "Asset Manager"
    })

    st.subheader("Enter New Prices")
    st.write(f"Valid unique orders found: **{len(orders):,}**")

    new_prices = {}

    for _, row in orders.iterrows():
        order_no = str(row["Order Number"]).strip()
        stock_name = str(row["Stock Name"]).strip()
        asset_manager = str(row["Asset Manager"]).strip()
        current_price = str(row["Current Price"]).strip()

        col1, col2, col3, col4 = st.columns([2, 4, 4, 2])

        with col1:
            st.write(f"**Order:** {order_no}")

        with col2:
            st.write(f"**Stock:** {stock_name}")

        with col3:
            st.write(f"**Asset Manager:** {asset_manager}")

        with col4:
            new_price = st.text_input(
                "New Price",
                value=current_price,
                key=f"price_{order_no}"
            )
            new_prices[order_no] = new_price.strip()

    if st.button("Generate Updated CSV"):
        updated_df = df.copy()
        errors = []

        for order_no, price in new_prices.items():
            order_no = str(order_no).strip()
            price = str(price).strip()

            if price in invalid_values:
                errors.append(f"Order {order_no}: price is empty")
                continue

            try:
                price_float = float(price)

                if price_float < 0:
                    errors.append(f"Order {order_no}: price cannot be negative")
                    continue

                if "." in price and len(price.split(".")[1]) > 4:
                    errors.append(f"Order {order_no}: price cannot exceed 4 decimals")
                    continue

                updated_df.loc[
                    updated_df[ORDER_COL].astype(str).str.strip() == order_no,
                    PRICE_COL
                ] = price

            except ValueError:
                errors.append(f"Order {order_no}: invalid price")

        if errors:
            st.error("Please fix these errors:")
            for err in errors:
                st.write(f"- {err}")
        else:
            output_buffer = StringIO()
            output_buffer.write(title_line + "\n")

            writer = csv.writer(output_buffer, lineterminator="\n")
            writer.writerows(updated_df.values.tolist())

            st.success("Updated file generated successfully.")

            st.download_button(
                label="Download Updated CSV",
                data=output_buffer.getvalue().encode("utf-8-sig"),
                file_name="updated_prices.csv",
                mime="text/csv"
            )
