import streamlit as st
import pandas as pd
from app.db import get_supabase, fetch_items_with_stock, create_request, fetch_requests_for_school, stock_badge, status_badge

st.set_page_config(page_title="Nurse Portal", layout="wide")

# --- auth ---
if not st.session_state.get("logged_in") or st.session_state.get("role") != "Nurse":
    st.warning("Please login from Home as Nurse.")
    st.stop()

sb = get_supabase()
if sb is None:
    st.error("Supabase is not ready. Check Home page and secrets.")
    st.stop()

school_name = st.session_state.get("school_name", "").strip()
nurse_name = st.session_state.get("full_name", "").strip()

st.title("Nurse Portal")
st.caption(f"School: **{school_name}**  |  Nurse: **{nurse_name}**")

tab1, tab2 = st.tabs(["📦 Available Stock", "🧾 My Requests History"])

with tab1:
    st.subheader("Available Items (from Officer Inventory)")
    category = st.selectbox("Category", ["Medicine", "Consumables", "Stationery"], index=0)

    items = fetch_items_with_stock(sb, category=category)
    if not items:
        st.info("No items found. (Check database tables and items list.)")
    else:
        df = pd.DataFrame(items)
        df["Stock Status"] = df["qty"].apply(stock_badge)

        # Show only available items (qty > 0) for selection, but display all with out-of-stock label.
        st.markdown("**Stock Overview**")
        st.dataframe(
            df[["name", "unit", "qty", "Stock Status"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        st.subheader("Create a New Request")

        available_df = df[df["qty"] > 0].copy()
        if available_df.empty:
            st.warning("All items in this category are out of stock. You cannot submit a request now.")
        else:
            item_options = {f"{r['name']} (Available: {int(r['qty'])} {r['unit']})": int(r["id"]) for _, r in available_df.iterrows()}
            selected = st.multiselect("Select items to request", list(item_options.keys()))

            lines = []
            for label in selected:
                item_id = item_options[label]
                max_qty = int(available_df[available_df["id"] == item_id]["qty"].iloc[0])
                req_qty = st.number_input(f"Requested quantity for: {label}", min_value=1, max_value=max_qty, value=min(1, max_qty), step=1)
                lines.append({"item_id": item_id, "requested_qty": int(req_qty)})

            if st.button("Submit Request", type="primary", use_container_width=True, disabled=(len(lines) == 0)):
                req_id = create_request(sb, school_name=school_name, nurse_name=nurse_name, lines=lines)
                if req_id:
                    st.success(f"✅ Request submitted successfully. Request ID: {req_id}")
                else:
                    st.error("Request failed. Please check database tables and try again.")

with tab2:
    st.subheader("My Requests History")
    reqs = fetch_requests_for_school(sb, school_name)
    if not reqs:
        st.info("No requests yet.")
    else:
        df = pd.DataFrame(reqs)
        df["Status"] = df["status"].apply(status_badge)
        df["Created"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        df["Updated"] = pd.to_datetime(df["updated_at"]).dt.strftime("%Y-%m-%d %H:%M")

        st.dataframe(
            df[["id", "nurse_name", "Status", "Created", "Updated"]],
            use_container_width=True,
            hide_index=True,
        )

        st.caption("Status colors: 🟡 Pending | 🟠 Approved not received | 🟢 Received")
