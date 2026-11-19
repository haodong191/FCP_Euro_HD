import csv
from pathlib import Path

import pandas as pd
import streamlit as st


# -----------------------------
# Page config
# -----------------------------
st.set_page_config(page_title="Rekluse PIES CSV Editor", layout="wide")
st.title("Rekluse PIES CSV Editor")
st.caption("View, search, edit, add, and save changes directly to Rekluse_PIES_CSV.")


# -----------------------------
# File path
# -----------------------------
CSV_PATH = Path("Rekluse_PIES_CSV.csv")
if not CSV_PATH.exists():
    alt_path = Path("Rekluse_PIES_CSV")
    if alt_path.exists():
        CSV_PATH = alt_path


# -----------------------------
# Helpers
# -----------------------------
def make_unique_display_names(columns: list[str]) -> list[str]:
    """Create unique display names while preserving original headers for save."""
    counts = {}
    unique_names = []
    for col in columns:
        counts[col] = counts.get(col, 0) + 1
        if counts[col] == 1:
            unique_names.append(col)
        else:
            unique_names.append(f"{col} [{counts[col]}]")
    return unique_names


@st.cache_data(show_spinner=False)
def load_csv(path_str: str):
    path = Path(path_str)

    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return [], [], pd.DataFrame()

    original_headers = rows[0]
    data_rows = rows[1:]
    unique_headers = make_unique_display_names(original_headers)

    max_len = len(original_headers)
    padded_rows = []
    for row in data_rows:
        if len(row) < max_len:
            row = row + [""] * (max_len - len(row))
        elif len(row) > max_len:
            row = row[:max_len]
        padded_rows.append(row)

    df = pd.DataFrame(padded_rows, columns=unique_headers)
    return original_headers, unique_headers, df


def save_csv(path_str: str, original_headers: list[str], unique_headers: list[str], edited_df: pd.DataFrame):
    path = Path(path_str)
    save_df = edited_df.copy()
    save_df = save_df.reindex(columns=unique_headers)
    save_df.columns = original_headers

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(original_headers)
        writer.writerows(save_df.fillna("").astype(str).values.tolist())

    load_csv.clear()


# -----------------------------
# Load data
# -----------------------------
if not CSV_PATH.exists():
    st.error(
        "Could not find 'Rekluse_PIES_CSV.csv' or 'Rekluse_PIES_CSV' in this folder. "
        "Place the CSV in the same folder as this app."
    )
    st.stop()

original_headers, unique_headers, df = load_csv(str(CSV_PATH))

if df.empty and len(unique_headers) == 0:
    st.warning("The CSV appears to be empty.")
    st.stop()


# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Search & Filter")

part_number_col = next((c for c in unique_headers if c.startswith("PartNumber")), None)
brand_col = next((c for c in unique_headers if c.startswith("BrandLabel")), None)

search_text = st.sidebar.text_input("Search any value")
search_part_number = st.sidebar.text_input("Search Part Number") if part_number_col else ""

visible_columns = st.sidebar.multiselect(
    "Columns to show",
    options=unique_headers,
    default=unique_headers[:12] if len(unique_headers) > 12 else unique_headers,
)

filtered_df = df.copy()

if search_text:
    mask = filtered_df.apply(
        lambda row: row.astype(str).str.contains(search_text, case=False, na=False).any(),
        axis=1,
    )
    filtered_df = filtered_df[mask]

if search_part_number and part_number_col:
    filtered_df = filtered_df[
        filtered_df[part_number_col].astype(str).str.contains(search_part_number, case=False, na=False)
    ]

if brand_col:
    brand_options = sorted([b for b in df[brand_col].dropna().astype(str).unique().tolist() if b.strip()])
    selected_brands = st.sidebar.multiselect("Filter BrandLabel", brand_options)
    if selected_brands:
        filtered_df = filtered_df[filtered_df[brand_col].astype(str).isin(selected_brands)]

st.subheader("CSV Data")
st.write(f"Rows shown: {len(filtered_df):,} / {len(df):,}")

if not visible_columns:
    st.info("Select at least one column to display.")
    st.stop()

edited_view = st.data_editor(
    filtered_df[visible_columns],
    use_container_width=True,
    num_rows="dynamic",
    hide_index=False,
    key="pies_editor",
)


# -----------------------------
# Save logic
# -----------------------------
col1, col2 = st.columns([1, 5])

with col1:
    if st.button("Save Changes", type="primary"):
        updated_df = df.copy()

        # Update rows that are currently shown/edited
        for idx in edited_view.index:
            for col in visible_columns:
                updated_df.at[idx, col] = edited_view.at[idx, col]

        # Add newly inserted rows from editor
        new_rows = edited_view[~edited_view.index.isin(df.index)]
        if not new_rows.empty:
            expanded_new_rows = pd.DataFrame(columns=unique_headers)
            for _, row in new_rows.iterrows():
                new_row = {col: "" for col in unique_headers}
                for col in visible_columns:
                    new_row[col] = row.get(col, "")
                expanded_new_rows = pd.concat([expanded_new_rows, pd.DataFrame([new_row])], ignore_index=True)
            updated_df = pd.concat([updated_df, expanded_new_rows], ignore_index=True)

        save_csv(str(CSV_PATH), original_headers, unique_headers, updated_df)
        st.success(f"Changes saved directly to {CSV_PATH.name}")
        st.rerun()

with col2:
    st.caption("Edits are written back to the original CSV file when you click Save Changes.")


# -----------------------------
# Add row form
# -----------------------------
with st.expander("Add New Row"):
    with st.form("add_row_form"):
        new_row_data = {}
        add_cols = st.columns(3)

        for i, col in enumerate(unique_headers):
            with add_cols[i % 3]:
                new_row_data[col] = st.text_input(col, key=f"new_{i}")

        submitted = st.form_submit_button("Add Row")
        if submitted:
            new_df = pd.concat([df, pd.DataFrame([new_row_data])], ignore_index=True)
            save_csv(str(CSV_PATH), original_headers, unique_headers, new_df)
            st.success("New row added and saved.")
            st.rerun()


# -----------------------------
# Footer details
# -----------------------------
with st.expander("File Details"):
    st.write(f"File: {CSV_PATH.resolve()}")
    st.write(f"Columns found: {len(original_headers)}")
    st.write("Original CSV headers are preserved exactly during save, including duplicates.")
