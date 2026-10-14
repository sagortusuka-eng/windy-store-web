# ============================================================
#  KC & Windy Smart Stock Tracker & Budget Control - Streamlit
# ============================================================
import calendar
import difflib
import functools
import hashlib
import html as html_lib
import io
import math
import os
import re
import zipfile
from datetime import date, datetime

import pandas as pd
import psycopg2
import streamlit as st

st.set_page_config(page_title="KC & Windy Stock Tracker", page_icon="📦", layout="wide")

st.markdown("""
<style>
    .stApp { background: #f4f6f9; }
    .block-container { padding-top: 1.2rem; max-width: 98%; }
    .app-header {
        background: #1b3b6f; color: white; text-align: center;
        padding: 10px 12px 8px 12px; border-radius: 6px; margin-bottom: 8px;
    }
    .app-header h1 { color: white; font-size: 22px; margin: 0; letter-spacing: 0.5px; }
    .app-header p { color: #a0c4ff; font-size: 12px; font-style: italic; margin: 2px 0 0 0; }
    .factory-bar {
        background: #d9e2ec; color: #1b3b6f; font-weight: 700;
        padding: 6px 12px; border-radius: 4px; margin-bottom: 8px; font-size: 13px;
    }
    div[data-testid="stMetric"] {
        background: white; border: 1px solid #d0d7e2; border-top: 3px solid #1b3b6f;
        padding: 8px 12px; border-radius: 4px;
    }
    div[data-testid="stMetricLabel"] { color: #1b3b6f; font-weight: 700; font-size: 12px; }
    div[data-testid="stMetricValue"] { color: #1b3b6f; font-size: 20px; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px; background: #e0e0e0; padding: 3px 3px 0 3px; border-radius: 4px 4px 0 0;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 700; font-size: 12px; padding: 6px 10px; background: #e0e0e0; color: #333;
    }
    .stTabs [aria-selected="true"] { background: #1b3b6f !important; color: white !important; }
    .stTabs [data-baseweb="tab-highlight"] { display: none; }
    .stDataFrame { border: 1px solid #d0d7e2; border-radius: 4px; background: white; }
    section[data-testid="stSidebar"] { background: #2d3748; }
    section[data-testid="stSidebar"] * { color: #e2e8f0; }
    section[data-testid="stSidebar"] div[data-baseweb="select"] * { color: #1a202c; }
</style>
""", unsafe_allow_html=True)

# ============================================================
#  CONSTANTS
# ============================================================
FACTORIES = ["KC Washing Plant", "Windy Washing LTD"]
ALL_VIEW = "🌟 CONSOLIDATED (Both Factories)"
DATE_FMT = "%d-%b-%Y"
ISSUE_TYPES = ("Issued", "Internal Issue")
RECEIPT_TYPES = ("Supplier. Rec", "Internal Rec", "Stock Adjustment (+)")
ADJ_OUT = "Stock Adjustment (-)"
COOLDOWN_DAYS = 3
PO_ALERT_DAYS = 7
DEPARTMENTS = ["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"]
CATEGORIES = ["Maintenance Spare Parts", "Electrical Accessories", "Utilities Spare Parts", "Stationeries Items",
              "Production Consumable Items", "Safety and Security", "Cleaning Goods", "Furniture Accessories",
              "Medicine & Others", "Plumbing and Sanitary Goods", "Office Maintenance", "Laboratory Accessories",
              "Uncategorized (Edit Later)"]
UOM = ["Pcs", "Kg"]
INV_COLS = ("sl_no, prod_id, factory_name, item_name, COALESCE(size,'') AS size, "
            "COALESCE(current_stock,0) AS stock, COALESCE(erp_stock,0) AS erp, COALESCE(unit_price,0) AS price")
TRANS_LABELS = {
    "Supplier. Rec": "📥 Supplier Receipt",
    "Issued": "📤 Issue to Production",
    "Internal Rec": "🔁 Internal Receipt (from other unit)",
    "Internal Issue": "🔄 Internal Issue (to other unit)",
    "Stock Adjustment (+)": "➕ Stock Adjustment (Increase)",
    "Stock Adjustment (-)": "➖ Stock Adjustment (Decrease)",
}
TRANS_CODES = {v: k for k, v in TRANS_LABELS.items()}   # label -> code
DS_KG_KEYWORDS = ("super enamel wire", "enamel paint", "anamel paint", "weather coat", "plastic paint", "thinner",
                  "cement", " rope", "welding rod", "wood chips", "perak", "heatproof fiber", "decoloring agent",
                  "gear oil", "lube oil", "compressor fluid", "poly bag", "jeet powder", "copper busbar", "varnish",
                  "blizing rod", "thermocol ball")
REQ_FIELDS = [("req_no", "Requisition No"), ("item", "Item Description"), ("code", "ERP Code (optional)"),
              ("qty", "Req Qty"), ("dept", "Department (optional)"), ("date", "Req Date (optional)")]
REQ_KEYS = {
    "req_no": ["reqno", "requisitionno", "requisitionnumber", "reqnumber", "indentno", "rqsnno", "requisition"],
    "item": ["itemname", "itemdescription", "productname", "materialdescription", "description", "item", "product"],
    "code": ["erpcode", "itemcode", "productcode", "materialcode", "partno", "code"],
    "qty": ["reqqty", "requisitionqty", "requestedqty", "requiredqty", "quantity", "qty"],
    "dept": ["department", "dept"],
    "date": ["reqdate", "requisitiondate", "date"],
}
VERDICT = {"FOUND": "✔ FOUND", "SIZE_MISSING": "⚠ SIZE NOT IN LIST", "CODE_MATCH": "⚠ CODE MATCH (name differs)",
           "SIMILAR": "≈ SIMILAR NAME ONLY", "NOT_FOUND": "✘ NOT FOUND - NEW ITEM"}


# ============================================================
#  DATABASE
# ============================================================
@st.cache_resource(show_spinner=False)
def get_conn():
    conn = psycopg2.connect(st.secrets["DB_URL"])
    conn.autocommit = False
    return conn


def fetch(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            if not cur.description:
                return [], []
            return [d[0] for d in cur.description], cur.fetchall()
    except Exception:
        conn.rollback()
        raise


def q(sql, params=None):
    cols, rows = fetch(sql, params)
    return [dict(zip(cols, r)) for r in rows]


def qdf(sql, params=None):
    cols, rows = fetch(sql, params)
    return pd.DataFrame(rows, columns=cols)


def run(sql, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall() if cur.description else None
    except Exception:
        conn.rollback()
        raise


def tx(fn):
    """Database write: commit on success, rollback on any error."""
    @functools.wraps(fn)
    def inner(*a, **k):
        conn = get_conn()
        try:
            res = fn(*a, **k)
            conn.commit()
            return True if res is None else res
        except Exception as e:
            conn.rollback()
            st.error(f"❌ Database error (rollback kora holo): {e}")
            return None
    return inner


def fw(fac, alias=""):
    """Factory filter. CONSOLIDATED / None = no filter."""
    if not fac or "CONSOLIDATED" in fac:
        return "", []
    return f" AND {alias}factory_name=%s", [fac]


@st.cache_resource(show_spinner="Database tayeri hocche...")
def init_db():
    conn = get_conn()
    ddl = [
        """CREATE TABLE IF NOT EXISTS inventory (
            sl_no INTEGER, prod_id TEXT, factory_name TEXT, item_name TEXT, department TEXT, category TEXT,
            erp_stock REAL DEFAULT 0, current_stock REAL DEFAULT 0, unit_price REAL DEFAULT 0,
            erp_status TEXT DEFAULT 'ERP Pending', unit_name TEXT DEFAULT 'Pcs', size TEXT DEFAULT '')""",
        """CREATE TABLE IF NOT EXISTS transactions (
            id SERIAL PRIMARY KEY, factory_name TEXT, officer_name TEXT, sl_no INTEGER, prod_id TEXT, item_name TEXT,
            qty REAL, trans_type TEXT, day INTEGER, notes TEXT, date TEXT, time TEXT,
            verification_status TEXT DEFAULT 'N/A', erp_grn_status TEXT DEFAULT 'Not Required', erp_grn_date TEXT)""",
        """CREATE TABLE IF NOT EXISTS inter_factory_transfers (
            id SERIAL PRIMARY KEY, transfer_ref TEXT UNIQUE, source_factory TEXT, dest_factory TEXT, prod_id TEXT,
            item_name TEXT, qty REAL, transfer_date TEXT, transfer_time TEXT, initiated_by TEXT,
            status TEXT DEFAULT 'Completed', notes TEXT)""",
        """CREATE TABLE IF NOT EXISTS audit_correction_tasks (
            id SERIAL PRIMARY KEY, factory_name TEXT, prod_id TEXT, item_name TEXT, variance_type TEXT,
            variance_qty REAL, variance_value REAL, root_cause TEXT, corrective_action TEXT, assigned_officer TEXT,
            task_date TEXT, target_date TEXT, status TEXT DEFAULT 'Open', manager_remarks TEXT,
            priority TEXT DEFAULT 'Medium', verification_status TEXT DEFAULT 'Pending')""",
        """CREATE TABLE IF NOT EXISTS requisition_tracking (
            id SERIAL PRIMARY KEY, factory_name TEXT, req_no TEXT, department TEXT, req_date TEXT, item_name TEXT,
            req_qty REAL, audit_approved_qty REAL DEFAULT 0, actual_received_qty REAL DEFAULT 0, po_date TEXT,
            received_date TEXT, status TEXT DEFAULT 'Req Created', po_delay_days INTEGER DEFAULT 0,
            prod_id TEXT DEFAULT '')""",
        """CREATE TABLE IF NOT EXISTS repair_returns (
            id SERIAL PRIMARY KEY, factory_name TEXT, tracking_code TEXT, gate_pass_no TEXT, item_name TEXT,
            qty REAL, source_type TEXT, return_type TEXT, supplier_name TEXT, sent_date TEXT, return_date TEXT,
            status TEXT DEFAULT 'Pending Return', remarks TEXT, officer_name TEXT)""",
        """CREATE TABLE IF NOT EXISTS production_plans (
            id SERIAL PRIMARY KEY, factory_name TEXT, plan_month TEXT, plan_qty REAL DEFAULT 0, plan_note TEXT,
            updated_by TEXT, updated_at TEXT, UNIQUE(factory_name, plan_month))""",
        """CREATE TABLE IF NOT EXISTS category_budgets (
            id SERIAL PRIMARY KEY, factory_name TEXT, department_name TEXT, category_name TEXT,
            allocated_budget REAL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS import_queue (
            id SERIAL PRIMARY KEY, factory_name TEXT, sl_no INTEGER, prod_id TEXT, item_name TEXT, department TEXT,
            category TEXT, erp_stock REAL DEFAULT 0, current_stock REAL DEFAULT 0, unit_price REAL DEFAULT 0,
            status TEXT DEFAULT 'Pending Approval', size TEXT DEFAULT '')""",
        "CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT, full_name TEXT)",
        "CREATE TABLE IF NOT EXISTS audit_logs (id SERIAL PRIMARY KEY, timestamp TEXT, username TEXT, action_type TEXT, details TEXT)",
        "CREATE TABLE IF NOT EXISTS req_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)",
        "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS size TEXT DEFAULT ''",
        "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS unit_name TEXT DEFAULT 'Pcs'",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS erp_grn_status TEXT DEFAULT 'Not Required'",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS erp_grn_date TEXT",
        "ALTER TABLE requisition_tracking ADD COLUMN IF NOT EXISTS prod_id TEXT DEFAULT ''",
        "ALTER TABLE requisition_tracking ADD COLUMN IF NOT EXISTS audit_approved_qty REAL DEFAULT 0",
        "ALTER TABLE requisition_tracking ADD COLUMN IF NOT EXISTS actual_received_qty REAL DEFAULT 0",
        "ALTER TABLE repair_returns ADD COLUMN IF NOT EXISTS tracking_code TEXT",
        "ALTER TABLE repair_returns ADD COLUMN IF NOT EXISTS gate_pass_no TEXT",
        "ALTER TABLE repair_returns ADD COLUMN IF NOT EXISTS return_type TEXT",
        "ALTER TABLE repair_returns ADD COLUMN IF NOT EXISTS officer_name TEXT",
        "ALTER TABLE import_queue ADD COLUMN IF NOT EXISTS size TEXT DEFAULT ''",
    ]
    try:
        with conn.cursor() as cur:
            for s in ddl:
                cur.execute(s)
            cur.execute("SELECT COUNT(*) FROM users")
            if cur.fetchone()[0] == 0:
                cur.executemany("INSERT INTO users (username, password, role, full_name) VALUES (%s,%s,%s,%s)", [
                    ("Officer_Sagor", hash_password("sagor123"), "Store Officer", "Md. Sagor Ali"),
                    ("Officer_Rahim", hash_password("rahim123"), "Store Officer", "Abdul Rahim"),
                    ("Store_Manager", hash_password("windy123"), "Store Manager", "Manager Admin"),
                    ("Auditor_User", hash_password("audit2026"), "Auditor", "External Auditor"),
                    ("Executive_Sattar", hash_password("sattar123"), "Executive", "Mr. Sattar"),
                ])
            cur.execute("SELECT COUNT(*) FROM category_budgets")
            if cur.fetchone()[0] == 0:
                budgets = [
                    ("KC Washing Plant", "Maintenance", "Maintenance Spare Parts", 328033.0),
                    ("KC Washing Plant", "Maintenance", "Electrical Accessories", 251628.0),
                    ("KC Washing Plant", "Maintenance", "Utilities Spare Parts", 127713.0),
                    ("KC Washing Plant", "Warehouse", "Stationeries Items", 215899.0),
                    ("KC Washing Plant", "Warehouse", "Production Consumable Items", 67558.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Safety and Security", 105882.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Furniture Accessories", 17911.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Cleaning Goods", 15579.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Medicine & Others", 15209.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Plumbing and Sanitary Goods", 2485.0),
                    ("KC Washing Plant", "Admin, HR & Compliance", "Office Maintenance", 1645.0),
                    ("KC Washing Plant", "Lab", "Laboratory Accessories", 22074.0),
                    ("Windy Washing LTD", "Maintenance", "Maintenance Spare Parts", 99417.0),
                    ("Windy Washing LTD", "Maintenance", "Electrical Accessories", 61705.0),
                    ("Windy Washing LTD", "Maintenance", "Utilities Spare Parts", 27268.0),
                    ("Windy Washing LTD", "Warehouse", "Stationeries Items", 144775.0),
                    ("Windy Washing LTD", "Warehouse", "Production Consumable Items", 19231.0),
                    ("Windy Washing LTD", "Admin, HR & Compliance", "Safety and Security", 55021.0),
                    ("Windy Washing LTD", "Admin, HR & Compliance", "Furniture Accessories", 14828.0),
                    ("Windy Washing LTD", "Admin, HR & Compliance", "Cleaning Goods", 8752.0),
                    ("Windy Washing LTD", "Admin, HR & Compliance", "Office Maintenance", 1470.0),
                ]
                cur.executemany("INSERT INTO category_budgets (factory_name, department_name, category_name, allocated_budget) VALUES (%s,%s,%s,%s)", budgets)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    try:  # same name + size can not be saved twice in one factory
        with conn.cursor() as cur:
            cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_name_size
                           ON inventory(factory_name, lower(replace(replace(item_name,' ',''),'.','')), lower(trim(COALESCE(size,''))))""")
        conn.commit()
    except Exception:
        conn.rollback()
    return True


# ============================================================
#  SECURITY & AUDIT
# ============================================================
def hash_password(pw):
    salt = os.urandom(32)
    return salt.hex() + ":" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 100000).hex()


def verify_password(stored, given):
    try:
        if ":" not in stored:  # legacy plain text
            return stored == given
        s, h = stored.split(":")
        return hashlib.pbkdf2_hmac("sha256", given.encode(), bytes.fromhex(s), 100000).hex() == h
    except Exception:
        return False


def verify_manager_password(pw):
    if not pw:
        return False
    r = q("SELECT password FROM users WHERE role='Store Manager'")
    return verify_password(r[0]["password"], pw) if r else pw == "windy123"


def audit(action, details):
    run("INSERT INTO audit_logs (timestamp, username, action_type, details) VALUES (%s,%s,%s,%s)",
        (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), st.session_state.get("user") or "SYSTEM", action, details))


@tx
def log_event(action, details):
    audit(action, details)


def done(msg):
    """Success message survives the rerun."""
    st.session_state["flash"] = msg
    st.rerun()


def show_flash():
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg)


def mgr_check(key):
    pw = st.text_input("🔐 Store Manager password", type="password", key=key)
    ok = bool(pw) and verify_manager_password(pw)
    if pw and not ok:
        st.caption("❌ Password vul")
    return ok


def sidebar_login():
    with st.sidebar:
        st.markdown("### 🔐 Login")
        if st.session_state.get("user"):
            st.success(f"{st.session_state['user']} [{st.session_state['role']}]")
            if st.button("🚪 Logout"):
                log_event("LOGOUT", f"User {st.session_state['user']} logged out.")
                st.session_state.pop("user", None)
                st.session_state.pop("role", None)
                done("Logged out.")
        else:
            with st.form("login_form"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                if st.form_submit_button("Login"):
                    r = q("SELECT password, role FROM users WHERE username=%s", (u.strip(),))
                    if r and verify_password(r[0]["password"], p.strip()):
                        st.session_state["user"] = u.strip()
                        st.session_state["role"] = r[0]["role"]
                        log_event("LOGIN", f"User {u.strip()} logged in as {r[0]['role']}.")
                        done(f"Welcome {u.strip()}!")
                    else:
                        st.error("Username ba password vul")


# ============================================================
#  HELPERS
# ============================================================
def num(v, default=None):
    try:
        if v is None or pd.isna(v):
            return default
    except (TypeError, ValueError):
        pass
    t = str(v).replace(",", "").strip()
    if t in ("", "nan", "None"):
        return default
    try:
        return float(t)
    except ValueError:
        return default


def txt(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    t = str(v).strip()
    return "" if t.lower() == "nan" else t


def norm_col(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def find_col(df, keys):
    m = {norm_col(c): c for c in df.columns}
    for k in keys:
        if norm_col(k) in m:
            return m[norm_col(k)]
    return None


def norm_name(s):
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def norm_size(s):
    return re.sub(r"[^a-z0-9.]", "", str(s or "").lower())


def is_blank_code(c):
    return str(c or "").strip().upper() in ("", "N/A", "NA", "NONE", "-", "NAN")


def code_base(prod_id, size):
    p, s = str(prod_id or "").strip(), str(size or "").strip()
    if s and len(p) > len(s) + 1 and p.lower().endswith("-" + s.lower()):
        return p[:-(len(s) + 1)]
    return ""


def parse_date(s):
    t = str(s or "").strip()
    if not t or t.lower() in ("none", "nan", "not received", "pending po", "not returned"):
        return None
    for f in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, f)
        except ValueError:
            continue
    return None


def age_days(start_s, end_s=None):
    s = parse_date(start_s)
    if not s:
        return None
    e = parse_date(end_s) or datetime.now()
    return max((e - s).days, 0)


def other_factory(f):
    return "Windy Washing LTD" if f == "KC Washing Plant" else "KC Washing Plant"


def item_label(r):
    return f"SL {r['sl_no']} | {r['factory_name']} | {r['item_name']} [{r['size'] or '-'}] | {r['prod_id']} | Stock {float(r['stock'] or 0):g}"


def next_free_temp(fac):
    used = {str(r["prod_id"]) for r in q("SELECT prod_id FROM inventory WHERE factory_name=%s", (fac,))}
    n = 1
    while f"TEMP-{n:04d}" in used:
        n += 1
    return f"TEMP-{n:04d}"


def insert_tx(fac, officer, sl, pid, name, qty, ttype, day, notes, date_s, time_s, verif, grn="Not Required"):
    run("""INSERT INTO transactions (factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, day,
           notes, date, time, verification_status, erp_grn_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (fac, officer, sl, pid, name, qty, ttype, day, notes, date_s, time_s, verif, grn))


def export_buttons(df, name):
    if df is None or df.empty:
        st.caption("Download korar moto data nei.")
        return
    c1, c2, c3 = st.columns(3)
    c1.download_button("⬇️ CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{name}.csv", "text/csv", key=f"csv_{name}")
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    c2.download_button("⬇️ Excel", buf.getvalue(), f"{name}.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"xls_{name}")
    pdf = to_pdf(df, name)
    if pdf:
        c3.download_button("⬇️ PDF", pdf, f"{name}.pdf", "application/pdf", key=f"pdf_{name}")
    else:
        c3.caption("PDF: 'pip install reportlab'")


def to_pdf(df, title):
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    except ImportError:
        return None
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18)
    data = [[str(c) for c in df.columns]]
    for r in df.values.tolist():
        data.append(["" if (v is None or (isinstance(v, float) and math.isnan(v))) else str(v) for v in r])
    t = Table(data, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3b6f")),
                           ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("FONTSIZE", (0, 0), (-1, -1), 7), ("GRID", (0, 0), (-1, -1), 0.3, colors.grey)]))
    doc.build([Paragraph(title, getSampleStyleSheet()["Title"]), t])
    return buf.getvalue()


def read_any(upload):
    if upload.name.lower().endswith(".csv"):
        return pd.read_csv(upload, dtype=object)
    return pd.read_excel(upload, dtype=object)


def backup_zip():
    """Every table as CSV inside one zip."""
    buf = io.BytesIO()
    tables = [r["table_name"] for r in q("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")]
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for t in tables:
            z.writestr(f"{t}.csv", qdf(f'SELECT * FROM "{t}"').to_csv(index=False))
    return buf.getvalue()


# ============================================================
#  ITEM RESOLVING
# ============================================================
def resolve_item(fac, key):
    """SL No (exact) -> ERP code -> name (exact) -> partial name/size. Returns (row, candidates)."""
    k = str(key or "").strip()
    if not k:
        return None, []
    stages = []
    if k.isdigit():
        stages.append(("sl_no=%s", [int(k)]))
    stages.append(("LOWER(TRIM(prod_id))=LOWER(%s)", [k]))
    stages.append(("LOWER(TRIM(item_name))=LOWER(%s)", [k]))
    like = f"%{k.lower()}%"
    stages.append(("(LOWER(item_name) LIKE %s OR LOWER(COALESCE(size,'')) LIKE %s)", [like, like]))
    fsql, fp = fw(fac)
    for where, params in stages:
        rows = q(f"SELECT {INV_COLS} FROM inventory WHERE {where}{fsql} ORDER BY factory_name, sl_no", params + fp)
        if len(rows) == 1:
            return rows[0], rows
        if len(rows) > 1:
            return None, rows
    return None, []


def search_items(fac, term):
    like = f"%{term.lower()}%"
    fsql, fp = fw(fac)
    return q(f"""SELECT {INV_COLS} FROM inventory
                 WHERE (LOWER(item_name) LIKE %s OR LOWER(COALESCE(size,'')) LIKE %s OR LOWER(prod_id) LIKE %s
                        OR CAST(sl_no AS TEXT)=%s){fsql} ORDER BY sl_no LIMIT 100""",
             [like, like, like, term] + fp)


def inv_options(fac):
    fsql, fp = fw(fac)
    rows = q(f"""SELECT sl_no, prod_id, factory_name, item_name, COALESCE(size,'') AS size, department, category,
                 COALESCE(erp_stock,0) AS erp_stock, COALESCE(current_stock,0) AS current_stock,
                 COALESCE(unit_price,0) AS unit_price, COALESCE(NULLIF(unit_name,''),'Pcs') AS unit_name
                 FROM inventory WHERE 1=1{fsql} ORDER BY factory_name, sl_no""", fp)
    return {f"SL {r['sl_no']} | {r['factory_name']} | {r['item_name']} [{r['size'] or '-'}] | {r['prod_id']}": r for r in rows}


def find_same_item(fac, name, size):
    nn, ns = norm_name(name), norm_size(size)
    for r in q("SELECT sl_no, prod_id, item_name, COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s", (fac,)):
        if norm_name(r["item_name"]) == nn and norm_size(r["size"]) == ns:
            return r
    return None


def find_same_in_other(prod_id, name, other_fac, size):
    """Same product (NAME + SIZE) in other factory: exact -> fuzzy name -> same ERP code."""
    ns, nn = norm_size(size), norm_name(name)
    rows = [r for r in q(f"SELECT {INV_COLS} FROM inventory WHERE factory_name=%s", (other_fac,))
            if norm_size(r["size"]) == ns]
    exact = [r for r in rows if nn and norm_name(r["item_name"]) == nn]
    if exact:
        same = [r for r in exact if r["prod_id"] == prod_id]
        return {**max(same or exact, key=lambda r: r["stock"] or 0), "level": "exact"}
    best, best_s = None, 0.0
    for r in rows:
        s = difflib.SequenceMatcher(None, nn, norm_name(r["item_name"])).ratio()
        if s > best_s:
            best, best_s = r, s
    if best and best_s >= 0.88:
        return {**best, "level": "fuzzy"}
    if prod_id and not is_blank_code(prod_id):
        bc = [r for r in rows if r["prod_id"] == prod_id]
        if bc:
            return {**bc[0], "level": "code"}
    return None


def recent_issue(fac, sl, ref_dt):
    for r in q("""SELECT date, time, qty, officer_name FROM transactions WHERE factory_name=%s AND sl_no=%s
                  AND trans_type IN ('Issued','Internal Issue') ORDER BY id DESC""", (fac, sl)):
        dt = None
        for s, f in ((f"{r['date']} {r['time']}", "%d-%b-%Y %I:%M %p"), (str(r["date"]), DATE_FMT)):
            try:
                dt = datetime.strptime(s.strip(), f)
                break
            except ValueError:
                continue
        if dt and 0 <= (ref_dt - dt).total_seconds() < COOLDOWN_DAYS * 86400:
            return dt, r["qty"], r["officer_name"]
    return None


# ============================================================
#  IMPORT ENGINE (Master Inventory, in-memory index)
# ============================================================
def empty_index():
    return {"all": [], "name": {}, "code": {}, "codes": set(), "max_sl": 0, "temp": 0}


def idx_add(idx, sl, code, name, size):
    e = {"sl": sl, "code": str(code or ""), "name": name or "", "size": size or "",
         "nn": norm_name(name), "ns": norm_size(size)}
    idx["all"].append(e)
    if e["nn"]:
        idx["name"].setdefault(e["nn"], []).append(e)
    ck = e["code"].strip().lower()
    if ck:
        idx["code"].setdefault(ck, []).append(e)
        idx["codes"].add(ck)
        b = code_base(e["code"], e["size"]).lower()
        if b:
            idx["code"].setdefault(b, []).append(e)
    try:
        idx["max_sl"] = max(idx["max_sl"], int(sl))
    except (TypeError, ValueError):
        pass
    return e


def load_index(fac):
    idx = empty_index()
    for r in q("SELECT sl_no, prod_id, item_name, COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s", (fac,)):
        idx_add(idx, r["sl_no"], r["prod_id"], r["item_name"], r["size"])
    mq = q("SELECT COALESCE(MAX(sl_no),0) AS m FROM import_queue WHERE factory_name=%s", (fac,))[0]["m"]
    idx["max_sl"] = max(idx["max_sl"], int(mq or 0))
    return idx


def idx_find(idx, code, name, size, claim_blank=True, loose=True):
    ns, nn = norm_size(size), norm_name(name)
    ck = "" if is_blank_code(code) else str(code).strip().lower()
    pools = []
    if ck:
        pools.append(idx["code"].get(ck, []))
    if nn:
        pools.append(idx["name"].get(nn, []))
    for p in pools:
        for e in p:
            if e["ns"] == ns:
                return e
    if claim_blank and ns:
        for p in pools:
            for e in p:
                if not e["ns"]:
                    return e
    if loose and not ns:
        for p in pools:
            if len(p) == 1:
                return p[0]
    return None


def unique_code(idx, code, size):
    base = str(code).strip()
    if base.lower() not in idx["codes"]:
        return base
    s = str(size or "").strip()
    cand = f"{base}-{s}" if s else base
    n = 1
    while cand.lower() in idx["codes"]:
        n += 1
        cand = f"{base}-{s}-{n}" if s else f"{base}-{n}"
    return cand


def temp_code(idx):
    n = idx["temp"] + 1
    while f"temp-{n:04d}" in idx["codes"]:
        n += 1
    idx["temp"] = n
    return f"TEMP-{n:04d}"


def idx_insert(fac, idx, code, name, size, dept, cat, erp, stock, price, unit):
    final = temp_code(idx) if is_blank_code(code) else unique_code(idx, code, size)
    idx["max_sl"] += 1
    sl = idx["max_sl"]
    run("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category,
           erp_stock, current_stock, unit_price, erp_status, unit_name)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ERP Pending',%s)""",
        (sl, final, fac, name, size or "", dept or "Maintenance", cat or "Uncategorized (Edit Later)",
         erp, stock, price or 0.0, unit or "Pcs"))
    idx_add(idx, sl, final, name, size)
    return final


def mirror_to_other(fac, code, name, size, dept, cat, price):
    """New product is also created in the other unit with stock 0."""
    other = other_factory(fac)
    if find_same_item(other, name, size):
        return False
    idx_insert(other, load_index(other), code, name, size, dept, cat, 0.0, 0.0, price, "Pcs")
    return True


def import_rows(fac, rows):
    other = other_factory(fac)
    idx, oidx = load_index(fac), load_index(other)
    st_ = dict(updated=0, added=0, added_zero=0, mirrored=0, dup=0, no_size=0, size_fill=0, code_fix=0, queue_closed=0)
    touched = set()
    for r in rows:
        code = "" if is_blank_code(r["code"]) else str(r["code"]).strip()
        name = r["name"] or code
        size = r["size"] or ""
        e = idx_find(idx, code, name, size)
        if e:
            if e["sl"] in touched:
                st_["dup"] += 1
            touched.add(e["sl"])
            new_size = size if (size and not e["ns"]) else None
            new_code = unique_code(idx, code, size or e["size"]) if (code and e["code"].upper().startswith("TEMP-")) else None
            run("""UPDATE inventory SET current_stock=COALESCE(%s,current_stock), erp_stock=COALESCE(%s,erp_stock),
                   unit_price=COALESCE(%s,unit_price), unit_name=COALESCE(%s,unit_name),
                   size=COALESCE(%s,size), prod_id=COALESCE(%s,prod_id) WHERE sl_no=%s AND factory_name=%s""",
                (r["phys"], r["erp"], r["price"], r["unit"], new_size, new_code, e["sl"], fac))
            if new_size:
                e["size"], e["ns"] = new_size, norm_size(new_size)
                st_["size_fill"] += 1
            if new_code:
                run("UPDATE transactions SET prod_id=%s WHERE sl_no=%s AND factory_name=%s", (new_code, e["sl"], fac))
                run("UPDATE requisition_tracking SET prod_id=%s WHERE factory_name=%s AND prod_id=%s", (new_code, fac, e["code"]))
                e["code"] = new_code
                idx["code"].setdefault(new_code.lower(), []).append(e)
                idx["codes"].add(new_code.lower())
                st_["code_fix"] += 1
            st_["updated"] += 1
        else:
            phys0 = r["phys"] if r["phys"] is not None else 0.0
            erp0 = r["erp"] if r["erp"] is not None else phys0
            idx_insert(fac, idx, code, name, size, r["dept"], r["cat"], erp0, phys0, r["price"], r["unit"])
            touched.add(idx["max_sl"])
            st_["added"] += 1
            st_["added_zero"] += int(phys0 == 0)
            st_["no_size"] += int(not size)
            if idx_find(oidx, code, name, size, claim_blank=False, loose=False) is None:
                idx_insert(other, oidx, code, name, size, r["dept"], r["cat"], 0.0, 0.0, r["price"], r["unit"])
                st_["mirrored"] += 1
    for qr in q("""SELECT id, prod_id, item_name, COALESCE(size,'') AS size FROM import_queue
                   WHERE factory_name=%s AND status='Pending Approval'""", (fac,)):
        if idx_find(idx, qr["prod_id"], qr["item_name"], qr["size"], claim_blank=False, loose=False):
            run("UPDATE import_queue SET status='Approved' WHERE id=%s", (qr["id"],))
            st_["queue_closed"] += 1
    audit("IMPORT_OPENING_STOCK", f"{fac}: added {st_['added']}, updated {st_['updated']}, mirrored {st_['mirrored']}")
    return st_


def detect_import_cols(df):
    c = {
        "code": find_col(df, ["erp code", "erp_code", "prod_id", "item code", "code"]),
        "name": find_col(df, ["item name", "item_name", "description", "product name", "item"]),
        "size": find_col(df, ["size", "item size", "product size"]),
        "phys": find_col(df, ["opening physical stock", "physical stock", "opening stock", "current stock", "qty", "stock"]),
        "erp": find_col(df, ["erp stock", "erp_stock", "erp balance"]),
        "price": find_col(df, ["unit price", "unit_price", "price"]),
        "unit": find_col(df, ["unit", "uom"]),
        "dept": find_col(df, ["department"]),
        "cat": find_col(df, ["category"]),
    }
    if not c["phys"] or (not c["code"] and not c["name"]):
        return None
    return c


def build_import_rows(df, c):
    rows, skipped = [], 0
    for _, r in df.iterrows():
        code = txt(r[c["code"]]) if c["code"] else ""
        name = txt(r[c["name"]]) if c["name"] else ""
        if is_blank_code(code) and not name:
            skipped += 1
            continue
        raw_phys = r[c["phys"]]
        if txt(raw_phys) != "" and num(raw_phys) is None:
            skipped += 1
            continue
        unit = txt(r[c["unit"]]) if c["unit"] else ""
        rows.append({
            "code": code, "name": name,
            "size": txt(r[c["size"]]) if c["size"] else "",
            "phys": num(raw_phys) if txt(raw_phys) != "" else None,
            "erp": num(r[c["erp"]]) if c["erp"] and txt(r[c["erp"]]) != "" else None,
            "price": num(r[c["price"]]) if c["price"] else None,
            "unit": unit if unit in UOM else None,
            "dept": txt(r[c["dept"]]) if c["dept"] else "",
            "cat": txt(r[c["cat"]]) if c["cat"] else "",
        })
    return rows, skipped


# ============================================================
#  ERP MATCH CHECK HELPERS
# ============================================================
def ec_index():
    out = {}
    for f in FACTORIES:
        idx = empty_index()
        for r in q("""SELECT sl_no, prod_id, item_name, COALESCE(size,'') AS size, COALESCE(erp_stock,0) AS erp,
                      COALESCE(current_stock,0) AS phys FROM inventory WHERE factory_name=%s""", (f,)):
            e = idx_add(idx, r["sl_no"], r["prod_id"], r["item_name"], r["size"])
            e["erp"], e["phys"] = r["erp"], r["phys"]
        out[f] = idx
    return out


def ec_lookup(index, fac, name, size, code):
    idx = index[fac]
    nn, ns = norm_name(name), norm_size(size)
    ck = "" if is_blank_code(code) else str(code).strip().lower()
    name_rows = idx["name"].get(nn, []) if nn else []
    code_rows = idx["code"].get(ck, []) if ck else []
    base = name_rows or (code_rows if not nn else [])
    if base:
        sizes = ", ".join(sorted({e["size"] or "(no size)" for e in base}))
        if ns:
            hit = [e for e in base if e["ns"] == ns]
            if hit:
                return "FOUND", hit, f"Size exists. Sizes: {sizes}"
            return "SIZE_MISSING", base, f"Size '{size}' NOT in list. Sizes: {sizes}"
        return "FOUND", base, f"Product exists. Sizes: {sizes}"
    if code_rows:
        return "CODE_MATCH", code_rows, "Same ERP code, DIFFERENT name - please check"
    similar = []
    if nn and len(nn) >= 3:
        similar = [e for k, lst in idx["name"].items() if nn in k or k in nn for e in lst][:60]
    if similar:
        return "SIMILAR", similar, "Exact product not found - similar names"
    return "NOT_FOUND", [], "NOT in system - NEW product / size"


# ============================================================
#  GUARDS
# ============================================================
def guard(write=True):
    if not st.session_state.get("user"):
        st.warning("🔑 Sidebar theke login korun.")
        return False
    if write and st.session_state.get("role") == "Auditor":
        st.error("Auditor role read-only.")
        return False
    if write and "CONSOLIDATED" in st.session_state.get("factory", ""):
        st.error("CONSOLIDATED view-te edit kora jabe na. Specific factory select korun.")
        return False
    return True


# ============================================================
#  TAB 1 - TRANSACTIONS
# ============================================================
@tx
def save_transaction(fac, item, qty, ttype, tx_dt, notes, verified, xfer_ok):
    user = st.session_state.get("user", "")
    sl, pid, name = item["sl_no"], item["prod_id"], item["item_name"]
    stock = float(item["stock"] or 0)
    date_s, time_s, day = tx_dt.strftime(DATE_FMT), datetime.now().strftime("%I:%M %p"), tx_dt.day
    verif = "Verified"

    if ttype in ISSUE_TYPES:
        rec = recent_issue(fac, sl, datetime.combine(tx_dt, datetime.now().time()))
        if rec and not verified:
            st.error("Cooldown: physical verification tick korun.")
            return False
        verif = "Physically Verified" if verified else "Not Required"

    if ttype in ISSUE_TYPES and qty > stock:
        shortage = qty - stock
        other = find_same_in_other(pid, name, other_factory(fac), item["size"])
        if not other or float(other["stock"] or 0) < shortage or not xfer_ok:
            st.error("Transfer possible nay / confirm kora hoy nai.")
            return False
        ref_no = f"TRF-{datetime.now():%Y%m%d%H%M%S%f}"
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s",
            (shortage, other["sl_no"], other["factory_name"]))
        run("UPDATE inventory SET current_stock=current_stock+%s WHERE sl_no=%s AND factory_name=%s", (shortage, sl, fac))
        run("""INSERT INTO inter_factory_transfers (transfer_ref, source_factory, dest_factory, prod_id, item_name, qty,
               transfer_date, transfer_time, initiated_by, status, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Completed',%s)""",
            (ref_no, other["factory_name"], fac, pid, name, shortage, date_s, time_s, user,
             f"Auto-transfer for shortage during issue (source item: {other['item_name']} [{other['prod_id']}])"))
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s", (qty, sl, fac))
        insert_tx(fac, user, sl, pid, name, qty, ttype, day,
                  f"{notes} [Auto-transferred {shortage:g} pcs from {other['factory_name']}]".strip(),
                  date_s, time_s, verif)
        audit("AUTO_TRANSFER", f"{shortage:g} pcs from {other['factory_name']} to {fac} for {pid}")
        return True

    if ttype in RECEIPT_TYPES:
        grn = "Pending" if ttype == "Supplier. Rec" else "Not Required"
        run("UPDATE inventory SET current_stock=current_stock+%s WHERE sl_no=%s AND factory_name=%s", (qty, sl, fac))
        insert_tx(fac, user, sl, pid, name, qty, ttype, day, notes, date_s, time_s, "Verified", grn)
    else:
        if qty > stock:
            st.error(f"Available stock ({stock:g}) kom ache requested qty ({qty:g}) theke.")
            return False
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s", (qty, sl, fac))
        insert_tx(fac, user, sl, pid, name, qty, ttype, day, notes, date_s, time_s, verif)
    audit("TRANSACTION", f"{fac}: {ttype} {qty:g} of {pid} ({name})")
    return True


@tx
def delete_transaction(tid):
    t = q("SELECT * FROM transactions WHERE id=%s", (tid,))[0]
    if t["trans_type"] in RECEIPT_TYPES:
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s", (t["qty"], t["sl_no"], t["factory_name"]))
    elif t["trans_type"] in ISSUE_TYPES + (ADJ_OUT,):
        run("UPDATE inventory SET current_stock=current_stock+%s WHERE sl_no=%s AND factory_name=%s", (t["qty"], t["sl_no"], t["factory_name"]))
    run("DELETE FROM transactions WHERE id=%s", (tid,))
    audit("DELETE_TRANS", f"Deleted transaction ID {tid}, stock reverted")
    return True


@tx
def update_tx_meta(tid, date_s, notes):
    run("UPDATE transactions SET date=%s, notes=%s WHERE id=%s", (date_s, notes, tid))
    audit("EDIT_TRANS", f"Transaction {tid}: date/notes edited")
    return True


def tab_transactions():
    fac, fsql, fp = FAC, FSQL, FP
    left, right = st.columns([1, 2])
    with left:
        st.markdown("#### 📝 New Transaction")
        st.text_input("Authenticated Officer", value=st.session_state.get("user", "-"), disabled=True)
        if is_cons_view:
            st.warning("CONSOLIDATED view-te entry hoy na. Sidebar theke factory select korun.")
        search = st.text_input("🔍 Search (Name / Size / ERP / SL)", key="tx_search")
        item, blocked, need_xfer, xfer_ok = None, False, False, False
        if search.strip():
            cands = search_items(fac, search.strip())
            if cands:
                opts = {item_label(c): c for c in cands}
                item = opts[st.selectbox("Pick item", list(opts), key="tx_pick")]
            else:
                st.warning("Kichu paoa jay nai.")
        else:
            key = st.text_input("SL No / ERP Code", key="tx_key")
            if key.strip():
                item, cands = resolve_item(fac, key.strip())
                if item is None:
                    st.error("Item paoa jay nai" if not cands else f"{len(cands)} ta item match kore - exact SL No likhun")

        # FIX: options are labels, lookup is label -> code
        type_label = st.selectbox("Transaction Type", list(TRANS_CODES), key="tx_type")
        ttype = TRANS_CODES[type_label]
        qty = st.number_input("Quantity", min_value=0.0, step=1.0, key="tx_qty")
        tx_date = st.date_input("Date", value=date.today(), max_value=date.today(), key="tx_date")
        verified = st.checkbox("Physically Verified (3-Day cooldown check)", key="tx_ver")
        notes = st.text_area("Remarks", key="tx_notes")

        if item is not None:
            st.info(f"**{item['item_name']}** [{item['size'] or '-'}] | SL {item['sl_no']} | ERP {item['prod_id']} | "
                    f"Stock **{float(item['stock']):g}** | Short: {max(float(item['erp']) - float(item['stock']), 0):g}")
            if qty > 0:
                if ttype in ISSUE_TYPES:
                    rec = recent_issue(fac, item["sl_no"], datetime.combine(tx_date, datetime.now().time()))
                    if rec and not verified:
                        st.warning(f"Cooldown: {rec[0]:%d-%b-%Y %I:%M %p} te issue hoyeche (Qty {rec[1]:g}, {rec[2]}). "
                                   "Physical verify tick korun.")
                        blocked = True
                if qty > float(item["stock"]) and ttype in ISSUE_TYPES:
                    shortage = qty - float(item["stock"])
                    other = find_same_in_other(item["prod_id"], item["item_name"], other_factory(fac), item["size"])
                    if other and float(other["stock"] or 0) >= shortage:
                        need_xfer = True
                        st.warning(f"⚠️ Stock short {shortage:g}. {other['factory_name']} theke auto-transfer hobe "
                                   f"({other['item_name']} [{other['prod_id']}], stock {float(other['stock']):g}, "
                                   f"match: {other['level']}).")
                        xfer_ok = st.checkbox("Transfer confirm kore issue korun", key="tx_xfer")
                    else:
                        st.error(f"Shortage {shortage:g} - other unit-e enough stock/same item nei.")
                        blocked = True
                elif qty > float(item["stock"]) and ttype not in RECEIPT_TYPES:
                    st.error("Stock kom ache.")
                    blocked = True

        can_write = bool(st.session_state.get("user")) and st.session_state.get("role") != "Auditor" and not is_cons_view
        disabled = item is None or blocked or (need_xfer and not xfer_ok) or not can_write
        if not can_write:
            st.caption("Save korte login + specific factory + non-Auditor role lage.")
        if st.button("💾 Save & Update Stock", type="primary", disabled=disabled, use_container_width=True):
            if guard() and save_transaction(fac, item, qty, ttype, tx_date, notes, verified, xfer_ok):
                done("✅ Transaction saved, stock updated.")

    with right:
        st.markdown("#### 📜 Recent Transactions")
        tdf = qdf(f"""SELECT id, factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type,
                      verification_status, notes, date, time FROM transactions WHERE 1=1{fsql}
                      ORDER BY id DESC LIMIT 300""", fp)
        if not tdf.empty:
            tdf["trans_type"] = tdf["trans_type"].map(lambda c: TRANS_LABELS.get(c, c))
            tdf["date_time"] = tdf[["date", "time"]].fillna("").agg(" ".join, axis=1)
            tdf = tdf.drop(columns=["date", "time"])
        st.dataframe(tdf, hide_index=True, use_container_width=True)
        export_buttons(tdf, "transactions")

        with st.expander("🔐 Manager: Delete / Edit a transaction"):
            if tdf.empty:
                st.caption("Kono transaction nei.")
            else:
                tid = int(st.selectbox("Transaction ID", tdf["id"].tolist(), key="tx_mgr_id"))
                trow = tdf[tdf["id"] == tid].iloc[0]
                pw_ok = mgr_check("tx_mgr_pw")
                if st.button("🗑 Delete & revert stock", key="tx_del"):
                    if not pw_ok:
                        st.error("Manager password thik nei.")
                    elif delete_transaction(tid):
                        done("Transaction deleted, stock reverted.")
                cur_d = parse_date(str(trow["date_time"]).split(" ")[0] if trow["date_time"] else None)
                ed = st.date_input("New date", value=cur_d.date() if cur_d else date.today(), key="tx_ed_date")
                en = st.text_input("Remarks", value=trow["notes"] or "", key="tx_ed_notes")
                if st.button("💾 Save edit", key="tx_ed_btn"):
                    if not pw_ok:
                        st.error("Manager password thik nei.")
                    elif update_tx_meta(tid, ed.strftime(DATE_FMT), en.strip()):
                        done("Transaction updated.")

    st.markdown("#### 🚨 Low & Negative Stock Alerts (≤ 5 pcs)")
    alerts = qdf(f"""SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,'') AS size, current_stock
                     FROM inventory WHERE current_stock <= 5{fsql} ORDER BY current_stock ASC""", fp)
    if not alerts.empty:
        alerts["status"] = alerts.current_stock.apply(lambda s: "🔴 NEGATIVE (URGENT)" if s < 0 else "⚠️ LOW STOCK")
    st.dataframe(alerts, hide_index=True, use_container_width=True)


# ============================================================
#  TAB 2 - INVENTORY
# ============================================================
@tx
def add_item(fac, code, name, size, dept, cat, stock, price):
    ex = find_same_item(fac, name, size)
    if ex:  # same name + size already exists -> stock add, no duplicate
        run("""UPDATE inventory SET current_stock=COALESCE(current_stock,0)+%s,
               unit_price=CASE WHEN %s>0 THEN %s ELSE unit_price END WHERE sl_no=%s AND factory_name=%s""",
            (stock, price, price, ex["sl_no"], fac))
        if stock > 0:
            now = datetime.now()
            insert_tx(fac, st.session_state["user"], ex["sl_no"], ex["prod_id"], name, stock, "Stock Adjustment (+)",
                      now.day, "Stock added to existing item (Add New Item)", now.strftime(DATE_FMT),
                      now.strftime("%I:%M %p"), "Verified")
        audit("ADD_STOCK_EXISTING", f"{fac}: {name} [{size}] +{stock:g}")
        return ("exists", ex["sl_no"])
    code = next_free_temp(fac) if is_blank_code(code) else code.strip()
    if q("SELECT 1 AS x FROM inventory WHERE prod_id=%s AND factory_name=%s", (code, fac)):
        st.error(f"ERP Code '{code}' already exists in {fac}!")
        return False
    mx = q("SELECT COALESCE(MAX(sl_no),0) AS m FROM inventory WHERE factory_name=%s", (fac,))[0]["m"]
    run("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category,
           erp_stock, current_stock, unit_price, erp_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ERP Pending')""",
        (int(mx) + 1, code, fac, name, size, dept, cat, stock, stock, price))
    mirrored = mirror_to_other(fac, code, name, size, dept, cat, price)
    audit("ADD_ITEM", f"{fac}: {name} [{size}] [{code}]" + (" + copied to other unit" if mirrored else ""))
    return ("new", int(mx) + 1)


@tx
def update_item(fac, sl, old_code, old_name, code, name, size, dept, cat, erp, phys, price, unit):
    if any(norm_name(r["item_name"]) == norm_name(name) and norm_size(r["size"]) == norm_size(size)
           for r in q("SELECT item_name, COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s AND sl_no<>%s", (fac, sl))):
        st.error(f"'{name}' [{size}] already exists in {fac}!")
        return False
    if code != old_code and q("SELECT 1 AS x FROM inventory WHERE factory_name=%s AND prod_id=%s AND sl_no<>%s", (fac, code, sl)):
        st.error(f"ERP Code '{code}' already used!")
        return False
    run("""UPDATE inventory SET prod_id=%s, item_name=%s, size=%s, department=%s, category=%s, erp_stock=%s,
           current_stock=%s, unit_price=%s, unit_name=%s WHERE sl_no=%s AND factory_name=%s""",
        (code, name, size, dept, cat, erp, phys, price, unit, sl, fac))
    if code != old_code or name != old_name:
        run("UPDATE transactions SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (code, name, sl, fac))
        run("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND prod_id=%s", (code, name, fac, old_code))
    audit("EDIT_INVENTORY", f"{fac} SL {sl}: [{old_code}] {old_name} -> [{code}] {name} [{size}]")
    return True


@tx
def delete_item(fac, sl, pid, name):
    run("DELETE FROM inventory WHERE sl_no=%s AND prod_id=%s AND factory_name=%s", (sl, pid, fac))
    audit("DELETE_INVENTORY", f"Deleted {name} [{pid}] from {fac}")
    return True


@tx
def do_import_opening(fac, rows):
    return import_rows(fac, rows)


def inv_master_view():
    inv = qdf(f"""SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,'') AS size, department, category,
                  COALESCE(erp_stock,0) AS erp_stock, COALESCE(current_stock,0) AS current_stock,
                  COALESCE(unit_price,0) AS unit_price, erp_status FROM inventory WHERE 1=1{FSQL}
                  ORDER BY factory_name, sl_no""", FP)
    if inv.empty:
        st.info("Kono item nei.")
        return
    inv["variance"] = inv.current_stock - inv.erp_stock
    inv["erp_value"] = inv.erp_stock * inv.unit_price
    inv["phys_value"] = inv.current_stock * inv.unit_price
    inv["var_value"] = inv.variance * inv.unit_price
    c = st.columns(5)
    c[0].metric("Total Items", len(inv))
    c[1].metric("ERP Value", f"{inv.erp_value.sum():,.2f}")
    c[2].metric("Physical Value", f"{inv.phys_value.sum():,.2f}")
    c[3].metric("Variance Value", f"{inv.var_value.sum():,.2f}")
    c[4].metric("Zero / No Stock", int((inv.current_stock <= 0).sum()))
    a, b = st.columns([2, 1])
    term = a.text_input("🔍 Search (Item / Size / ERP / Dept / Category)", key="inv_search")
    mode = b.selectbox("Show", ["All Items (incl. zero)", "Zero / No Stock Only", "In Stock Only (> 0)", "Items without Size"], key="inv_mode")
    view = inv
    if mode == "Zero / No Stock Only":
        view = inv[inv.current_stock <= 0]
    elif mode == "In Stock Only (> 0)":
        view = inv[inv.current_stock > 0]
    elif mode == "Items without Size":
        view = inv[inv["size"].astype(str).str.strip() == ""]
    if term:
        m = view[["item_name", "size", "prod_id", "department", "category"]].astype(str).apply(
            lambda col: col.str.contains(term, case=False, regex=False)).any(axis=1)
        view = view[m]
    st.caption(f"Showing {len(view)} items")
    st.dataframe(view, hide_index=True, use_container_width=True)
    export_buttons(view, "inventory")


def inv_add_import_view():
    st.markdown("#### ➕ Add New Item")
    with st.form("add_item_form", clear_on_submit=False):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("ERP Code (blank = temporary)")
        name = c2.text_input("Item Name*")
        size = c3.text_input("Size*")
        dept = c1.selectbox("Department", DEPARTMENTS)
        cat = c2.selectbox("Category", CATEGORIES)
        stock = c3.number_input("Initial Stock", min_value=0.0, step=1.0)
        price = c1.number_input("Unit Price (BDT)", min_value=0.0, step=1.0)
        submitted = st.form_submit_button("Save Item")
    if submitted and guard():
        if not name.strip() or not size.strip():
            st.error("Item Name ar Size mandatory.")
        else:
            res = add_item(FAC, code, name.strip(), size.strip(), dept, cat, stock, price)
            if res:
                done("Stock added to existing item (no duplicate)." if res[0] == "exists" else "New item added.")

    st.markdown("#### 📥 Import Opening Physical Stock")
    st.download_button("📄 Download import format (CSV)",
                       pd.DataFrame([{"SL No": 1, "ERP Code": "ERP-0001", "Item Name": "Example Item", "Size": "XL",
                                      "Department": "Maintenance", "Category": "Maintenance Spare Parts",
                                      "Opening Physical Stock": 10, "ERP Stock": 10, "Unit Price": 150, "Unit": "Pcs"}]
                                    ).to_csv(index=False).encode("utf-8-sig"),
                       "Opening_Physical_Stock_Format.csv", "text/csv")
    up = st.file_uploader("Excel / CSV", type=["xlsx", "xls", "csv"], key="open_file")
    if up and guard():
        raw = read_any(up)
        cols = detect_import_cols(raw)
        if cols is None:
            st.error("'Opening Physical Stock' column ba ERP Code/Item Name column paoa jay nai.")
            st.write("Columns found:", list(raw.columns))
            return
        rows, skipped = build_import_rows(raw, cols)
        st.caption(f"File rows: {len(raw)} | Valid: {len(rows)} | Skipped: {skipped} | Zero balance items are saved too.")
        st.dataframe(pd.DataFrame(rows).head(200), hide_index=True, use_container_width=True)
        st.download_button("💾 Download backup (all tables, CSV zip) before import", backup_zip(),
                           "windy_backup.zip", "application/zip")
        if st.button("✅ Import now", type="primary", key="do_open_import"):
            st_ = do_import_opening(FAC, rows)
            if st_:
                done(f"Import done: NEW {st_['added']} (zero {st_['added_zero']}), updated {st_['updated']}, "
                     f"mirrored to other unit {st_['mirrored']}, size missing {st_['no_size']}.")


def inv_edit_view():
    if not guard():
        return
    opts = inv_options(FAC)
    if not opts:
        st.info("Item nei.")
        return
    r = opts[st.selectbox("Select item", list(opts), key="edit_sel")]
    k = f"{r['factory_name']}_{r['sl_no']}"
    with st.form(f"edit_item_{k}"):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("ERP Code", r["prod_id"] or "", key=f"e_code_{k}")
        name = c2.text_input("Item Name", r["item_name"] or "", key=f"e_name_{k}")
        size = c3.text_input("Size (mandatory)", r["size"] or "", key=f"e_size_{k}")
        dept = c1.selectbox("Department", DEPARTMENTS,
                            index=DEPARTMENTS.index(r["department"]) if r["department"] in DEPARTMENTS else 0, key=f"e_dept_{k}")
        cat = c2.text_input("Category", r["category"] or "", key=f"e_cat_{k}")
        unit = c3.selectbox("Unit", UOM, index=UOM.index(r["unit_name"]) if r["unit_name"] in UOM else 0, key=f"e_unit_{k}")
        erp = c1.number_input("ERP Stock", value=float(r["erp_stock"]), step=1.0, key=f"e_erp_{k}")
        phys = c2.number_input("Physical Stock", value=float(r["current_stock"]), step=1.0, key=f"e_phys_{k}")
        price = c3.number_input("Unit Price", value=float(r["unit_price"]), min_value=0.0, key=f"e_price_{k}")
        pw = st.text_input("🔐 Store Manager password", type="password", key=f"e_pw_{k}")
        save = st.form_submit_button("💾 Save changes")
    if save:
        if not verify_manager_password(pw):
            st.error("Manager password thik nei.")
        elif not name.strip() or not size.strip():
            st.error("Item Name ar Size mandatory.")
        elif update_item(FAC, r["sl_no"], r["prod_id"], r["item_name"], code.strip() or r["prod_id"], name.strip(),
                         size.strip(), dept, cat.strip(), erp, phys, price, unit):
            done("Inventory item updated.")
    with st.expander("🗑 Delete this item (Manager)"):
        pw2 = mgr_check(f"del_pw_{k}")
        if st.button("Delete item", key=f"del_btn_{k}"):
            if not pw2:
                st.error("Manager password thik nei.")
            elif delete_item(FAC, r["sl_no"], r["prod_id"], r["item_name"]):
                done("Item deleted.")


@tx
def update_queue(qid, code, name, size, dept, cat, erp, phys, price):
    run("""UPDATE import_queue SET prod_id=%s, item_name=%s, size=%s, department=%s, category=%s,
           erp_stock=%s, current_stock=%s, unit_price=%s WHERE id=%s""",
        (code or "N/A", name, size, dept, cat, erp, phys, price, qid))
    return True


@tx
def approve_queue(qr):
    fac = qr["factory_name"]
    code = next_free_temp(fac) if is_blank_code(qr["prod_id"]) else qr["prod_id"]
    if not (qr["size"] or "").strip():
        st.error("Size mandatory - age Edit kore size din.")
        return False
    if find_same_item(fac, qr["item_name"], qr["size"]):
        st.error("Same name + size already in Master Inventory.")
        return False
    if q("SELECT 1 AS x FROM inventory WHERE prod_id=%s AND factory_name=%s", (code, fac)):
        st.error(f"ERP Code '{code}' already in Master.")
        return False
    mx = q("SELECT COALESCE(MAX(sl_no),0) AS m FROM inventory WHERE factory_name=%s", (fac,))[0]["m"]
    run("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category,
           erp_stock, current_stock, unit_price, erp_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ERP Pending')""",
        (int(mx) + 1, code, fac, qr["item_name"], qr["size"], qr["department"], qr["category"],
         qr["erp_stock"], qr["current_stock"], qr["unit_price"]))
    run("UPDATE import_queue SET status='Approved', prod_id=%s WHERE id=%s", (code, qr["id"]))
    mirrored = mirror_to_other(fac, code, qr["item_name"], qr["size"], qr["department"], qr["category"], qr["unit_price"])
    audit("APPROVE_QUEUE", f"{qr['item_name']} [{qr['size']}] into {fac}" + (" + other unit" if mirrored else ""))
    return True


@tx
def delete_queue(qid):
    run("DELETE FROM import_queue WHERE id=%s AND status<>'Approved'", (qid,))
    audit("DELETE_QUEUE", f"Deleted queue ID {qid}")
    return True


def inv_queue_view():
    qd = qdf(f"""SELECT id, factory_name, sl_no, prod_id, item_name, COALESCE(size,'') AS size, department, category,
                 erp_stock, current_stock, unit_price, status FROM import_queue WHERE 1=1{FSQL} ORDER BY id DESC""", FP)
    st.caption("Unmatch / Import Queue: ERP Balance import-e Master-e na paoa item ekhane jay. Approve korle Master-e jabe.")
    st.dataframe(qd, hide_index=True, use_container_width=True)
    if qd.empty:
        return
    pend = [r for r in qd.to_dict("records") if r["status"] == "Pending Approval"]
    if not pend:
        st.success("Pending item nei.")
        return
    opts = {f"Q{r['id']} | {r['factory_name']} | {r['item_name']} [{r['size'] or 'NO SIZE'}] | {r['prod_id']}": r for r in pend}
    r = opts[st.selectbox("Select queue item", list(opts), key="q_sel")]
    if not guard():
        return
    k = str(r["id"])
    with st.form(f"qedit_{k}"):
        c1, c2, c3 = st.columns(3)
        code = c1.text_input("ERP Code (N/A = later)", r["prod_id"] or "", key=f"qc_{k}")
        name = c2.text_input("Item Name", r["item_name"] or "", key=f"qn_{k}")
        size = c3.text_input("Size (mandatory)", r["size"] or "", key=f"qs_{k}")
        dept = c1.selectbox("Department", DEPARTMENTS, key=f"qd_{k}")
        cat = c2.text_input("Category", r["category"] or "", key=f"qcat_{k}")
        price = c3.number_input("Unit Price", value=float(r["unit_price"] or 0), min_value=0.0, key=f"qp_{k}")
        erp = c1.number_input("ERP Stock", value=float(r["erp_stock"] or 0), key=f"qe_{k}")
        phys = c2.number_input("Physical Stock", value=float(r["current_stock"] or 0), key=f"qph_{k}")
        if st.form_submit_button("💾 Save queue edit"):
            if update_queue(r["id"], code.strip(), name.strip(), size.strip(), dept, cat.strip(), erp, phys, price):
                done("Queue item updated.")
    pw = mgr_check(f"qpw_{k}")
    c1, c2 = st.columns(2)
    if c1.button("✔️ Approve to Master Inventory", key=f"qap_{k}", type="primary"):
        if not pw:
            st.error("Manager password din.")
        else:
            fresh = q("SELECT * FROM import_queue WHERE id=%s", (r["id"],))[0]
            if approve_queue(fresh):
                done("Approved & moved to Master Inventory.")
    if c2.button("🗑 Delete queue item", key=f"qdel_{k}"):
        if not pw:
            st.error("Manager password din.")
        elif delete_queue(r["id"]):
            done("Queue item deleted.")


def erp_check_view():
    st.caption("Ei product / size ager theke system-e ache kina, dekhun.")
    c1, c2, c3 = st.columns(3)
    name = c1.text_input("Product name", key="ec_name")
    size = c2.text_input("Size", key="ec_size")
    code = c3.text_input("ERP code", key="ec_code")
    idxs = ec_index()
    if name.strip() or code.strip():
        for f in FACTORIES:
            status, hits, note = ec_lookup(idxs, f, name, size, code)
            st.markdown(f"**{f}**: {VERDICT[status]} - {note}")
            if hits:
                st.dataframe(pd.DataFrame([{"SL": e["sl"], "ERP Code": e["code"], "Item": e["name"], "Size": e["size"],
                                            "ERP Stock": e.get("erp"), "Physical Stock": e.get("phys")} for e in hits[:200]]),
                             hide_index=True, use_container_width=True)
    st.markdown("#### 📋 Bulk check (Excel / CSV: Item Name, Size, ERP Code)")
    up = st.file_uploader("List to check", type=["xlsx", "xls", "csv"], key="bulk_chk")
    if up and st.button("🔍 Run bulk check"):
        df = read_any(up)
        cn = find_col(df, ["item name", "item_name", "description", "item", "product"])
        cs = find_col(df, ["size"])
        cc = find_col(df, ["erp code", "erp_code", "prod_id", "code"])
        out = []
        for _, r in df.iterrows():
            n = txt(r[cn]) if cn else ""
            s = txt(r[cs]) if cs else ""
            c = txt(r[cc]) if cc else ""
            if not n and is_blank_code(c):
                continue
            rec = {"Item Name": n, "Size": s, "ERP Code": c}
            for f, tag in ((FACTORIES[0], "KC"), (FACTORIES[1], "Windy")):
                status, hits, note = ec_lookup(idxs, f, n, s, c)
                rec[f"{tag} Result"] = VERDICT[status]
                rec[f"{tag} Note"] = note
                rec[f"{tag} SL"] = hits[0]["sl"] if status == "FOUND" and hits else ""
            out.append(rec)
        st.success(f"Checked {len(out)} rows")
        export_buttons(pd.DataFrame(out), "ERP_Match_Check_Result")


def tab_inventory():
    t1, t2, t3, t4, t5 = st.tabs(["📋 Master List", "➕ Add / Import", "✏️ Edit (Manager)", "📥 Unmatch Queue", "🔎 ERP Match Check"])
    with t1:
        inv_master_view()
    with t2:
        inv_add_import_view()
    with t3:
        inv_edit_view()
    with t4:
        inv_queue_view()
    with t5:
        erp_check_view()


# ============================================================
#  TAB 3 - ERP AUDIT
# ============================================================
@tx
def import_erp_rows(fac, rows):
    idx = load_index(fac)
    res = dict(matched=0, queued=0, dup=0)
    for r in rows:
        e = idx_find(idx, r["code"], r["name"], r["size"])
        if e:
            new_size = r["size"] if (r["size"] and not e["ns"]) else ""
            run("UPDATE inventory SET erp_stock=%s, size=COALESCE(NULLIF(%s,''), size) WHERE sl_no=%s AND factory_name=%s",
                (r["bal"], new_size, e["sl"], fac))
            res["matched"] += 1
        else:
            pend = q("""SELECT prod_id, item_name, COALESCE(size,'') AS size FROM import_queue
                        WHERE factory_name=%s AND status='Pending Approval'""", (fac,))
            ns, nn = norm_size(r["size"]), norm_name(r["name"])
            dup = any(norm_size(p["size"]) == ns and (norm_name(p["item_name"]) == nn or (
                not is_blank_code(r["code"]) and str(p["prod_id"]).strip().lower() == str(r["code"]).strip().lower()))
                for p in pend)
            if dup:
                res["dup"] += 1
            else:
                mq = q("SELECT COALESCE(MAX(sl_no),0) AS m FROM import_queue WHERE factory_name=%s", (fac,))[0]["m"]
                run("""INSERT INTO import_queue (factory_name, sl_no, prod_id, item_name, size, department, category,
                       erp_stock, current_stock, unit_price, status)
                       VALUES (%s,%s,%s,%s,%s,'Maintenance','Uncategorized (Edit Later)',%s,0,0,'Pending Approval')""",
                    (fac, max(int(mq), idx["max_sl"]) + 1, r["code"] or "N/A", r["name"] or r["code"], r["size"], r["bal"]))
                res["queued"] += 1
    audit("IMPORT_ERP_BALANCE", f"{fac}: matched {res['matched']}, queued {res['queued']}")
    return res


@tx
def adjust_variance(row, qty):
    cur, erp = float(row["current_stock"]), float(row["erp_stock"])
    variance = cur - erp
    kind = "Short" if variance < 0 else "Excess"
    ttype, new = ("Stock Adjustment (+)", cur + qty) if variance < 0 else (ADJ_OUT, cur - qty)
    run("UPDATE inventory SET current_stock=%s WHERE sl_no=%s AND factory_name=%s", (new, row["sl_no"], row["factory_name"]))
    now = datetime.now()
    insert_tx(row["factory_name"], st.session_state["user"], row["sl_no"], row["prod_id"], row["item_name"], qty, ttype,
              now.day, f"ERP variance adjustment ({kind} {abs(variance):g}, adjusted {qty:g})",
              now.strftime(DATE_FMT), now.strftime("%I:%M %p"), "Verified")
    audit("ADJUST_VARIANCE", f"{row['item_name']} [{row['prod_id']}] {kind} adjusted {qty:g}; stock {cur:g}->{new:g}")
    return True


@tx
def set_grn_done_inv(fac, sl):
    run("UPDATE inventory SET erp_status='ERP GRN Done' WHERE sl_no=%s AND factory_name=%s", (sl, fac))
    audit("ERP_STATUS_DONE", f"{fac}: SL {sl} marked ERP GRN Done")
    return True


@tx
def assign_task(fac, row, officer, days, prio, remarks):
    variance = float(row["current_stock"]) - float(row["erp_stock"])
    val = variance * float(row["unit_price"] or 0)
    target = (datetime.now().date().fromordinal(datetime.now().date().toordinal() + days)).strftime(DATE_FMT)
    run("""INSERT INTO audit_correction_tasks (factory_name, prod_id, item_name, variance_type, variance_qty, variance_value,
           root_cause, corrective_action, assigned_officer, task_date, target_date, status, manager_remarks, priority, verification_status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'In Progress',%s,%s,'Pending')""",
        (fac, row["prod_id"], row["item_name"], "Shortage" if variance < 0 else "Excess", variance, val, remarks,
         "Verify physical count & documents", officer, datetime.now().strftime(DATE_FMT), target, remarks, prio))
    audit("ASSIGN_TASK", f"{fac}: correction task {row['item_name']} -> {officer}")
    return True


@tx
def close_task(tid):
    run("UPDATE audit_correction_tasks SET status='Closed', verification_status='Verified by Manager' WHERE id=%s", (tid,))
    audit("CLOSE_TASK", f"Correction task {tid} closed")
    return True


@tx
def delete_task(tid):
    run("DELETE FROM audit_correction_tasks WHERE id=%s", (tid,))
    audit("DELETE_TASK", f"Deleted correction task {tid}")
    return True


@tx
def mark_grn_receipt(tid, date_s):
    run("UPDATE transactions SET erp_grn_status='Done', erp_grn_date=%s WHERE id=%s", (date_s, tid))
    audit("ERP_GRN_DONE", f"Receipt {tid} ERP GRN Done on {date_s}")
    return True


def tab_erp_audit():
    aud = qdf(f"""SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,'') AS size,
                  COALESCE(erp_stock,0) AS erp_stock, COALESCE(current_stock,0) AS current_stock,
                  COALESCE(unit_price,0) AS unit_price, erp_status
                  FROM inventory WHERE 1=1{FSQL} ORDER BY factory_name, sl_no""", FP)
    if not aud.empty:
        aud["variance"] = aud.current_stock - aud.erp_stock
        aud["var_value"] = aud.variance * aud.unit_price
        aud["short_value"] = aud.var_value.where(aud.variance < 0, 0).abs()
        aud["excess_value"] = aud.var_value.where(aud.variance > 0, 0)
        aud["variance_type"] = aud.variance.apply(lambda v: "Shortage" if v < 0 else ("Excess" if v > 0 else "Matched"))
        short = aud[aud.variance < 0]
        exc = aud[aud.variance > 0]
    else:
        short = exc = aud
    tasks = qdf(f"SELECT * FROM audit_correction_tasks WHERE 1=1{FSQL}", FP)
    open_n = int((tasks["status"] != "Closed").sum()) if not tasks.empty else 0
    pend_q = qdf(f"SELECT COUNT(*) AS n FROM import_queue WHERE status='Pending Approval'{FSQL}", FP)
    c = st.columns(6)
    c[0].metric("Mismatched", len(short) + len(exc))
    c[1].metric("Short Items", len(short))
    c[2].metric("Short Value", f"{short.short_value.sum():,.2f}" if not short.empty else "0")
    c[3].metric("Excess Items", len(exc))
    c[4].metric("Open Tasks", open_n)
    c[5].metric("Unmatch Pending", int(pend_q.n.iloc[0]) if not pend_q.empty else 0)

    t_act, t_all, t_short, t_exc, t_match, t_pend, t_plan, t_age = st.tabs(
        ["⚙️ Actions", "📋 All", "🔴 Short", "🟠 Excess", "🟢 Matched", "🟡 ERP Pending", "📝 Correction Plan", "⏱ Receipt Aging"])
    cols = ["factory_name", "sl_no", "prod_id", "item_name", "size", "erp_stock", "current_stock", "variance",
            "unit_price", "short_value", "excess_value", "erp_status", "variance_type"]
    with t_act:
        if guard():
            st.markdown("**📥 Import ERP Balance** (Excel/CSV: ERP Code, Item Name, Size, ERP Balance)")
            up = st.file_uploader("ERP balance file", type=["xlsx", "xls", "csv"], key="erp_bal_file")
            if up and st.button("Import ERP balance", key="erp_bal_btn"):
                df = read_any(up)
                cc = find_col(df, ["erp code", "erp_code", "prod_id", "code"])
                cn = find_col(df, ["item name", "item_name", "description", "item"])
                cs = find_col(df, ["size"])
                cb = find_col(df, ["erp balance", "erp_balance", "erp stock", "balance", "qty", "stock"])
                if not cb or (not cc and not cn):
                    st.error("'ERP Balance' ar ERP Code/Item Name column lagbe.")
                else:
                    rows, skipped = [], 0
                    for _, r in df.iterrows():
                        code = txt(r[cc]) if cc else ""
                        name = txt(r[cn]) if cn else ""
                        bal = num(r[cb]) if txt(r[cb]) != "" else 0.0
                        if (is_blank_code(code) and not name) or bal is None:
                            skipped += 1
                            continue
                        rows.append({"code": code, "name": name, "size": txt(r[cs]) if cs else "", "bal": bal})
                    res = import_erp_rows(FAC, rows)
                    if res is not None:
                        done(f"ERP import: matched {res['matched']}, unmatch queue-e {res['queued']}, "
                             f"already queued {res['dup']}, skipped {skipped}.")

            st.markdown("---")
            st.markdown("**⚖️ Adjust variance to ERP** (Manager)")
            vt = aud[aud.variance != 0] if not aud.empty else aud
            if vt.empty:
                st.success("Sob item ERP-er sathe matched.")
            else:
                labels = {f"{r['item_name']} [{r['size'] or '-'}] | {r['factory_name']} | Var {r['variance']:g}": r
                          for r in vt.to_dict("records")}
                row = labels[st.selectbox("Item", list(labels), key="adj_sel")]
                limit = abs(float(row["variance"]))
                aq = st.number_input("Adjust qty", min_value=0.0, max_value=limit, value=limit, key="adj_qty")
                pw = mgr_check("adj_pw")
                if st.button("⚖️ Adjust", key="adj_btn"):
                    if not pw:
                        st.error("Manager password thik nei.")
                    elif aq <= 0:
                        st.error("Qty 0 er beshi hote hobe.")
                    elif adjust_variance(row, aq):
                        done("Variance adjusted.")

                st.markdown("---")
                st.markdown("**📋 Assign correction task**")
                labels2 = {f"{r['item_name']} [{r['prod_id']}] | {r['factory_name']}": r for r in vt.to_dict("records")}
                row2 = labels2[st.selectbox("Item for task", list(labels2), key="task_item")]
                c1, c2, c3 = st.columns(3)
                officer = c1.selectbox("Officer", ["Officer_Sagor", "Officer_Rahim", "Manager Admin"], key="task_off")
                days = c2.selectbox("Deadline", [1, 2, 3, 7, 15], index=1, format_func=lambda d: f"{d} day(s)", key="task_days")
                prio = c3.selectbox("Priority", ["Critical", "High", "Medium", "Low"], index=1, key="task_prio")
                rem = st.text_input("Root cause / remarks", "Physical recount and verification required", key="task_rem")
                if st.button("Assign task", key="task_btn"):
                    if assign_task(row2["factory_name"], row2, officer, days, prio, rem):
                        done("Correction task assigned.")

                st.markdown("---")
                st.markdown("**✔️ Mark ERP status Done** (ERP Pending item)")
                ep = aud[aud.erp_status == "ERP Pending"]
                if not ep.empty:
                    labels3 = {f"{r['item_name']} [{r['size'] or '-'}] | {r['factory_name']}": r for r in ep.to_dict("records")}
                    row3 = labels3[st.selectbox("Item", list(labels3), key="grn_item")]
                    if st.button("Mark ERP GRN Done", key="grn_btn"):
                        if set_grn_done_inv(row3["factory_name"], row3["sl_no"]):
                            done("ERP status updated.")

    with t_all:
        st.dataframe(aud[cols] if not aud.empty else aud, hide_index=True, use_container_width=True)
        export_buttons(aud, "erp_audit_all")
    with t_short:
        st.dataframe(short[cols] if not short.empty else short, hide_index=True, use_container_width=True)
    with t_exc:
        st.dataframe(exc[cols] if not exc.empty else exc, hide_index=True, use_container_width=True)
    with t_match:
        mt = aud[aud.variance == 0] if not aud.empty else aud
        st.dataframe(mt[cols] if not mt.empty else mt, hide_index=True, use_container_width=True)
    with t_pend:
        pd_ = aud[aud.erp_status == "ERP Pending"] if not aud.empty else aud
        st.dataframe(pd_[cols] if not pd_.empty else pd_, hide_index=True, use_container_width=True)
    with t_plan:
        if tasks.empty:
            st.info("Correction task nei.")
        else:
            st.dataframe(tasks, hide_index=True, use_container_width=True)
            if guard():
                tid = int(st.selectbox("Task ID", tasks["id"].tolist(), key="task_id_sel"))
                pw = mgr_check("task_pw")
                c1, c2 = st.columns(2)
                if c1.button("✅ Verify & Close", key="task_close"):
                    if not pw:
                        st.error("Manager password din.")
                    elif close_task(tid):
                        done("Task closed.")
                if c2.button("🗑 Delete task", key="task_del"):
                    if not pw:
                        st.error("Manager password din.")
                    elif delete_task(tid):
                        done("Task deleted.")
    with t_age:
        rc = qdf(f"""SELECT id, factory_name, date, item_name, prod_id, qty, officer_name FROM transactions
                     WHERE trans_type='Supplier. Rec' AND erp_grn_status='Pending'{FSQL} ORDER BY id DESC""", FP)
        if rc.empty:
            st.success("ERP-e wait korche emon receipt nei.")
        else:
            rc["days_pending"] = rc.date.apply(lambda d: age_days(d) or 0)
            st.caption(f"Receipts waiting for ERP: {len(rc)} | Over 7 days: {int((rc.days_pending > PO_ALERT_DAYS).sum())}")
            st.dataframe(rc, hide_index=True, use_container_width=True)
            if guard():
                labels = {f"ID {r['id']} | {r['item_name']} | qty {r['qty']:g} | {r['date']}": r for r in rc.to_dict("records")}
                rr = labels[st.selectbox("Receipt", list(labels), key="age_sel")]
                gd = st.date_input("ERP PO / GRN date", value=date.today(), key="age_date")
                if st.button("✔️ Mark ERP PO/GRN Done", key="age_btn"):
                    if mark_grn_receipt(int(rr["id"]), gd.strftime(DATE_FMT)):
                        done("Receipt marked ERP GRN Done.")


# ============================================================
#  TAB 4 - ISSUE LEDGER
# ============================================================
def tab_issue_ledger():
    iss = qdf(f"""SELECT t.id, t.date, t.time, t.factory_name, t.item_name, t.prod_id, t.sl_no, t.qty,
                  COALESCE(i.unit_price,0) AS unit_price, t.officer_name, t.trans_type, t.notes, t.verification_status
                  FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                  WHERE t.trans_type IN ('Issued','Internal Issue'){fw(FAC, 't.')[0]} ORDER BY t.id DESC""", FP)
    if not iss.empty:
        iss["total_value"] = iss.qty * iss.unit_price
        iss["type"] = iss.trans_type.map(lambda c: TRANS_LABELS.get(c, c))
        iss["erp_status"] = iss.notes.fillna("").apply(lambda n: "ERP PO Pending" if "Pending" in n else "ERP GRN Completed")
    st.markdown("#### 📋 All Issues")
    st.dataframe(iss, hide_index=True, use_container_width=True)
    export_buttons(iss, "issue_ledger")

    st.markdown("#### 🔍 Item-wise Monthly Issue Search")
    if iss.empty:
        st.info("Issue record nei.")
        return
    c1, c2 = st.columns(2)
    item_txt = c1.text_input("Item Name", key="il_item")
    iss["_dt"] = iss.date.apply(parse_date)
    months = sorted({d.strftime("%b-%Y") for d in iss["_dt"].dropna()},
                    key=lambda s: datetime.strptime(s, "%b-%Y"), reverse=True)
    if not months:
        st.info("Valid date record nei.")
        return
    month = c2.selectbox("Month", months, key="il_month")
    if item_txt.strip():
        m = iss[iss["_dt"].apply(lambda d: d is not None and d.strftime("%b-%Y") == month)]
        m = m[m.item_name.fillna("").str.lower().str.contains(item_txt.strip().lower(), regex=False)]
        res = m.groupby(["date", "item_name", "factory_name"], as_index=False).qty.sum()
        res.columns = ["Date", "Item Name", "Factory", "Qty Issued"]
        st.metric("Total Issued Qty", f"{res['Qty Issued'].sum():g}")
        st.dataframe(res, hide_index=True, use_container_width=True)
        export_buttons(res, f"issue_search_{item_txt.strip()}_{month}")


# ============================================================
#  TAB 5 - TRANSFER HISTORY
# ============================================================
def transfer_items(t):
    m = re.search(r"source item:\s*(.+?)\s*\[([^\]]*)\]", t["notes"] or "")
    size_row = q("""SELECT COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s AND prod_id=%s
                    ORDER BY (LOWER(item_name)=LOWER(%s)) DESC LIMIT 1""", (t["source_factory"], t["prod_id"], t["item_name"]))
    size = size_row[0]["size"] if size_row else ""
    dest = find_same_in_other(t["prod_id"], t["item_name"], t["dest_factory"], size)
    src = None
    if m:
        cand = q("SELECT sl_no, prod_id, item_name, current_stock FROM inventory WHERE factory_name=%s AND prod_id=%s",
                 (t["source_factory"], m.group(2).strip()))
        cand = [c for c in cand if norm_name(c["item_name"]) == norm_name(m.group(1))]
        if cand:
            src = cand[0]
    if not src:
        src = find_same_in_other(t["prod_id"], t["item_name"], t["source_factory"], size)
    return src, dest


@tx
def delete_transfer(t, reverse):
    if reverse:
        src, dest = transfer_items(t)
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s", (t["qty"], dest["sl_no"], t["dest_factory"]))
        run("UPDATE inventory SET current_stock=current_stock+%s WHERE sl_no=%s AND factory_name=%s", (t["qty"], src["sl_no"], t["source_factory"]))
    run("DELETE FROM inter_factory_transfers WHERE id=%s", (t["id"],))
    audit("DELETE_TRANSFER", f"Deleted transfer {t['transfer_ref']}" + (" (balance reversed)" if reverse else " (record only)"))
    return True


@tx
def edit_transfer(t, new_qty, date_s, time_s, notes):
    delta = new_qty - float(t["qty"])
    if abs(delta) > 1e-9:
        src, dest = transfer_items(t)
        if not src or not dest:
            st.error("Inventory item paoa jay nai - quantity change kora jabe na.")
            return False
        run("UPDATE inventory SET current_stock=current_stock+%s WHERE sl_no=%s AND factory_name=%s", (delta, dest["sl_no"], t["dest_factory"]))
        run("UPDATE inventory SET current_stock=current_stock-%s WHERE sl_no=%s AND factory_name=%s", (delta, src["sl_no"], t["source_factory"]))
    run("UPDATE inter_factory_transfers SET qty=%s, transfer_date=%s, transfer_time=%s, notes=%s WHERE id=%s",
        (new_qty, date_s, time_s, notes, t["id"]))
    audit("EDIT_TRANSFER", f"Transfer {t['transfer_ref']}: qty {t['qty']} -> {new_qty}")
    return True


def tab_transfer_history():
    cols_sql = """SELECT id, transfer_ref, source_factory, dest_factory, prod_id, item_name, qty, transfer_date,
                  transfer_time, initiated_by, status, notes FROM inter_factory_transfers"""
    if not FAC or "CONSOLIDATED" in FAC:
        tf = qdf(cols_sql + " ORDER BY id DESC")
    else:
        tf = qdf(cols_sql + " WHERE source_factory=%s OR dest_factory=%s ORDER BY id DESC", (FAC, FAC))
    term = st.text_input("🔍 Search (ref / item / code / factory / date)", key="tf_search")
    view = tf
    if term and not tf.empty:
        view = tf[tf.astype(str).apply(lambda c: c.str.contains(term, case=False, regex=False)).any(axis=1)]
    st.dataframe(view, hide_index=True, use_container_width=True)
    export_buttons(view, "transfer_history")
    with st.expander("🔐 Manager: Delete / Edit transfer"):
        if view.empty:
            st.caption("Transfer nei.")
        else:
            ref = st.selectbox("Transfer", view["transfer_ref"].tolist(), key="tf_sel")
            t = q("SELECT * FROM inter_factory_transfers WHERE transfer_ref=%s", (ref,))[0]
            pw = mgr_check("tf_pw")
            src, dest = transfer_items(t)
            reverse = bool(src and dest)
            if not reverse:
                st.warning("Stock item paoa jay nai - delete korle shudhu record delete hobe, stock change hobe na.")
            c1, c2 = st.columns(2)
            if c1.button("🗑 Delete transfer", key="tf_del"):
                if not pw:
                    st.error("Manager password din.")
                elif delete_transfer(t, reverse):
                    done("Transfer deleted" + (" & stock reversed." if reverse else " (record only)."))
            nq = st.number_input("New quantity", min_value=0.0, value=float(t["qty"] or 0), key="tf_qty")
            nd = st.text_input("Date (DD-Mon-YYYY)", t["transfer_date"] or "", key="tf_date")
            nn = st.text_input("Notes", t["notes"] or "", key="tf_notes")
            if c2.button("💾 Save edit", key="tf_save"):
                if not pw:
                    st.error("Manager password din.")
                elif nq <= 0:
                    st.error("Quantity 0 er beshi hote hobe.")
                elif not parse_date(nd):
                    st.error("Date DD-Mon-YYYY format-e hote hobe.")
                elif edit_transfer(t, nq, nd, t["transfer_time"], nn):
                    done("Transfer updated.")


# ============================================================
#  TAB 6 - REQUISITION
# ============================================================
def req_calc(r):
    req, aud, rec = float(r["req_qty"] or 0), float(r["aud_qty"] or 0), float(r["rec_qty"] or 0)
    base = aud if aud > 0 else req
    pending = max(base - rec, 0)
    now = datetime.now()
    d_req, d_po = parse_date(r["req_date"]), parse_date(r["po_date"])
    age = max((now - d_req).days, 0) if d_req else 0
    delay = max((d_po - d_req).days, 0) if (d_req and d_po) else age
    since_po = max((now - d_po).days, 0) if d_po else 0
    if rec > 0 and pending <= 0:
        st_ = "Fully Received"
    elif rec > 0:
        st_ = "Partially Received"
    elif d_po:
        st_ = "PO Issued - Awaiting Delivery"
    elif aud > 0:
        st_ = "Audit Approved - PO Pending"
    else:
        st_ = "Req Created - Audit Pending"
    return {**r, "aud_qty": aud, "rec_qty": rec, "req_qty": req, "base": base, "pending": pending, "age": age,
            "delay": delay, "since_po": since_po, "calc_status": st_, "has_po": d_po is not None}


def load_requisitions():
    rows = q(f"""SELECT id, factory_name, req_no, department, req_date, item_name, req_qty, audit_approved_qty AS aud_qty,
                 actual_received_qty AS rec_qty, po_date, received_date, COALESCE(prod_id,'') AS prod_id
                 FROM requisition_tracking WHERE 1=1{FSQL} ORDER BY id DESC""", FP)
    return [req_calc(r) for r in rows]


@tx
def create_req_item(fac, code, name, dept):
    mx = q("SELECT COALESCE(MAX(sl_no),0) AS m FROM inventory WHERE factory_name=%s", (fac,))[0]["m"]
    if is_blank_code(code):
        code = next_free_temp(fac)
    run("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, department, category, erp_stock,
           current_stock, unit_price, erp_status, size) VALUES (%s,%s,%s,%s,%s,%s,0,0,0,'ERP Pending','')""",
        (int(mx) + 1, code, fac, name, dept, "Uncategorized (Edit Later)"))
    return code


def find_inv_for_req(fac, code, name):
    if not is_blank_code(code):
        r = q("SELECT sl_no, prod_id, item_name FROM inventory WHERE factory_name=%s AND prod_id=%s", (fac, code))
        if r:
            return r[0]
    if name:
        r = q("SELECT sl_no, prod_id, item_name FROM inventory WHERE factory_name=%s AND LOWER(item_name)=LOWER(%s)", (fac, name))
        if r:
            return r[0]
    return None


@tx
def import_requisition(fac, rows, create_items):
    new_items = 0
    for p in rows:
        inv = find_inv_for_req(fac, p["code"], p["item"])
        if inv:
            code = inv["prod_id"]
        elif create_items:
            code = create_req_item(fac, p["code"], p["item"], p["dept"])
            new_items += 1
        else:
            code = p["code"]
        run("""INSERT INTO requisition_tracking (factory_name, req_no, department, req_date, item_name, req_qty,
               audit_approved_qty, actual_received_qty, status, po_delay_days, prod_id)
               VALUES (%s,%s,%s,%s,%s,%s,0,0,'Req Created - Audit Pending',0,%s)""",
            (fac, p["req_no"], p["dept"], p["date"], p["item"], p["qty"], code))
    audit("IMPORT_REQUISITION", f"Imported {len(rows)} line(s) into {fac}, new items {new_items}")
    return new_items


def find_header_row(raw):
    allk = {k for ks in REQ_KEYS.values() for k in ks}
    best, bi = 0, 0
    for i in range(min(25, len(raw))):
        s = sum(1 for v in raw.iloc[i] if norm_col(txt(v)) in allk)
        if s > best:
            best, bi = s, i
    return bi


def auto_map(heads):
    norm = [norm_col(h) for h in heads]
    mp, used = {}, set()
    for field, keys in REQ_KEYS.items():
        for k in keys:
            hit = next((i for i, n in enumerate(norm) if n == k and i not in used), None)
            if hit is not None:
                mp[field] = hit
                used.add(hit)
                break
    return mp


def req_import_view():
    f = st.file_uploader("ERP Requisition file (Excel / CSV)", type=["xlsx", "xls", "csv"], key="req_file")
    if not f:
        return
    if f.name.lower().endswith(".csv"):
        raw = pd.read_csv(f, header=None, dtype=object, keep_default_na=False)
    else:
        xls = pd.ExcelFile(f)
        raw = xls.parse(st.selectbox("Sheet", xls.sheet_names, key="req_sheet"), header=None, dtype=object)
    raw = raw.fillna("")
    hdr = st.number_input("Header row no. (column names ache je row-e)", 1, max(len(raw), 1),
                          find_header_row(raw) + 1, key="req_hdr")
    hi = int(hdr) - 1
    heads = [txt(v) for v in raw.iloc[hi]]
    labels = ["(none)"] + [f"{i + 1}: {h or '(blank)'}" for i, h in enumerate(heads)]
    auto = auto_map(heads)
    mp = {}
    cols = st.columns(3)
    for i, (key, label) in enumerate(REQ_FIELDS):
        default = labels[auto[key] + 1] if key in auto else "(none)"
        sel = cols[i % 3].selectbox(label, labels, index=labels.index(default), key=f"rmap_{key}_{hi}")
        mp[key] = int(sel.split(":")[0]) - 1 if sel != "(none)" else None
    c1, c2, c3 = st.columns(3)
    fx_no = c1.text_input("Requisition No (fallback)", f"RQSN-{datetime.now():%m%d-%H%M}", key="req_fx_no")
    fx_dept = c2.selectbox("Department (fallback)", DEPARTMENTS, key="req_fx_dept")
    fx_date = c3.date_input("Req date (fallback)", value=date.today(), key="req_fx_date")
    create = st.checkbox("Inventory-te na thaka item auto create korun", value=True, key="req_create")

    parsed, last, ncols = [], {"req_no": "", "dept": "", "date": ""}, raw.shape[1]

    def cell(row, field):
        ci = mp.get(field)
        return txt(row.iloc[ci]) if ci is not None and ci < ncols else ""

    for ridx in range(hi + 1, len(raw)):
        row = raw.iloc[ridx]
        item, code, qty_t = cell(row, "item"), cell(row, "code"), cell(row, "qty")
        if code.upper() in ("N/A", "NA", "NONE", "-"):
            code = ""
        vals = {}
        for fld in ("req_no", "dept", "date"):
            if mp.get(fld) is not None and cell(row, fld):
                last[fld] = cell(row, fld)
            vals[fld] = last[fld] if mp.get(fld) is not None else ""
        if not item and not code and not qty_t:
            continue
        m = re.search(r"\d+(?:\.\d+)?", qty_t.replace(",", ""))
        qty = float(m.group()) if m else 0.0
        d = parse_date(vals["date"]) or datetime.combine(fx_date, datetime.min.time())
        p = {"line": ridx + 1, "req_no": vals["req_no"] or fx_no, "item": item, "code": code, "qty": qty,
             "dept": vals["dept"] or fx_dept, "date": d.strftime(DATE_FMT), "ok": False, "result": ""}
        if not item:
            p["result"] = "Skipped: item description nei"
        elif qty <= 0:
            p["result"] = "Skipped: Req Qty nei"
        elif q("SELECT 1 AS x FROM requisition_tracking WHERE factory_name=%s AND req_no=%s AND LOWER(item_name)=LOWER(%s)",
               (FAC, p["req_no"], item)):
            p["result"] = "Already imported"
        else:
            p["ok"] = True
            p["result"] = "OK"
        parsed.append(p)
    ok_rows = [p for p in parsed if p["ok"]]
    st.caption(f"Lines to import: {len(ok_rows)} | Skipped/already: {len(parsed) - len(ok_rows)}")
    st.dataframe(pd.DataFrame(parsed), hide_index=True, use_container_width=True)
    if st.button("✅ Import requisition", type="primary", disabled=not ok_rows, key="req_import_btn"):
        n = import_requisition(FAC, ok_rows, create)
        if n is not None:
            done(f"Requisition import done: {len(ok_rows)} line(s), new inventory items {n}. "
                 "Audit approved qty 0 - Executive approve korbe.")


def sourcing_email(rows, fac_label, sender, role):
    a = [r for r in rows if r["pending"] > 0 and not r["has_po"] and r["aud_qty"] > 0]
    b = [r for r in rows if r["pending"] > 0 and r["has_po"]]
    if not a and not b:
        return None

    def block(items, mode):
        out = []
        for n, r in enumerate(sorted(items, key=lambda x: -x["age"]), 1):
            code = r["prod_id"] if r["prod_id"] and not r["prod_id"].upper().startswith("TEMP-") else "ERP code awaited"
            aging = (f"Pending for {r['age']} day(s) since requisition" if mode == "A"
                     else f"PO Date: {r['po_date']} | Waiting {r['since_po']} day(s) since PO")
            out.append(f"{n}. {r['item_name']} (ERP: {code})\n   Req No: {r['req_no']} | Req Date: {r['req_date']}\n"
                       f"   Approved: {r['aud_qty']:g} | Received: {r['rec_qty']:g} | PENDING: {r['pending']:g}\n   {aging}")
        return "\n\n".join(out)

    lines = ["Dear Sourcing Manager,", "", f"Greetings from {fac_label} Store.", ""]
    if a:
        lines += [f"The following {len(a)} audit-approved requisition item(s) are still waiting for Purchase Order (PO) issuance. "
                  "Material delivery and GRN are on hold due to the PO delay.", "", "A. PO NOT YET RECEIVED",
                  "-" * 40, block(a, "A"), ""]
    if b:
        lines += [("Additionally, " if a else "") + f"the following {len(b)} item(s) have PO issued but delivery/GRN is pending:",
                  "", "B. PO ISSUED - DELIVERY / GRN PENDING", "-" * 40, block(b, "B"), ""]
    total = sum(r["pending"] for r in a + b)
    lines += [f"Total items: {len(a) + len(b)} | Total pending qty: {total:g}", "",
              "We would appreciate it if you could expedite the PO process and share the expected PO date and delivery schedule.",
              "", "Thank you for your kind support.", "", "Best regards,", sender, f"{role}, {fac_label}",
              f"Date: {datetime.now().strftime(DATE_FMT)}"]
    return "\n".join(lines)


@tx
def set_audit_qty(rid, new_q, old_q, name, req_no):
    run("UPDATE requisition_tracking SET audit_approved_qty=%s WHERE id=%s", (new_q, rid))
    audit("EDIT_AUDIT_APPROVED", f"Req {req_no} / {name}: approved {old_q:g} -> {new_q:g}")
    return True


@tx
def set_po_receiving(rid, po_s, rec_q, rec_s, req_no, name):
    run("UPDATE requisition_tracking SET po_date=%s, actual_received_qty=%s, received_date=%s WHERE id=%s",
        (po_s, rec_q, rec_s, rid))
    audit("UPDATE_REQ_TRACKING", f"Req {req_no} / {name}: PO={po_s}, received={rec_q:g}")
    return True


@tx
def edit_requisition(rid, req_no, dept, req_date, req_qty, item, code, old_code):
    if code and code != old_code:
        if q("SELECT item_name FROM inventory WHERE factory_name=%s AND prod_id=%s", (FAC, code)):
            st.error(f"ERP Code '{code}' already used in {FAC}.")
            return False
        run("UPDATE inventory SET prod_id=%s WHERE factory_name=%s AND prod_id=%s", (code, FAC, old_code))
        run("UPDATE transactions SET prod_id=%s WHERE factory_name=%s AND prod_id=%s", (code, FAC, old_code))
    run("""UPDATE requisition_tracking SET req_no=%s, department=%s, req_date=%s, req_qty=%s, item_name=%s, prod_id=%s
           WHERE id=%s""", (req_no, dept, req_date, req_qty, item, code or old_code, rid))
    audit("EDIT_REQUISITION", f"Req ID {rid}: {req_no} / {item}")
    return True


@tx
def delete_requisition(rid, req_no, name):
    run("DELETE FROM requisition_tracking WHERE id=%s", (rid,))
    audit("DELETE_REQUISITION", f"Deleted requisition {req_no} - {name}")
    return True


def tab_requisition():
    with st.expander("📥 Import requisition (Excel / CSV)"):
        if guard():
            req_import_view()

    rows = load_requisitions()
    term = st.text_input("🔍 Search by Requisition No", key="req_search")
    if term.strip():
        rows = [r for r in rows if term.strip().lower() in str(r["req_no"]).lower()]
    total_pending = sum(r["pending"] for r in rows)
    st.caption(f"Requisitions: {len(rows)} | Fully Received: {sum(r['calc_status'] == 'Fully Received' for r in rows)} | "
               f"Awaiting PO: {sum(not r['has_po'] and r['aud_qty'] > 0 for r in rows)} | Pending Qty: {total_pending:,.2f}")
    if not rows:
        st.info("Requisition nei.")
        return
    df = pd.DataFrame([{"ID": r["id"], "Factory": r["factory_name"], "Req No": r["req_no"], "Department": r["department"],
                        "Req Date": r["req_date"], "Item": r["item_name"], "ERP Code": r["prod_id"], "Req Qty": r["req_qty"],
                        "Audit Approved": r["aud_qty"], "Received": r["rec_qty"], "Pending": r["pending"],
                        "PO Date": r["po_date"] or "Pending PO", "Status": r["calc_status"],
                        "Delay (days)": r["delay"]} for r in rows])

    def hl(row):
        late = (row["PO Date"] == "Pending PO") and row["Delay (days)"] > PO_ALERT_DAYS and row["Audit Approved"] > 0
        color = ("#e8f5e9" if row["Status"] == "Fully Received" else
                 "#fff8e1" if row["Status"] == "Partially Received" else
                 "#fde8e8" if late else "")
        return [f"background-color:{color}" if color else "" for _ in row]

    st.dataframe(df.style.apply(hl, axis=1), hide_index=True, use_container_width=True)
    export_buttons(df, "requisition_tracking")

    labels = {f"ID {r['id']} | {r['req_no']} | {r['item_name']}": r for r in rows}
    r = labels[st.selectbox("Select requisition", list(labels), key="req_sel")]
    k = str(r["id"])
    t1, t2, t3, t4 = st.tabs(["✔️ Audit Approved Qty (Executive)", "🚚 PO / Receiving", "✏️ Edit", "📧 Sourcing Email"])
    with t1:
        if st.session_state.get("role") != "Executive":
            st.caption("Audit Approved Qty shudhu Executive (Mr. Sattar) change korte parben.")
        else:
            nq = st.number_input("Audit approved qty", 0.0, float(r["req_qty"]), float(r["aud_qty"]), key=f"aud_{k}")
            if st.button("Save approved qty", key=f"aud_btn_{k}") and guard():
                if set_audit_qty(r["id"], nq, r["aud_qty"], r["item_name"], r["req_no"]):
                    done("Audit approved qty updated.")
    with t2:
        if guard():
            has_po = st.checkbox("HO PO issued", value=r["has_po"], key=f"hp_{k}")
            po_d = st.date_input("HO PO Date", value=parse_date(r["po_date"]).date() if parse_date(r["po_date"]) else date.today(), key=f"pod_{k}")
            rq = st.number_input("Total received qty so far", 0.0, step=1.0, value=float(r["rec_qty"]), key=f"rq_{k}")
            rd = st.date_input("Last received date", value=parse_date(r["received_date"]).date() if parse_date(r["received_date"]) else date.today(), key=f"rd_{k}")
            if st.button("Save PO / receiving", key=f"po_btn_{k}"):
                if set_po_receiving(r["id"], po_d.strftime(DATE_FMT) if has_po else None, rq,
                                    rd.strftime(DATE_FMT) if rq > 0 else None, r["req_no"], r["item_name"]):
                    done("PO / receiving updated.")
    with t3:
        if guard():
            with st.form(f"req_edit_{k}"):
                c1, c2, c3 = st.columns(3)
                no = c1.text_input("Requisition No", r["req_no"] or "", key=f"rn_{k}")
                dept = c2.selectbox("Department", DEPARTMENTS,
                                    index=DEPARTMENTS.index(r["department"]) if r["department"] in DEPARTMENTS else 0, key=f"rdp_{k}")
                rdate = c3.text_input("Req Date (DD-Mon-YYYY)", r["req_date"] or "", key=f"rdt_{k}")
                qty = c1.number_input("Req Qty", min_value=0.0, value=float(r["req_qty"]), key=f"rqty_{k}")
                item = c2.text_input("Item", r["item_name"] or "", key=f"ri_{k}")
                code = c3.text_input("ERP Code", r["prod_id"] or "", key=f"rc_{k}")
                if st.form_submit_button("💾 Save"):
                    d = parse_date(rdate)
                    if not d or qty <= 0 or not item.strip():
                        st.error("Req date (DD-Mon-YYYY), Qty ar Item thik kore din.")
                    elif edit_requisition(r["id"], no.strip(), dept, d.strftime(DATE_FMT), qty, item.strip(), code.strip(), r["prod_id"]):
                        done("Requisition updated.")
            pw = mgr_check(f"req_pw_{k}")
            if st.button("🗑 Delete requisition", key=f"req_del_{k}"):
                if not pw:
                    st.error("Manager password din.")
                elif delete_requisition(r["id"], r["req_no"], r["item_name"]):
                    done("Requisition deleted.")
    with t4:
        sel = st.multiselect("Items (blank = sob pending)", list(labels), key="mail_sel")
        pool = [labels[s] for s in sel] if sel else rows
        fac_label = FAC if "CONSOLIDATED" not in FAC else " & ".join(FACTORIES)
        body = sourcing_email(pool, fac_label, st.session_state.get("user", ""), st.session_state.get("role", ""))
        if not body:
            st.info("PO-pending / delivery-pending item nei.")
        else:
            st.text_area("Email body", body, height=380, key="mail_body")
            st.download_button("💾 Download .txt", body, "Sourcing_Email.txt", "text/plain")


# ============================================================
#  TAB 7 - REPAIR & RETURNS
# ============================================================
@tx
def add_repair(fac, d):
    run("""INSERT INTO repair_returns (factory_name, tracking_code, gate_pass_no, item_name, qty, source_type, return_type,
           supplier_name, sent_date, return_date, status, remarks, officer_name)
           VALUES (%s,'TMP',%s,%s,%s,%s,%s,%s,%s,%s,%s,'',%s)""",
        (fac, d["gate"], d["item"], d["qty"], d["stype"], d["rtype"], d["supplier"], d["sent"], d["ret"], d["status"],
         st.session_state.get("user", "")))
    new_id = run("SELECT MAX(id) FROM repair_returns WHERE factory_name=%s AND tracking_code='TMP'", (fac,))[0][0]
    tracking = d["track"] or f"REP-{new_id:04d}"
    run("UPDATE repair_returns SET tracking_code=%s WHERE id=%s", (tracking, new_id))
    audit("ADD_REPAIR", f"{tracking} ({d['item']}, qty {d['qty']:g}) for {fac}")
    return tracking


@tx
def update_repair(rid, d):
    run("""UPDATE repair_returns SET gate_pass_no=%s, item_name=%s, qty=%s, source_type=%s, return_type=%s,
           supplier_name=%s, sent_date=%s, return_date=%s, status=%s WHERE id=%s""",
        (d["gate"], d["item"], d["qty"], d["stype"], d["rtype"], d["supplier"], d["sent"], d["ret"], d["status"], rid))
    audit("EDIT_REPAIR", f"Edited repair record {rid}")
    return True


@tx
def delete_repair(rid):
    run("DELETE FROM repair_returns WHERE id=%s", (rid,))
    audit("DELETE_REPAIR", f"Deleted repair record {rid}")
    return True


def tab_repair():
    rp = qdf(f"""SELECT id, tracking_code, factory_name, gate_pass_no, item_name, COALESCE(qty,0) AS qty, source_type,
                 return_type, supplier_name, sent_date, return_date, status, officer_name
                 FROM repair_returns WHERE 1=1{FSQL} ORDER BY id DESC""", FP)
    term = st.text_input("🔍 Search (Item / Gate Pass / Supplier / Tracking)", key="rp_search")
    if term and not rp.empty:
        m = rp[["item_name", "gate_pass_no", "supplier_name", "tracking_code"]].astype(str).apply(
            lambda c: c.str.contains(term, case=False, regex=False)).any(axis=1)
        rp = rp[m]
    if not rp.empty:
        rp["aging_days"] = rp.apply(lambda r: age_days(r["sent_date"], r["return_date"]), axis=1)
    st.dataframe(rp, hide_index=True, use_container_width=True)
    export_buttons(rp, "repair_returns")

    if not guard():
        return
    with st.expander("➕ Add repair / return"):
        with st.form("rp_add"):
            c1, c2, c3 = st.columns(3)
            gate = c1.text_input("Gate Pass No*")
            track = c2.text_input("Tracking Code (blank = auto REP-xxxx)")
            rtype = c3.selectbox("Return Type", ["Returnable", "Non-Returnable"])
            item = c1.text_input("Item Description*")
            qty = c2.number_input("Qty*", min_value=0.0, step=1.0)
            stype = c3.selectbox("Type", ["Repair", "Warranty Claim", "Rejected Return", "Other"])
            supplier = c1.text_input("Supplier Name*")
            sent = c2.date_input("Sent Date", value=date.today())
            status = c3.selectbox("Status", ["Pending Return", "Returned", "Closed"])
            ret = c2.date_input("Return Date (if returned)", value=date.today())
            if st.form_submit_button("Add"):
                if not gate or not item or not supplier or qty <= 0:
                    st.error("Gate Pass, Item, Supplier ar Qty (>0) lagbe.")
                else:
                    d = dict(gate=gate.strip(), track=track.strip(), item=item.strip(), qty=qty, stype=stype, rtype=rtype,
                             supplier=supplier.strip(), sent=sent.strftime(DATE_FMT),
                             ret=ret.strftime(DATE_FMT) if status != "Pending Return" else None, status=status)
                    tr = add_repair(FAC, d)
                    if tr:
                        done(f"Item added. Tracking Code: {tr}")

    if not rp.empty:
        with st.expander("✏️ Update / 🗑 Delete record"):
            labels = {f"ID {r['id']} | {r['tracking_code']} | {r['item_name']} | {r['status']}": r for r in rp.to_dict("records")}
            r = labels[st.selectbox("Record", list(labels), key="rp_sel")]
            k = str(r["id"])
            with st.form(f"rp_edit_{k}"):
                c1, c2, c3 = st.columns(3)
                gate = c1.text_input("Gate Pass No", r["gate_pass_no"] or "", key=f"rg_{k}")
                item = c2.text_input("Item", r["item_name"] or "", key=f"ri_{k}")
                qty = c3.number_input("Qty", min_value=0.0, value=float(r["qty"] or 0), key=f"rq_{k}")
                stype = c1.selectbox("Type", ["Repair", "Warranty Claim", "Rejected Return", "Other"], key=f"rs_{k}")
                rtype = c2.selectbox("Return Type", ["Returnable", "Non-Returnable"], key=f"rt_{k}")
                supplier = c3.text_input("Supplier", r["supplier_name"] or "", key=f"rsu_{k}")
                sent = c1.text_input("Sent Date (DD-Mon-YYYY)", r["sent_date"] or "", key=f"rse_{k}")
                status = c2.selectbox("Status", ["Pending Return", "Returned", "Closed"], key=f"rst_{k}")
                ret = c3.text_input("Return Date (blank = not returned)", r["return_date"] or "", key=f"rre_{k}")
                upd = st.form_submit_button("✏️ Update")
            if upd:
                if not parse_date(sent):
                    st.error("Sent date DD-Mon-YYYY format-e hote hobe.")
                elif update_repair(r["id"], dict(gate=gate, item=item, qty=qty, stype=stype, rtype=rtype, supplier=supplier,
                                                 sent=sent, ret=ret or None, status=status)):
                    done("Record updated.")
            if st.button("🗑 Delete record", key=f"rdel_{k}"):
                if delete_repair(r["id"]):
                    done("Record deleted.")


# ============================================================
#  TAB 8 - LEDGER
# ============================================================
def tab_ledger():
    led = qdf(f"""SELECT t.factory_name, t.officer_name, t.sl_no, t.prod_id, t.item_name, t.qty, t.trans_type, t.notes,
                  t.date, t.time, COALESCE(i.unit_price,0) AS unit_price
                  FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                  WHERE 1=1{fw(FAC, 't.')[0]} ORDER BY t.id DESC""", FP)
    if not led.empty:
        led["type"] = led.trans_type.map(lambda c: TRANS_LABELS.get(c, c))
        led["total_price"] = (led.qty * led.unit_price).round(2)
        led["date_time"] = led[["date", "time"]].fillna("").agg(" ".join, axis=1)
        led = led[["factory_name", "officer_name", "sl_no", "prod_id", "item_name", "qty", "type",
                   "total_price", "notes", "date_time"]]
    st.dataframe(led, hide_index=True, use_container_width=True)
    export_buttons(led, "ledger")


# ============================================================
#  TAB 9 - FORECAST
# ============================================================
def month_info(now=None):
    now = now or datetime.now()
    cy, cm = now.year, now.month
    ny, nm = (cy + 1, 1) if cm == 12 else (cy, cm + 1)
    return {"now": now, "cur_key": f"{cy}-{cm:02d}", "next_key": f"{ny}-{nm:02d}",
            "cur_label": f"{calendar.month_abbr[cm]}-{cy}", "next_label": f"{calendar.month_abbr[nm]}-{ny}",
            "next_days": calendar.monthrange(ny, nm)[1]}


@tx
def save_plans(fac, cur_q, next_q, note, mi):
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = st.session_state.get("user", "")
    for key, qty in ((mi["cur_key"], cur_q), (mi["next_key"], next_q)):
        run("""INSERT INTO production_plans (factory_name, plan_month, plan_qty, plan_note, updated_by, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (factory_name, plan_month)
               DO UPDATE SET plan_qty=EXCLUDED.plan_qty, plan_note=EXCLUDED.plan_note,
               updated_by=EXCLUDED.updated_by, updated_at=EXCLUDED.updated_at""",
            (fac, key, qty, note, user, now_s))
    audit("SAVE_PROD_PLAN", f"{fac}: {mi['cur_label']}={cur_q:g}, {mi['next_label']}={next_q:g}. {note}")
    return True


def compute_forecast(mi):
    now = mi["now"]
    cy, cm = now.year, now.month
    sy, sm = (cy, cm - 3) if cm > 3 else (cy - 1, cm + 9)
    l3_start, cur_start = datetime(sy, sm, 1), datetime(cy, cm, 1)
    l3_days = max((cur_start - l3_start).days, 1)
    cur_c, l3_c = {}, {}
    for t in q(f"SELECT factory_name, sl_no, qty, date FROM transactions WHERE trans_type IN ('Issued','Internal Issue'){FSQL}", FP):
        dt = parse_date(t["date"])
        if not dt:
            continue
        k = (t["factory_name"], t["sl_no"])
        if dt.year == cy and dt.month == cm:
            cur_c[k] = cur_c.get(k, 0) + float(t["qty"] or 0)
        elif l3_start <= dt < cur_start:
            l3_c[k] = l3_c.get(k, 0) + float(t["qty"] or 0)
    plans = {(p["factory_name"], p["plan_month"]): float(p["plan_qty"] or 0)
             for p in q("SELECT factory_name, plan_month, plan_qty FROM production_plans")}
    out = []
    for r in q(f"""SELECT factory_name, sl_no, prod_id, item_name, COALESCE(current_stock,0) AS stock,
                   COALESCE(unit_price,0) AS price FROM inventory WHERE 1=1{FSQL}""", FP):
        k = (r["factory_name"], r["sl_no"])
        cur_p = plans.get((r["factory_name"], mi["cur_key"]), 0)
        nxt_p = plans.get((r["factory_name"], mi["next_key"]), 0)
        factor = nxt_p / cur_p if cur_p > 0 and nxt_p > 0 else 1.0
        avg = l3_c.get(k, 0) / l3_days
        proj = avg * mi["next_days"] * factor
        net_raw = proj - float(r["stock"])
        net = math.ceil(net_raw - 1e-9) if net_raw > 0 else 0
        out.append({"Factory": r["factory_name"], "SL": r["sl_no"], "ERP Code": r["prod_id"], "Item": r["item_name"],
                    "Current Stock": round(float(r["stock"]), 2), "Current Month Cons.": round(cur_c.get(k, 0), 2),
                    "Last 3M Cons.": round(l3_c.get(k, 0), 2), "Avg Daily": round(avg, 3),
                    "Next Month Projected": round(proj, 2), "Factor": round(factor, 2),
                    "Net Requisition": net, "Unit Price": float(r["price"]),
                    "Est. Cost": round(net * float(r["price"]), 2)})
    return pd.DataFrame(out)


def tab_forecast():
    mi = month_info()
    st.markdown(f"#### 🏭 Production Plan   |   Current: **{mi['cur_label']}**   |   Next: **{mi['next_label']}**")
    plans = {(p["factory_name"], p["plan_month"]): p for p in q("SELECT * FROM production_plans")}
    if FAC and "CONSOLIDATED" not in FAC:
        cp = plans.get((FAC, mi["cur_key"]), {})
        npn = plans.get((FAC, mi["next_key"]), {})
        c1, c2, c3 = st.columns([1, 1, 2])
        cur_q = c1.number_input("Current month plan (pcs)", min_value=0.0, step=100.0,
                                value=float(cp.get("plan_qty") or 0), key="fc_cur")
        next_q = c2.number_input("Next month plan (pcs)", min_value=0.0, step=100.0,
                                 value=float(npn.get("plan_qty") or 0), key="fc_next")
        note = c3.text_input("Plan remarks (e.g. Denim Pant)", (npn.get("plan_note") or cp.get("plan_note") or ""), key="fc_note")
        if cur_q > 0 and next_q > 0:
            f = next_q / cur_q
            st.info(f"Production Factor = {next_q:,.0f} ÷ {cur_q:,.0f} = **{f:.2f}x**  "
                    f"({'higher' if f > 1 else 'lower' if f < 1 else 'same'} consumption expected)")
        else:
            st.info("Production Factor = 1.00x (current ar next dui month-er plan dile factor apply hobe).")
        if st.button("💾 Save plan & recalculate", key="fc_save") and guard():
            if save_plans(FAC, cur_q, next_q, note, mi):
                done("Production plan saved.")
    else:
        st.info("Consolidated view-te read-only. Plan edit korte specific factory select korun.")

    fc = compute_forecast(mi)
    only = st.checkbox("Only items with consumption (this month / last 3 months)", value=True, key="fc_only")
    term = st.text_input("🔍 Item name / ERP code", key="fc_search")
    if only and not fc.empty:
        fc = fc[(fc["Current Month Cons."] > 0) | (fc["Last 3M Cons."] > 0)]
    if term and not fc.empty:
        t_low = term.lower()
        fc = fc[fc["Item"].str.lower().str.contains(t_low, regex=False)
                | fc["ERP Code"].astype(str).str.lower().str.contains(t_low, regex=False)]
    if not fc.empty:
        fc = fc.sort_values("Est. Cost", ascending=False)
        st.caption(f"Items: {len(fc)} | Need requisition: {int((fc['Net Requisition'] > 0).sum())} | "
                   f"Total net qty: {fc['Net Requisition'].sum():,.0f} | Est. cost: {fc['Est. Cost'].sum():,.2f} BDT")
    st.dataframe(fc, hide_index=True, use_container_width=True)
    export_buttons(fc, "forecast")
    st.caption("Formula: Avg Daily = Last 3M consumption ÷ days  |  Projected = Avg Daily × days in next month × Factor  |  "
               "Net Requisition = Projected − Stock (rounded up)  |  Est. Cost = Net × Unit Price")


# ============================================================
#  TAB 10 - BUDGET
# ============================================================
def tab_budget():
    bud = qdf(f"SELECT factory_name, department_name, category_name, allocated_budget FROM category_budgets WHERE 1=1{FSQL}", FP)
    cost_rows = q(f"""SELECT t.factory_name, i.category, SUM(t.qty*i.unit_price) AS cost
                      FROM transactions t JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                      WHERE t.trans_type IN ('Issued','Internal Issue'){fw(FAC, 't.')[0]}
                      GROUP BY t.factory_name, i.category""", FP)
    cost = {(r["factory_name"], r["category"]): float(r["cost"] or 0) for r in cost_rows}
    if bud.empty:
        st.info("Budget nei.")
        return
    bud["actual_cost"] = [cost.get((f, c), 0.0) for f, c in zip(bud.factory_name, bud.category_name)]
    bud["remaining"] = bud.allocated_budget - bud.actual_cost
    bud["status"] = bud.remaining.apply(lambda v: "SAFE" if v >= 0 else "OVER BUDGET")
    total_b, total_c = bud.allocated_budget.sum(), bud.actual_cost.sum()
    c = st.columns(4)
    c[0].metric("Total Budget", f"{total_b:,.2f}")
    c[1].metric("Consumption", f"{total_c:,.2f}")
    c[2].metric("Remaining", f"{total_b - total_c:,.2f}")
    c[3].metric("Utilization", f"{(total_c / total_b * 100 if total_b else 0):.1f}%")
    st.dataframe(bud, hide_index=True, use_container_width=True)
    export_buttons(bud, "budget")


# ============================================================
#  TAB 11 - DAILY WORK SHEET
# ============================================================
def guess_uom(name, stock):
    n = " " + str(name or "").lower()
    if "filter" not in n and any(k in n for k in DS_KG_KEYWORDS):
        return "Kg"
    try:
        if stock is not None and abs(float(stock) - round(float(stock))) > 1e-9:
            return "Kg"
    except (TypeError, ValueError):
        pass
    return "Pcs"


def autoset_uom_once():
    if q("SELECT 1 AS x FROM req_settings WHERE setting_key='uom_autoset_v1' AND setting_value='done'"):
        return

    @tx
    def _do():
        for r in q("""SELECT sl_no, factory_name, item_name, COALESCE(current_stock,0) AS stock,
                      COALESCE(NULLIF(unit_name,''),'Pcs') AS unit FROM inventory"""):
            if r["unit"] == "Pcs" and guess_uom(r["item_name"], r["stock"]) == "Kg":
                run("UPDATE inventory SET unit_name='Kg' WHERE sl_no=%s AND factory_name=%s", (r["sl_no"], r["factory_name"]))
        run("""INSERT INTO req_settings (setting_key, setting_value) VALUES ('uom_autoset_v1','done')
               ON CONFLICT (setting_key) DO UPDATE SET setting_value='done'""")
        return True
    _do()


def daily_rows(d, fac, show_all):
    ds = d.strftime(DATE_FMT)
    rows = q("""SELECT i.sl_no, i.item_name, COALESCE(i.size,'') AS size, COALESCE(NULLIF(i.unit_name,''),'Pcs') AS unit,
                COALESCE(i.current_stock,0) AS cur, COALESCE(i.erp_stock,0) AS erp,
                COALESCE((SELECT SUM(t.qty) FROM transactions t WHERE t.factory_name=i.factory_name AND t.sl_no=i.sl_no
                          AND t.date=%s AND t.trans_type IN ('Issued','Internal Issue')),0) AS issue,
                COALESCE((SELECT SUM(t.qty) FROM transactions t WHERE t.factory_name=i.factory_name AND t.sl_no=i.sl_no
                          AND t.date=%s AND t.trans_type IN ('Supplier. Rec','Internal Rec')),0) AS recv
                FROM inventory i WHERE i.factory_name=%s ORDER BY i.sl_no""", (ds, ds, fac))
    out = []
    for r in rows:
        cur, erp = float(r["cur"]), float(r["erp"])
        diff = round(cur - erp, 4)
        short, exc = (abs(diff) if diff < 0 else 0.0), (diff if diff > 0 else 0.0)
        if not show_all and abs(cur) < 1e-9 and short == 0 and exc == 0 and float(r["issue"]) <= 0 and float(r["recv"]) <= 0:
            continue
        out.append({"SL No.": r["sl_no"], "Item Name": r["item_name"], "Size": r["size"], "Unit": r["unit"],
                    "Current Stock": cur, "Daily Issue": float(r["issue"]), "Daily Received": float(r["recv"]),
                    "Short Qty": short, "Excess Qty": exc})
    return pd.DataFrame(out)


@tx
def set_uom(fac, sl, name, unit, same_name):
    if same_name:
        run("UPDATE inventory SET unit_name=%s WHERE LOWER(TRIM(item_name))=LOWER(TRIM(%s))", (unit, name))
    else:
        run("UPDATE inventory SET unit_name=%s WHERE sl_no=%s AND factory_name=%s", (unit, sl, fac))
    audit("EDIT_UOM", f"{name}: UOM -> {unit}")
    return True


def sheet_html(d, fac, df, auto):
    esc = html_lib.escape
    body = ""
    for _, r in df.iterrows():
        cls = "short" if r["Short Qty"] > 0 else ("excess" if r["Excess Qty"] > 0 else "")
        issue_txt = f"{r['Daily Issue']:g}" if auto else ""
        recv_txt = f"{r['Daily Received']:g}" if auto else ""
        body += (f"<tr class='{cls}'><td>{r['SL No.']}</td>"
                 f"<td style='text-align:left'>{esc(str(r['Item Name']))}</td>"
                 f"<td>{esc(str(r['Size'] or '-'))}</td><td>{esc(str(r['Unit']))}</td>"
                 f"<td>{r['Current Stock']:g}</td><td>{issue_txt}</td><td>{recv_txt}</td>"
                 f"<td>{r['Short Qty']:g}</td><td>{r['Excess Qty']:g}</td></tr>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Daily Work Sheet</title>
<style>@page {{ size: A4 portrait; margin: 10mm; }} body {{ font-family: Arial; font-size: 11px; }}
h2 {{ text-align:center; color:#1b3b6f; margin:0; }} p {{ text-align:center; margin:4px 0 10px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ background:#1b3b6f; color:#fff; padding:4px; border:1px solid #333; }}
td {{ border:1px solid #333; padding:3px 4px; text-align:center; }}
tr.short td {{ background:#fde8e8; }} tr.excess td {{ background:#fff3e0; }}</style></head><body>
<h2>Daily Issue Status For Month: {d.strftime('%B-%Y')}</h2>
<p><b>Date:</b> {d.strftime(DATE_FMT)} &nbsp; <b>Factory Name:</b> {esc(fac)}</p>
<table><thead><tr><th>SL No.</th><th>Item Name</th><th>Size</th><th>Unit</th><th>Current Stock</th>
<th>Daily Issue</th><th>Daily Received</th><th>Short Qty</th><th>Excess Qty</th></tr></thead>
<tbody>{body}</tbody></table>
</body></html>"""


def tab_daily_sheet():
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
    d = c1.date_input("Date", value=date.today(), key="ds_date")
    fac = c2.selectbox("Factory", FACTORIES, index=FACTORIES.index(FAC) if FAC in FACTORIES else 0, key="ds_fac")
    show_all = c3.checkbox("Include zero-stock", key="ds_all")
    auto = c4.checkbox("Auto-fill issue/received", key="ds_auto")
    df = daily_rows(d, fac, show_all)
    st.markdown(f"### Daily Issue Status For Month: {d.strftime('%B-%Y')}")
    n_short = int((df["Short Qty"] > 0).sum()) if not df.empty else 0
    n_exc = int((df["Excess Qty"] > 0).sum()) if not df.empty else 0
    st.caption(f"Date: {d.strftime(DATE_FMT)} | Factory: {fac} | SL No = Master Inventory SL (same as Transactions). "
               f"Items: {len(df)} | Short: {n_short} | Excess: {n_exc}")
    view = df.copy()
    if not auto and not view.empty:
        view["Daily Issue"] = None
        view["Daily Received"] = None
    st.dataframe(view, hide_index=True, use_container_width=True)
    st.download_button("🖨️ Download print sheet (HTML → open & Print)", sheet_html(d, fac, df, auto),
                       f"Daily_Work_Sheet_{d:%Y%m%d}.html", "text/html")
    with st.expander("✏️ Edit UOM"):
        if guard():
            opts = inv_options(fac)
            if opts:
                r = opts[st.selectbox("Item", list(opts), key="uom_item")]
                unit = st.selectbox("UOM", UOM, index=UOM.index(r["unit_name"]) if r["unit_name"] in UOM else 0, key="uom_val")
                same = st.checkbox("Apply to every item with this name (both factories)", value=True, key="uom_same")
                if st.button("Save UOM", key="uom_btn"):
                    if set_uom(fac, r["sl_no"], r["item_name"], unit, same):
                        done("UOM updated.")


# ============================================================
#  MAIN
# ============================================================
try:
    init_db()
except Exception as e:
    st.error(f"Cloud database-e connect kora jacche na: {e}")
    st.stop()

show_flash()
sidebar_login()

with st.sidebar:
    st.markdown("### 🏭 Factory")
    FAC = st.selectbox("Active factory", FACTORIES + [ALL_VIEW], key="factory", label_visibility="collapsed")
    st.markdown("---")
    st.caption("📌 CONSOLIDATED view shudhu dekhar jonno. Entry-r jonno specific factory bachun.")

FSQL, FP = fw(FAC)
is_cons_view = "CONSOLIDATED" in FAC
autoset_uom_once()

st.markdown(f"""
<div class="app-header">
    <h1>KC &amp; WINDY SMART STOCK TRACKER &amp; BUDGET CONTROL</h1>
    <p>Designed &amp; Created By: MD. Sagor Ali</p>
</div>
<div class="factory-bar">🏭 Active View: {html_lib.escape(FAC)}</div>
""", unsafe_allow_html=True)

try:
    kpi = q(f"""SELECT COUNT(*) AS items,
                       COALESCE(SUM(COALESCE(current_stock,0)*COALESCE(unit_price,0)),0) AS stock_value,
                       SUM(CASE WHEN current_stock <= 5 THEN 1 ELSE 0 END) AS alerts
                FROM inventory WHERE 1=1{FSQL}""", FP)[0]
    bud = q(f"SELECT COALESCE(SUM(allocated_budget),0) AS b FROM category_budgets WHERE 1=1{FSQL}", FP)[0]["b"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("TOTAL ITEMS", int(kpi["items"] or 0))
    c2.metric("STOCK VALUE (BDT)", f"{float(kpi['stock_value']):,.0f}")
    c3.metric("ALLOCATED BUDGET (BDT)", f"{float(bud):,.0f}")
    c4.metric("LOW / NEGATIVE STOCK", int(kpi["alerts"] or 0))
except Exception as e:
    st.warning(f"Summary load kora jacche na: {e}")

TAB_NAMES = ["[1] TRANSACTIONS", "[2] INVENTORY", "[3] ERP AUDIT", "[4] ISSUE LEDGER", "[5] TRANSFER HISTORY",
             "[6] REQUISITION", "[7] REPAIR", "[8] LEDGER", "[9] FORECAST", "[10] BUDGET", "[11] DAILY WORK SHEET"]
RENDERERS = [tab_transactions, tab_inventory, tab_erp_audit, tab_issue_ledger, tab_transfer_history,
             tab_requisition, tab_repair, tab_ledger, tab_forecast, tab_budget, tab_daily_sheet]
tabs = st.tabs(TAB_NAMES)
for t, fn in zip(tabs, RENDERERS):
    with t:
        fn()
