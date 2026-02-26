import streamlit as st

st.set_page_config(page_title="AHS Health Inventory", layout="wide")
st.title("AHS School Health Inventory")

# --- SAFE IMPORT: don't crash if supabase isn't installed yet ---
try:
    from supabase import create_client
except Exception:
    create_client = None

# --- check secrets ---
supabase_url = st.secrets.get("SUPABASE_URL", "").strip() if hasattr(st, "secrets") else ""
supabase_key = st.secrets.get("SUPABASE_ANON_KEY", "").strip() if hasattr(st, "secrets") else ""

if create_client is None:
    st.error(
        "Supabase library is not installed.\n\n"
        "Fix: add this to requirements.txt:\n"
        "supabase"
    )
    st.stop()

if not supabase_url or not supabase_key:
    st.warning(
        "Supabase is not configured yet.\n\n"
        "Add secrets in Streamlit Cloud → App → Settings → Secrets:\n\n"
        'SUPABASE_URL = "https://xxxxx.supabase.co"\n'
        'SUPABASE_ANON_KEY = "your_anon_key"\n'
    )
    st.stop()

# --- if everything is ready, create client ---
@st.cache_resource
def get_supabase():
    return create_client(supabase_url, supabase_key)

sb = get_supabase()
st.success("✅ Supabase connection is ready.")
