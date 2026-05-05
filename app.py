import streamlit as st
import pandas as pd
import csv
from io import StringIO

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

    PRICE_COL = 8     # Column I
    STOCK_COL = 2     # Column C
    ORDER_COL = 20    # Column U

    required_cols = max(PRICE_COL, STOCK_COL, ORDER_COL) + 1

    if df.shape[1] < required_cols:
        st.error(f"File has only {df.shape[1]} columns. Expected at least {required_cols}.")
        st.stop()

    st.success(f"File loaded successfully. Rows: {len(df):,}")

    if skipped_rows:
        st.warning(f"{len(skipped_rows)} malformed rows were skipped.")

    invalid_values = ["", "None", "none", "NONE", "nan", "NaN", "NAN", "null", "NULL"]

    orders = df[[ORDER_COL, STOCK_COL, PRICE_COL]].copy()
    orders.columns = ["Order Number", "Stock Name", "Current Price"]

    orders["Order Number"] = orders["Order Number"].astype(str).str.strip()
    orders["Stock Name"] = orders["Stock Name"].astype(str).str.strip()
    orders["Current Price"] = orders["Current Price"].astype(str).str.strip()

    orders = orders[
        ~orders["Order Number"].isin(invalid_values)
        & ~orders["Stock Name"].isin(invalid_values)
    ]

    orders = orders.drop_duplicates(subset=["Order Number"])

    st.subheader("Enter New Prices")
    st.write(f"Valid unique orders found: **{len(orders):,}**")

    new_prices = {}

    for _, row in orders.iterrows():
        order_no = str(row["Order Number"]).strip()
        stock_name = str(row["Stock Name"]).strip()
        current_price = str(row["Current Price"]).strip()

        col1, col2, col3 = st.columns([2, 4, 2])

        with col1:
            st.write(f"**Order:** {order_no}")

        with col2:
            st.write(f"**Stock:** {stock_name}")

        with col3:
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
