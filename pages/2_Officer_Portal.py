import io
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.db import (
    get_supabase,
    fetch_stock,
    fetch_all_requests,
    fetch_request_lines,
    update_line_approved_qty,
    set_request_status,
)
from app.ui import format_stock_table
from app.constants import STATUS_LABELS

st.set_page_config(page_title="Officer Portal", layout="wide")
sb = get_supabase()

if "session" not in st.session_state or st.session_state.session is None:
    st.warning("Please login from Home.")
    st.stop()

profile = st.session_state.get("profile")
if not profile or profile.get("role") != "OFFICER":
    st.error("Access denied. This page is for OFFICER users only.")
    st.stop()

st.title("Officer Portal")

# Inventory
st.subheader("Inventory (Color-coded)")
stock = fetch_stock(sb)
df = format_stock_table(stock)
if df.empty:
    st.warning("No inventory view found yet (`v_stock_on_hand`). Create your DB schema first.")
else:
    st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Requests Review")

reqs = fetch_all_requests(sb)
if not reqs:
    st.info("No requests yet.")
    st.stop()

status_filter = st.selectbox(
    "Filter",
    ["ALL", "PENDING_APPROVAL", "APPROVED_NOT_RECEIVED", "APPROVED_RECEIVED", "REJECTED"],
)

filtered = reqs if status_filter == "ALL" else [r for r in reqs if r.get("status") == status_filter]

def make_pdf(request_id: int, status: str, lines_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"AHS School Health - Request #{request_id}")
    y -= 22
    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Status: {status}")
    y -= 22

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Items:")
    y -= 16

    c.setFont("Helvetica", 10)
    for _, row in lines_df.iterrows():
        txt = f"- {row['item']} | Approved: {int(row['approved_qty'])} {row['unit']} (Requested: {int(row['requested_qty'])})"
        c.drawString(50, y, txt[:120])
        y -= 14
        if y < 80:
            c.showPage()
            y = h - 50
            c.setFont("Helvetica", 10)

    y -= 10
    c.setFont("Helvetica", 11)
    c.drawString(40, y, "Officer Signature: ____________________")
    y -= 18
    c.drawString(40, y, "Received by Nurse: ____________________")
    c.showPage()
    c.save()
    return buf.getvalue()

for r in filtered[:60]:
    label = STATUS_LABELS.get(r.get("status", ""), r.get("status", "UNKNOWN"))
    with st.expander(f'Request #{r["request_id"]} — {label} — {r.get("created_at","")}'):
        lines = fetch_request_lines(sb, r["request_id"])
        if not lines:
            st.warning("No request lines found.")
            continue

        rows = []
        for ln in lines:
            itm = ln.get("items") or {}
            rows.append(
                {
                    "line_id": ln["line_id"],
                    "item": itm.get("item_name", str(ln.get("item_id"))),
                    "unit": itm.get("unit", ""),
                    "requested_qty": ln.get("requested_qty", 0),
                    "approved_qty": ln.get("approved_qty", ln.get("requested_qty", 0)),
                }
            )

        df_lines = pd.DataFrame(rows)
        edited = st.data_editor(
            df_lines,
            use_container_width=True,
            hide_index=True,
            disabled=["line_id", "item", "unit", "requested_qty"],
        )

        c1, c2, c3 = st.columns(3)

        if c1.button("Save approved qty", key=f"save_{r['request_id']}", use_container_width=True):
            try:
                for _, row in edited.iterrows():
                    update_line_approved_qty(sb, int(row["line_id"]), int(row["approved_qty"]))
                st.success("Saved.")
                st.rerun()
            except Exception as e:
                st.error("Save failed (check DB + RLS).")
                st.caption(str(e))

        approve_disabled = (r.get("status") != "PENDING_APPROVAL")
        if c2.button("Approve", key=f"approve_{r['request_id']}", type="primary", use_container_width=True, disabled=approve_disabled):
            try:
                for _, row in edited.iterrows():
                    update_line_approved_qty(sb, int(row["line_id"]), int(row["approved_qty"]))
                set_request_status(sb, r["request_id"], "APPROVED_NOT_RECEIVED", profile["user_id"])
                st.success("Approved.")
                st.rerun()
            except Exception as e:
                st.error("Approve failed (check DB + RLS).")
                st.caption(str(e))

        if r.get("status") in ("APPROVED_NOT_RECEIVED", "APPROVED_RECEIVED"):
            pdf = make_pdf(r["request_id"], r["status"], edited)
            c3.download_button(
                "Download PDF",
                data=pdf,
                file_name=f"Request_{r['request_id']}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
