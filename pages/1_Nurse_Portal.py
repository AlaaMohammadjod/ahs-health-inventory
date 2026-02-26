import streamlit as st
from app.db import get_supabase, fetch_stock, create_request, add_request_lines, fetch_requests_for_nurse, fetch_request_lines
from app.ui import format_stock_table
from app.constants import STATUS_LABELS

st.set_page_config(page_title="Nurse Portal", layout="wide")
sb = get_supabase()

if "session" not in st.session_state or st.session_state.session is None:
    st.warning("Please login from Home.")
    st.stop()

profile = st.session_state.get("profile")
if not profile or profile.get("role") != "NURSE":
    st.error("Access denied. This page is for NURSE users only.")
    st.stop()

school_id = profile.get("school_id")
if school_id is None:
    st.error("Your profile is missing school_id. Please set school_id in user_profiles.")
    st.stop()

st.title("Nurse Portal")

stock = fetch_stock(sb)
df = format_stock_table(stock)

st.subheader("Available Items (Central Store)")
if df.empty:
    st.warning(
        "No stock data found.\n\n"
        "Make sure your Supabase database has the view `v_stock_on_hand` "
        "and the `items` + `inventory_transactions` tables."
    )
else:
    for cat in ["MEDICINE", "CONSUMABLES", "STATIONERY"]:
        with st.expander(cat.title(), expanded=True):
            st.dataframe(df[df["Category"] == cat], use_container_width=True, hide_index=True)

st.divider()
st.subheader("Create a Request")

requestable = [r for r in stock if int(r.get("on_hand", 0)) > 0]
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
        try:
            req_id = create_request(sb, school_id=school_id, nurse_user_id=profile["user_id"], notes=notes)
            add_request_lines(sb, req_id, lines)
            st.success(f"Request submitted. Request ID: {req_id}")
            st.rerun()
        except Exception as e:
            st.error("Failed to submit request. Check database tables and RLS policies.")
            st.caption(str(e))

st.divider()
st.subheader("My Requests History")

reqs = fetch_requests_for_nurse(sb, profile["user_id"])
if not reqs:
    st.info("No requests yet.")
else:
    for r in reqs[:50]:
        label = STATUS_LABELS.get(r.get("status", ""), r.get("status", "UNKNOWN"))
        with st.expander(f'Request #{r["request_id"]} — {label} — {r.get("created_at","")}'):
            lines = fetch_request_lines(sb, r["request_id"])
            if not lines:
                st.write("No lines found.")
            else:
                for ln in lines:
                    item = ln["items"]["item_name"] if ln.get("items") else ln.get("item_id")
                    rq = ln.get("requested_qty")
                    ap = ln.get("approved_qty")
                    st.write(f"- **{item}** | Requested: {rq} | Approved: {ap if ap is not None else '—'}")
