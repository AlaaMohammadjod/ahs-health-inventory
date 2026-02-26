import streamlit as st
from typing import List, Dict, Optional
from datetime import datetime

# ----------------------------
# REQUIRED SUPABASE TABLES SQL
# ----------------------------
"""
Run this in Supabase → SQL Editor:

create table if not exists items (
  id bigserial primary key,
  name text not null,
  category text not null check (category in ('Medicine','Consumables','Stationery')),
  unit text default '',
  active boolean default true
);

create table if not exists inventory (
  item_id bigint primary key references items(id) on delete cascade,
  qty integer not null default 0,
  updated_at timestamptz default now()
);

create table if not exists requests (
  id bigserial primary key,
  school_name text not null,
  nurse_name text not null,
  status text not null check (status in ('Pending Approval','Approved - Not Received','Approved & Received')) default 'Pending Approval',
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table if not exists request_lines (
  id bigserial primary key,
  request_id bigint references requests(id) on delete cascade,
  item_id bigint references items(id),
  requested_qty integer not null,
  approved_qty integer,
  created_at timestamptz default now()
);

-- Helpful index
create index if not exists idx_requests_school on requests(school_name);
create index if not exists idx_request_lines_req on request_lines(request_id);
"""

# ----------------------------
# SUPABASE CLIENT
# ----------------------------
@st.cache_resource
def get_supabase():
    """
    Returns a supabase client or None if secrets are missing.
    """
    try:
        from supabase import create_client
    except Exception:
        return None

    url = st.secrets.get("SUPABASE_URL", "").strip()
    key = st.secrets.get("SUPABASE_ANON_KEY", "").strip()
    if not url or not key:
        return None
    return create_client(url, key)


def healthcheck_tables(sb) -> List[str]:
    """
    Returns list of missing tables (best-effort check).
    """
    required = ["items", "inventory", "requests", "request_lines"]
    missing = []
    for t in required:
        try:
            sb.table(t).select("*").limit(1).execute()
        except Exception:
            missing.append(t)
    return missing


# ----------------------------
# DATA HELPERS
# ----------------------------
def fetch_items_with_stock(sb, category: Optional[str] = None) -> List[Dict]:
    """
    Returns items + qty. Only active items.
    """
    try:
        q = sb.table("items").select("id,name,category,unit,active").eq("active", True)
        if category:
            q = q.eq("category", category)
        items = q.order("name").execute().data or []
    except Exception:
        return []

    # Fetch inventory for all item ids in one go
    ids = [i["id"] for i in items]
    inv_map = {i: 0 for i in ids}

    if ids:
        try:
            inv = sb.table("inventory").select("item_id,qty").in_("item_id", ids).execute().data or []
            for row in inv:
                inv_map[row["item_id"]] = int(row.get("qty") or 0)
        except Exception:
            pass

    out = []
    for it in items:
        out.append(
            {
                "id": it["id"],
                "name": it["name"],
                "category": it["category"],
                "unit": it.get("unit", "") or "",
                "qty": int(inv_map.get(it["id"], 0)),
            }
        )
    return out


def upsert_inventory_add(sb, item_id: int, add_qty: int) -> bool:
    """
    Adds stock to inventory (creates row if missing).
    """
    add_qty = int(add_qty)
    if add_qty <= 0:
        return False

    try:
        current = sb.table("inventory").select("item_id,qty").eq("item_id", item_id).execute().data
        if current:
            new_qty = int(current[0]["qty"]) + add_qty
            sb.table("inventory").update({"qty": new_qty, "updated_at": datetime.utcnow().isoformat()}).eq("item_id", item_id).execute()
        else:
            sb.table("inventory").insert({"item_id": item_id, "qty": add_qty}).execute()
        return True
    except Exception:
        return False


def create_request(sb, school_name: str, nurse_name: str, lines: List[Dict]) -> Optional[int]:
    """
    lines: [{item_id:int, requested_qty:int}]
    """
    try:
        header = sb.table("requests").insert(
            {
                "school_name": school_name,
                "nurse_name": nurse_name,
                "status": "Pending Approval",
            }
        ).execute().data
        if not header:
            return None
        req_id = header[0]["id"]

        payload = []
        for ln in lines:
            payload.append(
                {
                    "request_id": req_id,
                    "item_id": int(ln["item_id"]),
                    "requested_qty": int(ln["requested_qty"]),
                    "approved_qty": None,
                }
            )
        if payload:
            sb.table("request_lines").insert(payload).execute()
        return req_id
    except Exception:
        return None


def fetch_requests_for_school(sb, school_name: str) -> List[Dict]:
    try:
        data = (
            sb.table("requests")
            .select("id,school_name,nurse_name,status,created_at,updated_at")
            .eq("school_name", school_name)
            .order("created_at", desc=True)
            .execute()
            .data
            or []
        )
        return data
    except Exception:
        return []


def fetch_all_requests(sb, status: Optional[str] = None) -> List[Dict]:
    try:
        q = sb.table("requests").select("id,school_name,nurse_name,status,created_at,updated_at").order("created_at", desc=True)
        if status:
            q = q.eq("status", status)
        return q.execute().data or []
    except Exception:
        return []


def fetch_request_lines(sb, request_id: int) -> List[Dict]:
    try:
        # Join: request_lines + items
        data = (
            sb.table("request_lines")
            .select("id,request_id,item_id,requested_qty,approved_qty,items(name,unit,category)")
            .eq("request_id", request_id)
            .execute()
            .data
            or []
        )
        # Normalize
        out = []
        for r in data:
            item = r.get("items") or {}
            out.append(
                {
                    "line_id": r["id"],
                    "item_id": r["item_id"],
                    "item_name": item.get("name", ""),
                    "unit": item.get("unit", "") or "",
                    "category": item.get("category", ""),
                    "requested_qty": int(r.get("requested_qty") or 0),
                    "approved_qty": None if r.get("approved_qty") is None else int(r.get("approved_qty")),
                }
            )
        return out
    except Exception:
        return []


def update_approved_quantities(sb, request_id: int, approved_map: Dict[int, int]) -> bool:
    """
    approved_map: {line_id: approved_qty}
    """
    try:
        for line_id, qty in approved_map.items():
            sb.table("request_lines").update({"approved_qty": int(qty)}).eq("id", int(line_id)).execute()

        sb.table("requests").update({"status": "Approved - Not Received", "updated_at": datetime.utcnow().isoformat()}).eq("id", request_id).execute()
        return True
    except Exception:
        return False


def mark_request_received(sb, request_id: int) -> bool:
    """
    Deduct approved quantities from inventory and mark received.
    """
    lines = fetch_request_lines(sb, request_id)
    if not lines:
        return False

    # Deduct
    try:
        for ln in lines:
            approved = ln["approved_qty"]
            if approved is None:
                approved = 0
            approved = int(approved)

            # read current
            cur = sb.table("inventory").select("item_id,qty").eq("item_id", ln["item_id"]).execute().data
            cur_qty = int(cur[0]["qty"]) if cur else 0
            new_qty = max(0, cur_qty - approved)

            if cur:
                sb.table("inventory").update({"qty": new_qty, "updated_at": datetime.utcnow().isoformat()}).eq("item_id", ln["item_id"]).execute()
            else:
                sb.table("inventory").insert({"item_id": ln["item_id"], "qty": 0}).execute()

        sb.table("requests").update({"status": "Approved & Received", "updated_at": datetime.utcnow().isoformat()}).eq("id", request_id).execute()
        return True
    except Exception:
        return False


# ----------------------------
# UI HELPERS
# ----------------------------
def stock_badge(qty: int) -> str:
    """
    Color rule:
    - < 50 red
    - 50–200 orange
    - > 200 green
    """
    qty = int(qty)
    if qty <= 0:
        return "Out of stock"
    if qty < 50:
        return "🔴 Low"
    if qty <= 200:
        return "🟠 Medium"
    return "🟢 Good"


def status_badge(status: str) -> str:
    m = {
        "Pending Approval": "🟡 Pending Approval",
        "Approved - Not Received": "🟠 Approved - Not Received",
        "Approved & Received": "🟢 Approved & Received",
    }
    return m.get(status, status)
