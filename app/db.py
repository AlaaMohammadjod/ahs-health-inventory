import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase():
    url = st.secrets.get("SUPABASE_URL", "").strip()
    key = st.secrets.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in Streamlit secrets.")
    return create_client(url, key)

def safe_execute(fn, default=None):
    try:
        return fn()
    except Exception:
        return default

def fetch_stock(sb):
    """
    Expected source:
      - view `v_stock_on_hand` with columns: item_id, category, item_name, unit, on_hand
    If not available yet, returns empty list.
    """
    res = safe_execute(lambda: sb.from_("v_stock_on_hand").select("*").execute(), default=None)
    if not res or not getattr(res, "data", None):
        return []
    return res.data

def create_request(sb, school_id: int, nurse_user_id: str, notes: str = ""):
    res = sb.table("requests").insert(
        {"school_id": school_id, "nurse_user_id": nurse_user_id, "notes": notes}
    ).execute()
    return res.data[0]["request_id"]

def add_request_lines(sb, request_id: int, lines: list[dict]):
    payload = []
    for ln in lines:
        payload.append(
            {
                "request_id": request_id,
                "item_id": ln["item_id"],
                "requested_qty": int(ln["requested_qty"]),
            }
        )
    sb.table("request_lines").insert(payload).execute()

def fetch_requests_for_nurse(sb, nurse_user_id: str):
    res = safe_execute(
        lambda: sb.table("requests")
        .select("*")
        .eq("nurse_user_id", nurse_user_id)
        .order("created_at", desc=True)
        .execute(),
        default=None,
    )
    return res.data if res and getattr(res, "data", None) else []

def fetch_all_requests(sb):
    res = safe_execute(
        lambda: sb.table("requests").select("*").order("created_at", desc=True).execute(),
        default=None,
    )
    return res.data if res and getattr(res, "data", None) else []

def fetch_request_lines(sb, request_id: int):
    res = safe_execute(
        lambda: sb.table("request_lines")
        .select("line_id, item_id, requested_qty, approved_qty, items(item_name,category,unit)")
        .eq("request_id", request_id)
        .execute(),
        default=None,
    )
    return res.data if res and getattr(res, "data", None) else []

def update_line_approved_qty(sb, line_id: int, approved_qty: int):
    sb.table("request_lines").update({"approved_qty": int(approved_qty)}).eq("line_id", int(line_id)).execute()

def set_request_status(sb, request_id: int, status: str, reviewer_user_id: str):
    sb.table("requests").update(
        {"status": status, "reviewed_by": reviewer_user_id}
    ).eq("request_id", int(request_id)).execute()
