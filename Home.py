import streamlit as st
from supabase import create_client

st.set_page_config(page_title="AHS Health Inventory", layout="wide")

def require_secrets():
    missing = []
    for k in ["SUPABASE_URL", "SUPABASE_ANON_KEY"]:
        if k not in st.secrets or not str(st.secrets.get(k, "")).strip():
            missing.append(k)
    if missing:
        st.error(
            "Missing Streamlit Secrets: "
            + ", ".join(missing)
            + "\n\nGo to Streamlit Cloud → App → Settings → Secrets and add them."
        )
        st.stop()

@st.cache_resource
def get_supabase():
    require_secrets()
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_ANON_KEY"])

sb = get_supabase()

# session state
if "session" not in st.session_state:
    st.session_state.session = None
if "profile" not in st.session_state:
    st.session_state.profile = None

st.title("AHS School Health Inventory")

with st.sidebar:
    st.subheader("Login")

    if st.session_state.session is None:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login", use_container_width=True):
            try:
                auth = sb.auth.sign_in_with_password({"email": email, "password": password})
                st.session_state.session = auth.session

                # fetch user profile
                user_id = auth.user.id
                prof = (
                    sb.table("user_profiles")
                    .select("*")
                    .eq("user_id", user_id)
                    .single()
                    .execute()
                    .data
                )
                st.session_state.profile = prof
                st.success("Logged in.")
                st.rerun()
            except Exception as e:
                st.error("Login failed. Check email/password and user profile setup.")
                st.caption(str(e))
    else:
        st.success(f"Signed in: {st.session_state.session.user.email}")
        if st.button("Logout", use_container_width=True):
            try:
                sb.auth.sign_out()
            except Exception:
                pass
            st.session_state.session = None
            st.session_state.profile = None
            st.rerun()

# main
if st.session_state.session is None:
    st.info("Please login from the left sidebar.")
    st.stop()

profile = st.session_state.profile
if not profile:
    st.error(
        "No profile found for this user.\n\n"
        "In Supabase, create a row in `user_profiles` with:\n"
        "- user_id (from Auth)\n"
        "- role (NURSE or OFFICER)\n"
        "- school_id (for nurses)\n"
        "- active = true"
    )
    st.stop()

if not profile.get("active", True):
    st.error("Your account is not active. Contact the administrator.")
    st.stop()

role = profile.get("role")
if role == "NURSE":
    st.success("Go to **Nurse Portal** from the left menu.")
elif role == "OFFICER":
    st.success("Go to **Officer Portal** from the left menu.")
else:
    st.error("Role not recognized. Use NURSE or OFFICER in `user_profiles.role`.")
