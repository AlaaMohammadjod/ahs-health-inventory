import streamlit as st
import pandas as pd
from fpdf import FPDF

from app.db import (
    get_supabase,
    fetch_items_with_stock,
    upsert_inventory_add,
    fetch_all_requests,
    fetch_request_lines,
    update_approved_quantities,
    mark_request_received,
    status_badge,
)

st.set_page_config(page_title="Officer Portal", layout="wide")

# --- auth ---
if not st.session_state.get("logged_in") or st.session_state.get("role") != "Officer":
    st.warning("Please login from Home as Officer.")
    st.stop()

sb = get_supabase()
if sb is None:
    st.error("Supabase is not ready. Check Home page and secrets.")
    st.stop()

officer_name = st.session_state.get("full_name", "").strip()

st.title("Officer Portal")
st.caption(f"Officer: **{officer_name}**")

tab1, tab2, tab3 = st.tabs(["🧾 Requests Review", "📥 Receive Stock", "📊 Inventory Overview"])


def build_pdf_bytes(request_row: dict, lines_df: pd.DataFrame) -> bytes:
    pdf = FPDF(format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AHS School Health Inventory - Issue Request", ln=True)

    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, f"Request ID: {request_row.get('id','')}", ln=True)
    pdf.cell(0, 8, f"School: {request_row.get('school_name','')}", ln=True)
    pdf.cell(0, 8, f"Nurse: {request_row.get('nurse_name','')}", ln=True)
    pdf.cell(0, 8, f"Status: {request_row.get('status','')}", ln=True)
    pdf.ln(6)

    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Approved Items:", ln=True)
    pdf.set_font("Helvetica", "", 10)

    for _, r in lines_df.iterrows():
        appr = int(r["approved_qty"]) if pd.notna(r["approved_qty"]) else 0
        req = int(r["requested_qty"])
        unit = r.get("unit", "") or ""
        line = f"- {r['item_name']} | Approved: {appr} {unit} (Requested: {req})"
        pdf.multi_cell(0, 6, line)

    pdf.ln(8)
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(0, 8, "Officer Signature: ____________________", ln=True)
    pdf.cell(0, 8, "Nurse Received (Name & Signature): ____________________", ln=True)

    return pdf.output(dest="S").encode("latin-1")


with tab1:
    st.subheader("Requests Review")

    status_filter = st.selectbox(
        "Filter by status",
        ["All", "Pending Approval", "Approved - Not Received", "Approved & Received"],
        index=0,
    )
    status_val = None if status_filter == "All" else status_filter

    reqs = fetch_all_requests(sb, status=status_val)
    if not reqs:
        st.info("No requests found.")
    else:
        df = pd.DataFrame(reqs)
        df["Status Badge"] = df["status"].apply(status_badge)
        df["Created"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            df[["id", "school_name", "nurse_name", "Status Badge", "Created"]],
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        selected_id = st.number_input("Open Request ID", min_value=1, step=1, value=int(df["id"].iloc[0]))
        # Find selected request row
        req_row = next((r for r in reqs if int(r["id"]) == int(selected_id)), None)
        if not req_row:
            st.warning("Request ID not found in current list.")
        else:
            st.markdown(f"### Request #{req_row['id']}")
            st.write(f"**School:** {req_row['school_name']}")
            st.write(f"**Nurse:** {req_row['nurse_name']}")
            st.write(f"**Status:** {status_badge(req_row['status'])}")

            lines = fetch_request_lines(sb, int(selected_id))
            if not lines:
                st.warning("No request lines found.")
            else:
                lines_df = pd.DataFrame(lines)

                st.markdown("#### Requested Items")
                st.dataframe(
                    lines_df[["item_name", "unit", "requested_qty", "approved_qty"]],
                    use_container_width=True,
                    hide_index=True,
                )

                st.divider()
                st.markdown("#### Approve / Amend Quantities")

                approved_map = {}
                for _, r in lines_df.iterrows():
                    line_id = int(r["line_id"])
                    max_qty = int(r["requested_qty"])  # officer can still reduce; if you want allow increase, change max
                    default_val = int(r["approved_qty"]) if pd.notna(r["approved_qty"]) else int(r["requested_qty"])
                    new_val = st.number_input(
                        f"{r['item_name']} (Requested: {int(r['requested_qty'])})",
                        min_value=0,
                        max_value=max_qty,
                        value=default_val,
                        step=1,
                        key=f"appr_{line_id}",
                    )
                    approved_map[line_id] = int(new_val)

                c1, c2, c3 = st.columns(3)

                with c1:
                    if st.button("Approve Request", type="primary", use_container_width=True):
                        ok = update_approved_quantities(sb, int(selected_id), approved_map)
                        if ok:
                            st.success("✅ Approved successfully (Approved - Not Received).")
                        else:
                            st.error("Approval failed. Check DB tables.")

                with c2:
                    if st.button("Mark as Received (Deduct Stock)", use_container_width=True):
                        ok = mark_request_received(sb, int(selected_id))
                        if ok:
                            st.success("✅ Marked as received and stock deducted.")
                        else:
                            st.error("Failed. Make sure approved quantities exist and inventory table is ready.")

                with c3:
                    # PDF download available once approved (even if not received)
                    if req_row["status"] in ["Approved - Not Received", "Approved & Received"]:
                        pdf_bytes = build_pdf_bytes(req_row, lines_df)
                        st.download_button(
                            "Download PDF",
                            data=pdf_bytes,
                            file_name=f"request_{req_row['id']}.pdf",
                            mime="application/pdf",
                            use_container_width=True,
                        )
                    else:
                        st.info("PDF is available after approval.")


with tab2:
    st.subheader("Receive Stock from Main Store (Add to Inventory)")

    category = st.selectbox("Category", ["Medicine", "Consumables", "Stationery"], index=0, key="recv_cat")
    items = fetch_items_with_stock(sb, category=category)

    if not items:
        st.info("No items found. Add items to the items table first.")
    else:
        df = pd.DataFrame(items)
        item_map = {f"{r['name']} (Current: {int(r['qty'])} {r['unit']})": int(r["id"]) for _, r in df.iterrows()}

        item_label = st.selectbox("Select item", list(item_map.keys()))
        add_qty = st.number_input("Quantity received", min_value=1, step=1, value=1)

        if st.button("Add to Inventory", type="primary", use_container_width=True):
            ok = upsert_inventory_add(sb, item_map[item_label], int(add_qty))
            if ok:
                st.success("✅ Inventory updated.")
            else:
                st.error("Update failed. Check DB tables / permissions.")


with tab3:
    st.subheader("Inventory Overview (All Categories)")

    all_rows = []
    for cat in ["Medicine", "Consumables", "Stationery"]:
        all_rows.extend(fetch_items_with_stock(sb, category=cat))

    if not all_rows:
        st.info("No inventory data available yet.")
    else:
        df = pd.DataFrame(all_rows)
        df["Stock Status"] = df["qty"].apply(lambda x: "Out of stock" if int(x) <= 0 else ("🔴 < 50" if int(x) < 50 else ("🟠 50–200" if int(x) <= 200 else "🟢 > 200")))
        df = df.sort_values(["category", "name"])

        st.dataframe(
            df[["category", "name", "unit", "qty", "Stock Status"]],
            use_container_width=True,
            hide_index=True,
        )

        st.caption("Color thresholds: < 50 red, 50–200 orange, > 200 green. (0 shows Out of stock.)")
