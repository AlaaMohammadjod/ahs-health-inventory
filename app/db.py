import streamlit as st
from supabase import create_client

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

def fetch_stock(sb):
    return sb.from_("v_stock_on_hand").select("*").order("category").order("item_name").execute()

def create_request(sb, school_id: int, nurse_user_id: str, notes: str = ""):
    payload = {"school_id": school_id, "nurse_user_id": nurse_user_id, "notes": notes}
    return sb.table("requests").insert(payload).execute()

def add_request_lines(sb, request_id: int, lines: list[dict]):
    for ln in lines:
        ln["request_id"] = request_id
    return sb.table("request_lines").insert(lines).execute()

def fetch_requests(sb):
    return sb.table("requests").select("*").order("created_at", desc=True).execute()

def fetch_request_lines(sb, request_id: int):
    return (
        sb.table("request_lines")
        .select("*, items(item_name,category,unit)")
        .eq("request_id", request_id)
        .execute()
    )
