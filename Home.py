import streamlit as st
from supabase import create_client

st.set_page_config(page_title="AHS School Health Inventory", layout="wide")

@st.cache_resource
def get_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_ANON_KEY"]
    return create_client(url, key)

sb = get_supabase()

# session containers
if "session" not in st.session_state:
    st.session_state.session = None
if "profile" not in st.session_state:
    st.session_state.profile = None

st.title("AHS School Health Inventory")

# Sidebar login
with st.sidebar:
    st.subheader("Sign in")
    if st.session_state.session is None:
        email = st.text_input("Email", placeholder="yourname@school.ae")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            try:
                auth = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.session = auth.session

                # fetch role profile
                user_id = auth.user.id
                prof = sb.table("user_profiles").select("*").eq("user_id", user_id).single().execute().data
                st.session_state.profile = prof

                st.success("Logged in.")
                st.rerun()
            except Exception:
                st.error("Login failed. Check email/password.")
    else:
        st.write(f"Signed in as: **{st.session_state.session.user.email}**")
        if st.button("Logout", use_container_width=True):
            sb.auth.sign_out()
            st.session_state.session = None
            st.session_state.profile = None
            st.rerun()

# Main content
if st.session_state.session is None:
    st.info("Please sign in from the left panel.")
    st.stop()

profile = st.session_state.profile
if not profile or not profile.get("active", True):
    st.error("Your account is not active. Contact the officer/admin.")
    st.stop()

role = profile["role"]
if role == "NURSE":
    st.success("Open **Nurse Portal** from the left pages menu.")
elif role == "OFFICER":
    st.success("Open **Officer Portal** from the left pages menu.")
else:
    st.error("Role is not configured correctly.")
