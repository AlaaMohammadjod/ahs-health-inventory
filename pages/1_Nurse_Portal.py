import streamlit as st
from app.db import get_supabase, fetch_stock, create_request, add_request_lines, fetch_requests, fetch_request_lines
from app.ui import format_stock_table
from app.constants import STATUS_LABELS

st.set_page_config(page_title="Nurse Portal", layout="wide")
sb = get_supabase()

if "session" not in st.session_state or st.session_state.session is None:
    st.warning("Please login from Home.")
    st.stop()

profile = st.session_state.profile
if profile["role"] != "NURSE":
    st.error("Access denied.")
    st.stop()

school_id = profile["school_id"]

st.title("Nurse Portal")
st.caption("You can only see items available in the central store. Items with 0 show as Out of stock.")

stock = fetch_stock(sb).data
df = format_stock_table(stock)

st.subheader("Items by Category")
if df.empty:
    st.info("No items found yet.")
else:
    for cat in ["MEDICINE", "CONSUMABLES", "STATIONERY"]:
        with st.expander(cat.title(), expanded=True):
            st.dataframe(df[df["Category"] == cat], use_container_width=True, hide_index=True)

st.divider()
st.subheader("Create a Request")

requestable = [r for r in stock if int(r["on_hand"]) > 0]
if not requestable:
    st.info("All items are currently out of stock.")
else:
    options = {f'{r["item_name"]} ({r["on_hand"]} {r["unit"]} available)': r for r in requestable}
    selected = st.multiselect("Select items", list(options.keys()))

    lines = []
    for key in selected:
        item = options[key]
        max_qty = int(item["on_hand"])
        qty = st.number_input(
            f'Request quantity: {item["item_name"]} (max {max_qty})',
            min_value=1, max_value=max_qty, value=1, step=1
        )
        lines.append({"item_id": item["item_id"], "requested_qty": int(qty)})

    notes = st.text_area("Notes (optional)")
    if st.button("Submit request", type="primary", use_container_width=True, disabled=(len(lines) == 0)):
        req_res = create_request(sb, school_id=school_id, nurse_user_id=profile["user_id"], notes=notes)
        req_id = req_res.data[0]["request_id"]
        add_request_lines(sb, req_id, lines)
        st.success(f"Request submitted. Request ID: {req_id}")
        st.rerun()

st.divider()
st.subheader("My Requests History")

reqs = fetch_requests(sb).data
if not reqs:
    st.info("No requests yet.")
else:
    for r in reqs[:30]:
        label = STATUS_LABELS.get(r["status"], r["status"])
        with st.expander(f'Request #{r["request_id"]} — {label} — {r["created_at"]}'):
            lines = fetch_request_lines(sb, r["request_id"]).data
            for ln in lines:
                item = ln["items"]["item_name"]
                rq = ln["requested_qty"]
                ap = ln.get("approved_qty", None)
                st.write(f"- **{item}** | Requested: {rq} | Approved: {ap if ap is not None else '—'}")
