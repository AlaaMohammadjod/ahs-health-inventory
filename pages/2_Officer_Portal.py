import io
import streamlit as st
import pandas as pd
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.db import get_supabase, fetch_stock, fetch_requests, fetch_request_lines
from app.ui import format_stock_table
from app.constants import STATUS_LABELS

st.set_page_config(page_title="Officer Portal", layout="wide")
sb = get_supabase()

if "session" not in st.session_state or st.session_state.session is None:
    st.warning("Please login from Home.")
    st.stop()

profile = st.session_state.profile
if profile["role"] != "OFFICER":
    st.error("Access denied.")
    st.stop()

st.title("Officer Portal")

st.subheader("Inventory (Color-coded)")
stock = fetch_stock(sb).data
df = format_stock_table(stock)
st.dataframe(df, use_container_width=True, hide_index=True)

st.divider()
st.subheader("Requests")

reqs = fetch_requests(sb).data
if not reqs:
    st.info("No requests yet.")
    st.stop()

status_filter = st.selectbox("Filter", ["ALL","PENDING_APPROVAL","APPROVED_NOT_RECEIVED","APPROVED_RECEIVED","REJECTED"])
filtered = reqs if status_filter == "ALL" else [r for r in reqs if r["status"] == status_filter]

def make_pdf(request_id: int, status: str, lines_df: pd.DataFrame) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 50

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, f"AHS School Health - Approved Request #{request_id}")
    y -= 25

    c.setFont("Helvetica", 11)
    c.drawString(40, y, f"Status: {status}")
    y -= 25

    c.setFont("Helvetica-Bold", 11)
    c.drawString(40, y, "Items:")
    y -= 18

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
    y -= 20
    c.drawString(40, y, "Received by Nurse: ____________________")
    c.showPage()
    c.save()

    return buf.getvalue()

for r in filtered[:50]:
    label = STATUS_LABELS.get(r["status"], r["status"])
    with st.expander(f'Request #{r["request_id"]} — {label} — {r["created_at"]}'):
        lines = fetch_request_lines(sb, r["request_id"]).data
        rows = []
        for ln in lines:
            rows.append({
                "line_id": ln["line_id"],
                "item": ln["items"]["item_name"],
                "unit": ln["items"]["unit"],
                "requested_qty": ln["requested_qty"],
                "approved_qty": ln.get("approved_qty", ln["requested_qty"])
            })

        df_lines = pd.DataFrame(rows)
        edited = st.data_editor(
            df_lines,
            use_container_width=True,
            hide_index=True,
            disabled=["line_id","item","unit","requested_qty"]
        )

        c1, c2, c3 = st.columns(3)

        if c1.button("Save approved qty", key=f"save_{r['request_id']}", use_container_width=True):
            for _, row in edited.iterrows():
                sb.table("request_lines").update({"approved_qty": int(row["approved_qty"])}).eq("line_id", int(row["line_id"])).execute()
            st.success("Saved.")
            st.rerun()

        if c2.button("Approve", key=f"approve_{r['request_id']}", type="primary", use_container_width=True, disabled=(r["status"] != "PENDING_APPROVAL")):
            for _, row in edited.iterrows():
                sb.table("request_lines").update({"approved_qty": int(row["approved_qty"])}).eq("line_id", int(row["line_id"])).execute()
            sb.table("requests").update({
                "status": "APPROVED_NOT_RECEIVED",
                "reviewed_by": profile["user_id"],
                "reviewed_at": "now()"
            }).eq("request_id", r["request_id"]).execute()
            st.success("Approved.")
            st.rerun()

        if r["status"] in ("APPROVED_NOT_RECEIVED","APPROVED_RECEIVED"):
            pdf = make_pdf(r["request_id"], r["status"], edited)
            c3.download_button(
                "Download PDF",
                data=pdf,
                file_name=f"Approved_Request_{r['request_id']}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
