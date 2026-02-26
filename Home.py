import streamlit as st
from app.db import get_supabase, healthcheck_tables

st.set_page_config(page_title="AHS School Health Inventory", layout="wide")

st.markdown(
    """
    <style>
      .big-title { font-size: 64px; font-weight: 800; margin-bottom: 0.25rem; }
      .sub { color:#6b7280; margin-top:-10px; }
      .card { background:#f8fafc; border:1px solid #e5e7eb; border-radius:14px; padding:18px; }
      .pill { display:inline-block; padding:6px 10px; border-radius:999px; font-size:12px; border:1px solid #e5e7eb; background:#ffffff; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="big-title">AHS School Health Inventory</div>', unsafe_allow_html=True)
st.markdown('<div class="sub">Material Management Officer & School Nurses Portal</div>', unsafe_allow_html=True)
st.write("")

# --- Supabase connectivity (safe) ---
sb = get_supabase()
if sb is None:
    st.error(
        "Supabase is not ready.\n\n"
        "Please add secrets in Streamlit Cloud → App → Settings → Secrets:\n\n"
        'SUPABASE_URL = "https://YOURPROJECTREF.supabase.co"\n'
        'SUPABASE_ANON_KEY = "YOUR_ANON_KEY"\n'
    )
    st.stop()

st.success("✅ Supabase connection is ready.")

# --- Check tables exist (non-fatal; shows guidance) ---
missing = healthcheck_tables(sb)
if missing:
    st.warning(
        "Your database tables are not ready yet. The app can load, but pages will show limited data.\n\n"
        f"Missing tables: {', '.join(missing)}\n\n"
        "Open `app/db.py` and copy the SQL section into Supabase → SQL Editor to create them."
    )

st.write("")

# --- Login (simple, role-based) ---
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "role" not in st.session_state:
    st.session_state.role = None
if "school_name" not in st.session_state:
    st.session_state.school_name = ""
if "full_name" not in st.session_state:
    st.session_state.full_name = ""

left, right = st.columns([1.2, 1])

with left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Login")
    role = st.selectbox("Role", ["Nurse", "Officer"], index=0)
    full_name = st.text_input("Full name (for records)", value=st.session_state.full_name)
    school_name = ""
    if role == "Nurse":
        school_name = st.text_input("School name", value=st.session_state.school_name)

    pin = st.text_input("PIN (temporary login)", type="password", help="This is a temporary login. We can upgrade to proper auth later.")
    c1, c2 = st.columns(2)

    with c1:
        if st.button("Login", use_container_width=True):
            if not full_name.strip():
                st.error("Please enter your full name.")
            elif role == "Nurse" and not school_name.strip():
                st.error("Please enter your school name.")
            elif not pin.strip():
                st.error("Please enter a PIN.")
            else:
                st.session_state.logged_in = True
                st.session_state.role = role
                st.session_state.full_name = full_name.strip()
                st.session_state.school_name = school_name.strip()
                st.success("Logged in successfully. Use the left menu to open your portal.")

    with c2:
        if st.button("Logout", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.role = None
            st.session_state.school_name = ""
            st.session_state.full_name = ""
            st.success("Logged out.")

    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("Quick Guide")
    st.markdown(
        """
        **Nurse Portal**
        - View available stock by category
        - Out-of-stock items show clearly
        - Submit requests and track status

        **Officer Portal**
        - Review requests
        - Amend quantities
        - Approve / Mark Received
        - Download PDF for approved requests
        - Receive stock from main store
        """
    )
    st.markdown('<span class="pill">Stock thresholds: < 50 red, 50–200 orange, > 200 green</span>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
