from datetime import datetime
import calendar
import difflib
import hashlib
import html as html_lib
import math
import os
import re
import shutil
import tempfile
import tkinter as tk
import urllib.parse
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
import pandas as pd

import psycopg2  # Cloud database er sathe connect korar jonno

DB_URL = os.environ.get("WINDY_DB_URL") or "postgresql://postgres:FQauoo9dk4Rsc2Vi@db.lersqtzjxfuzslnhtpjg.supabase.co:5432/postgres"

try:
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cursor = conn.cursor()
except Exception as e:
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror("Database Connection Error", f"Cloud Database-e connect kora sombhob hoyni:\n{e}")
    exit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS inventory (
        sl_no INTEGER,
        prod_id TEXT,
        factory_name TEXT,
        item_name TEXT,
        department TEXT,
        category TEXT,
        erp_stock REAL DEFAULT 0,
        current_stock REAL DEFAULT 0,
        unit_price REAL DEFAULT 0,
        erp_status TEXT DEFAULT 'ERP Pending'
    )
""")

try:
    cursor.execute("SELECT erp_status FROM inventory LIMIT 1")
except Exception:
    conn.rollback()
    cursor.execute("ALTER TABLE inventory ADD COLUMN IF NOT EXISTS erp_status TEXT DEFAULT 'ERP Pending'")
    conn.commit()

try:
    cursor.execute("SELECT unit_name FROM inventory LIMIT 1")
except Exception:
    conn.rollback()
    cursor.execute("ALTER TABLE inventory ADD COLUMN IF NOT EXISTS unit_name TEXT DEFAULT ''")
    conn.commit()

try:
    cursor.execute("SELECT unit_name FROM inventory LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE inventory ADD COLUMN unit_name TEXT DEFAULT 'Pcs'")
    conn.commit()

# product size (mandatory for new items). Existing rows keep blank size until edited.
try:
    cursor.execute("SELECT size FROM inventory LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE inventory ADD COLUMN size TEXT DEFAULT ''")
    conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        officer_name TEXT,
        sl_no INTEGER,
        prod_id TEXT,
        item_name TEXT,
        qty REAL,
        trans_type TEXT,
        day INTEGER,
        notes TEXT,
        date TEXT,
        time TEXT,
        verification_status TEXT DEFAULT 'N/A'
    )
""")

# ERP GRN / PO gap tracking columns (existing data is kept)
try:
    cursor.execute("SELECT erp_grn_status FROM transactions LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE transactions ADD COLUMN erp_grn_status TEXT DEFAULT 'Not Required'")
    cursor.execute("ALTER TABLE transactions ADD COLUMN erp_grn_date TEXT")
    cursor.execute("UPDATE transactions SET erp_grn_status='Pending' WHERE trans_type='Supplier. Rec' AND notes ILIKE '%Pending%'")
    conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS inter_factory_transfers (
        id SERIAL PRIMARY KEY,
        transfer_ref TEXT UNIQUE,
        source_factory TEXT,
        dest_factory TEXT,
        prod_id TEXT,
        item_name TEXT,
        qty REAL,
        transfer_date TEXT,
        transfer_time TEXT,
        initiated_by TEXT,
        status TEXT DEFAULT 'Completed',
        notes TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_correction_tasks (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        prod_id TEXT,
        item_name TEXT,
        variance_type TEXT,
        variance_qty REAL,
        variance_value REAL,
        root_cause TEXT,
        corrective_action TEXT,
        assigned_officer TEXT,
        task_date TEXT,
        target_date TEXT,
        status TEXT DEFAULT 'Open',
        manager_remarks TEXT,
        priority TEXT DEFAULT 'Medium',
        verification_status TEXT DEFAULT 'Pending'
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS requisition_tracking (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        req_no TEXT,
        department TEXT,
        req_date TEXT,
        item_name TEXT,
        req_qty REAL,
        audit_approved_qty REAL DEFAULT 0,
        actual_received_qty REAL DEFAULT 0,
        po_date TEXT,
        received_date TEXT,
        status TEXT DEFAULT 'Req Created',
        po_delay_days INTEGER DEFAULT 0
    )
""")

try:
    cursor.execute("SELECT audit_approved_qty FROM requisition_tracking LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE requisition_tracking ADD COLUMN audit_approved_qty REAL DEFAULT 0")
    cursor.execute("ALTER TABLE requisition_tracking ADD COLUMN actual_received_qty REAL DEFAULT 0")
    conn.commit()

try:
    cursor.execute("SELECT prod_id FROM requisition_tracking LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE requisition_tracking ADD COLUMN prod_id TEXT DEFAULT ''")
    conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS repair_returns (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        tracking_code TEXT,
        gate_pass_no TEXT,
        item_name TEXT,
        qty REAL,
        source_type TEXT,
        return_type TEXT,
        supplier_name TEXT,
        sent_date TEXT,
        return_date TEXT,
        status TEXT DEFAULT 'Pending Return',
        remarks TEXT
    )
""")

try:
    cursor.execute("SELECT tracking_code FROM repair_returns LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE repair_returns ADD COLUMN tracking_code TEXT DEFAULT 'REP-000'")
    cursor.execute("ALTER TABLE repair_returns ADD COLUMN gate_pass_no TEXT DEFAULT 'GP-000'")
    cursor.execute("ALTER TABLE repair_returns ADD COLUMN return_type TEXT DEFAULT 'Returnable'")
    conn.commit()

try:
    cursor.execute("SELECT officer_name FROM repair_returns LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE repair_returns ADD COLUMN officer_name TEXT DEFAULT 'Officer_Sagor'")
    conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS production_plans (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        plan_month TEXT,
        plan_qty REAL DEFAULT 0,
        plan_note TEXT,
        updated_by TEXT,
        updated_at TEXT,
        UNIQUE(factory_name, plan_month)
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS category_budgets (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        department_name TEXT,
        category_name TEXT,
        allocated_budget REAL DEFAULT 0
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS import_queue (
        id SERIAL PRIMARY KEY,
        factory_name TEXT,
        sl_no INTEGER,
        prod_id TEXT,
        item_name TEXT,
        department TEXT,
        category TEXT,
        erp_stock REAL DEFAULT 0,
        current_stock REAL DEFAULT 0,
        unit_price REAL DEFAULT 0,
        status TEXT DEFAULT 'Pending Approval'
    )
""")

try:
    cursor.execute("SELECT size FROM import_queue LIMIT 1")
except Exception:
    cursor.execute("ALTER TABLE import_queue ADD COLUMN size TEXT DEFAULT ''")
    conn.commit()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT,
        role TEXT,
        full_name TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id SERIAL PRIMARY KEY,
        timestamp TEXT,
        username TEXT,
        action_type TEXT,
        details TEXT
    )
""")

cursor.execute("CREATE TABLE IF NOT EXISTS req_settings (setting_key TEXT PRIMARY KEY, setting_value TEXT)")
conn.commit()
conn.autocommit = False  # schema setup done; from here commit()/rollback() work like they did with SQLite

# ---- NEW: one product = one row (name + size) per factory. Enforced by the database when possible. ----
def _backup_database(folder):
    """Cloud DB backup: every public table is saved as CSV inside <folder>."""
    try:
        os.makedirs(folder, exist_ok=True)
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
        tables = [r[0] for r in cursor.fetchall()]
        for tbl in tables:
            with open(os.path.join(folder, f"{tbl}.csv"), "w", encoding="utf-8", newline="") as f:
                cursor.copy_expert(f'COPY "{tbl}" TO STDOUT WITH CSV HEADER', f)
        return folder
    except Exception:
        conn.rollback()
        raise


DUP_WARNING = ""
try:
    cursor.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_name_size
                      ON inventory(factory_name, lower(replace(replace(item_name,' ',''),'.','')), lower(trim(COALESCE(size,''))))""")
    conn.commit()
except Exception:
    conn.rollback()
    cursor.execute("""SELECT factory_name, COUNT(*) FROM (
                          SELECT factory_name FROM inventory
                          GROUP BY factory_name, lower(replace(replace(item_name,' ',''),'.','')), lower(trim(COALESCE(size,'')))
                          HAVING COUNT(*) > 1) GROUP BY factory_name""")
    _dups = cursor.fetchall()
    if _dups:
        DUP_WARNING = ("Master Inventory-এ একই নাম + সাইজের একাধিক আইটেম পাওয়া গেছে (পুরোনো ডাটায়):\n\n"
                       + "\n".join(f"- {f}: {n} টি গ্রুপ" for f, n in _dups)
                       + "\n\nএগুলো স্বয়ংক্রিয়ভাবে মুছা হয়নি। Edit Selected Item দিয়ে ঠিক করুন।")


# ================= SECURITY HELPERS =================
def hash_password(password):
    salt = os.urandom(32)
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + pwd_hash.hex()


def verify_password(stored_password, provided_password):
    try:
        if ":" not in stored_password:
            # Fallback for legacy plain-text passwords in an existing database
            return stored_password == provided_password
        salt_hex, pwd_hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return pwd_hash.hex() == pwd_hash_hex
    except Exception:
        return False


def verify_manager_password(pwd):
    if pwd is None:
        return False
    cursor.execute("SELECT password FROM users WHERE role='Store Manager'")
    mgr_pw = cursor.fetchone()
    if mgr_pw:
        return verify_password(mgr_pw[0], pwd)
    return pwd == "windy123"


def ask_manager_password(prompt):
    pwd = simpledialog.askstring("Manager Password Required", prompt, show="*")
    return verify_manager_password(pwd)


def _audit(action, details):
    cursor.execute("INSERT INTO audit_logs (timestamp, username, action_type, details) VALUES (%s, %s, %s, %s)",
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_authenticated_user.get() or "SYSTEM", action, details))


# Default users (created only when the users table is empty)
cursor.execute("SELECT COUNT(*) FROM users")
if cursor.fetchone()[0] == 0:
    default_users = [
        ("Officer_Sagor", hash_password("sagor123"), "Store Officer", "Md. Sagor Ali"),
        ("Officer_Rahim", hash_password("rahim123"), "Store Officer", "Abdul Rahim"),
        ("Store_Manager", hash_password("windy123"), "Store Manager", "Manager Admin"),
        ("Auditor_User", hash_password("audit2026"), "Auditor", "External Auditor")
    ]
    cursor.executemany("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s)", default_users)
conn.commit()

cursor.execute("SELECT id FROM users WHERE username=%s", ("Executive_Sattar",))
if not cursor.fetchone():
    cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s)",
                   ("Executive_Sattar", hash_password("sattar123"), "Executive", "Mr. Sattar"))
    conn.commit()

cursor.execute("SELECT COUNT(*) FROM category_budgets")
if cursor.fetchone()[0] == 0:
    default_budgets = [
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
    cursor.executemany("INSERT INTO category_budgets (factory_name, department_name, category_name, allocated_budget) VALUES (%s, %s, %s, %s)", default_budgets)
    conn.commit()

# Transaction type: friendly labels in the UI; original codes stay in the DB (old records and reports keep working)
TRANS_TYPE_LABELS = {
    "Supplier. Rec": "📥 Supplier Receipt",
    "Issued": "📤 Issue to Production",
    "Internal Rec": "🔁 Internal Receipt (from other unit)",
    "Internal Issue": "🔄 Internal Issue (to other unit)",
    "Stock Adjustment (+)": "➕ Stock Adjustment (Increase)",
    "Stock Adjustment (-)": "➖ Stock Adjustment (Decrease)",
}
TRANS_TYPE_CODES = {v: k for k, v in TRANS_TYPE_LABELS.items()}


def _tlabel(code):
    return TRANS_TYPE_LABELS.get(code, code)


# ================= SHARED HELPERS =================
def _num(v, default=None):
    try:
        if v is None or pd.isna(v):
            return default
    except (TypeError, ValueError):
        pass
    t = str(v).replace(",", "").strip()
    if t == "" or t.lower() == "nan":
        return default
    try:
        return float(t)
    except ValueError:
        return default


def _txt(v):
    try:
        if v is None or pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    t = str(v).strip()
    return "" if t.lower() == "nan" else t


def _norm_col(s):
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def _find_col(df, keys):
    """Finds a column by flexible name (ignores case, spaces and underscores)."""
    mapping = {_norm_col(c): c for c in df.columns}
    for k in keys:
        nk = _norm_col(k)
        if nk in mapping:
            return mapping[nk]
    return None


def _norm_size(s):
    """Size key for matching: lower-case letters, digits and dots only."""
    return re.sub(r"[^a-z0-9.]", "", str(s or "").lower())


def _norm_item_name(s):
    """Name key for matching: lower-case letters and digits only (ignores spaces, dots, dashes)."""
    return re.sub(r"[^a-z0-9]", "", str(s or "").lower())


def _other_factory(fac):
    return "Windy Washing LTD" if fac == "KC Washing Plant" else "KC Washing Plant"


def _inv_match(term, *vals):
    """True when the search term is empty or appears in any of the values."""
    if not term:
        return True
    return any(term in str(v).lower() for v in vals)


# ---------- NEW: single, exact item resolver (used by Transactions, Daily Sheet, search) ----------
_INV_COLS = "sl_no, prod_id, factory_name, item_name, COALESCE(size,''), COALESCE(current_stock,0), COALESCE(erp_stock,0), COALESCE(unit_price,0)"


def _inv_query(fac, where, params):
    """Inventory rows matching `where`. fac=None or a CONSOLIDATED label means 'all factories'."""
    sql = f"SELECT {_INV_COLS} FROM inventory WHERE {where}"
    params = list(params)
    if fac and "CONSOLIDATED" not in fac:
        sql += " AND factory_name=%s"
        params.append(fac)
    sql += " ORDER BY factory_name, sl_no"
    cursor.execute(sql, params)
    return cursor.fetchall()


def _resolve_item(fac, key):
    """Finds ONE inventory row for a typed SL No / ERP code / name.
    Priority (exact first, so a number is never confused with a partial name):
      1. SL No (exact)   2. ERP code (exact)   3. item name (exact)   4. partial name / size
    Returns (row, candidates). row = (sl_no, prod_id, factory, item_name, size, stock, erp_stock, price)
    or None when nothing or more than one row matches (candidates then lists the matches)."""
    k = str(key or "").strip()
    if not k:
        return None, []
    stages = []
    if k.isdigit():
        stages.append(("sl_no=%s", [int(k)]))
    stages.append(("LOWER(TRIM(prod_id))=LOWER(%s)", [k]))
    stages.append(("LOWER(TRIM(item_name))=LOWER(%s)", [k]))
    like = f"%{k.lower()}%"
    stages.append(("(LOWER(item_name) ILIKE %s OR LOWER(COALESCE(size,'')) ILIKE %s)", [like, like]))
    for where, params in stages:
        rows = _inv_query(fac, where, params)
        if len(rows) == 1:
            return rows[0], rows
        if len(rows) > 1:
            return None, rows
    return None, []


def _ambiguous_text(rows, limit=12):
    lines = [f"SL {r[0]}  |  {r[2]}  |  {r[3]} [{r[4] or '-'}]  |  Stock {r[5]:g}" for r in rows[:limit]]
    more = f"\n... and {len(rows) - limit} more" if len(rows) > limit else ""
    return "\n".join(lines) + more


def _item_exists(fac, name, size, exclude_sl=None):
    """True if the same product NAME + SIZE already exists in the factory's master."""
    cursor.execute("SELECT sl_no, item_name, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (fac,))
    nn, ns = _norm_item_name(name), _norm_size(size)
    for sl, n, s in cursor.fetchall():
        if exclude_sl is not None and str(sl) == str(exclude_sl):
            continue
        if _norm_item_name(n) == nn and _norm_size(s) == ns:
            return True
    return False


def _find_item_row(fac, name, size):
    """Existing row with the same NAME + SIZE in one factory -> (sl_no, prod_id, current_stock) or None."""
    nn, ns = _norm_item_name(name), _norm_size(size)
    cursor.execute("SELECT sl_no, prod_id, item_name, COALESCE(size,''), COALESCE(current_stock,0) FROM inventory WHERE factory_name=%s", (fac,))
    for sl, code, n, s, stk in cursor.fetchall():
        if _norm_item_name(n) == nn and _norm_size(s) == ns:
            return (sl, code, stk)
    return None


def _next_temp_code(fac):
    """Next free TEMP-#### code for an item whose real ERP code is not known yet."""
    cursor.execute("SELECT prod_id FROM inventory WHERE factory_name=%s", (fac,))
    used = {str(r[0]) for r in cursor.fetchall()}
    n = 1
    while f"TEMP-{n:04d}" in used:
        n += 1
    return f"TEMP-{n:04d}"


def _is_blank_code(code):
    """True when the ERP code cell is empty or a placeholder such as N/A."""
    return str(code or "").strip().upper() in ("", "N/A", "NA", "NONE", "-", "NAN")


def _num_blank0(v):
    """Blank cell -> 0.0 (zero balance). Text that is not a number -> None (row is skipped)."""
    if _txt(v) == "":
        return 0.0
    return _num(v)


def _code_base(prod_id, size):
    """When one ERP code is shared by several sizes the 2nd, 3rd ... size is stored as 'CODE-SIZE'.
    Returns the original ERP code ('' when the stored code is not of that form)."""
    p, s = str(prod_id or "").strip(), str(size or "").strip()
    if s and len(p) > len(s) + 1 and p.lower().endswith("-" + s.lower()):
        return p[:-(len(s) + 1)]
    return ""


def _rq_find_inventory(fac, code, name, size=None):
    """Find an inventory row by ERP code first, then by name (+ size when size is given).
    size=None means 'ignore size'. When a size IS given, a different size of the same ERP code / name is NOT a match.
    Returns (sl_no, prod_id, item_name, erp_stock, current_stock) or None."""
    cols = "sl_no, prod_id, item_name, erp_stock, current_stock"
    ns = _norm_size(size) if size is not None else None
    if code:
        cursor.execute(f"SELECT {cols}, COALESCE(size,'') FROM inventory WHERE factory_name=%s AND (prod_id=%s OR prod_id ILIKE %s) ORDER BY sl_no",
                       (fac, code, code + "-%"))
        rows = [r for r in cursor.fetchall()
                if str(r[1]).lower() == str(code).lower() or _code_base(r[1], r[5]).lower() == str(code).lower()]
        if ns is None:
            if rows:
                nn = _norm_item_name(name)
                for r in rows:
                    if nn and _norm_item_name(r[2]) == nn:
                        return r[:5]
                return rows[0][:5]
        else:
            for r in rows:
                if _norm_size(r[5]) == ns:
                    return r[:5]
    if name:
        cursor.execute(f"SELECT {cols}, COALESCE(size,'') FROM inventory WHERE LOWER(item_name)=LOWER(%s) AND factory_name=%s ORDER BY sl_no", (name.strip(), fac))
        for r in cursor.fetchall():
            if ns is None or _norm_size(r[5]) == ns:
                return r[:5]
    return None


def _item_size(fac, code, name):
    """Size of an inventory item: same code + name first, then same name, then same code.
    (Fixed: an ERP code shared by several sizes no longer returns a random size.)"""
    cursor.execute("SELECT COALESCE(size,'') FROM inventory WHERE factory_name=%s AND prod_id=%s AND LOWER(item_name)=LOWER(%s)", (fac, code, name))
    r = cursor.fetchone()
    if r:
        return r[0]
    cursor.execute("SELECT COALESCE(size,'') FROM inventory WHERE factory_name=%s AND LOWER(item_name)=LOWER(%s)", (fac, name))
    r = cursor.fetchone()
    if r:
        return r[0]
    cursor.execute("SELECT COALESCE(size,'') FROM inventory WHERE factory_name=%s AND prod_id=%s", (fac, code))
    r = cursor.fetchone()
    return r[0] if r else ""


def _mirror_to_other(fac, code, name, size, dept, cat, price):
    """Every product added in one unit is also created in the other unit (stock 0), so both units share the product list.
    Returns True if a copy was created."""
    other = _other_factory(fac)
    cursor.execute("SELECT prod_id, item_name, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (other,))
    rows = cursor.fetchall()
    nn, ns = _norm_item_name(name), _norm_size(size)
    if any(_norm_item_name(r[1]) == nn and _norm_size(r[2]) == ns for r in rows):
        return False
    if not code or any(str(r[0]) == code for r in rows):
        code = _next_temp_code(other)
    sl = _queue_next_sl(other)
    cursor.execute("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category, erp_stock, current_stock, unit_price, erp_status)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, 'ERP Pending')""",
                   (sl, code, other, name, size, dept or "Maintenance", cat or "Uncategorized (Edit Later)", price or 0.0))
    return True


def _find_same_item_in_other_unit(prod_id, item_name, other_fac, size=None):
    """Finds the SAME product in the other factory by NAME + SIZE.
    Order: exact name -> fuzzy name (spelling variation) -> same ERP code.
    size=None means 'ignore size'. Returns (sl_no, prod_id, item_name, current_stock, level) or None.
    level: 'exact' | 'fuzzy' | 'code'."""
    cursor.execute("SELECT sl_no, prod_id, item_name, current_stock, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (other_fac,))
    rows = cursor.fetchall()
    if size is not None:
        ns = _norm_size(size)
        rows = [r for r in rows if _norm_size(r[4]) == ns]
    n = _norm_item_name(item_name)

    exact = [r for r in rows if n and _norm_item_name(r[2]) == n]
    if exact:
        same_code = [r for r in exact if r[1] == prod_id]
        best = max(same_code or exact, key=lambda r: r[3] or 0)
        return best[:4] + ("exact",)

    best_score, best_row = 0.0, None
    if n:
        for r in rows:
            score = difflib.SequenceMatcher(None, n, _norm_item_name(r[2])).ratio()
            if score > best_score:
                best_score, best_row = score, r
    if best_row is not None and best_score >= 0.88:
        return best_row[:4] + ("fuzzy",)

    if prod_id and str(prod_id).strip().upper() not in ("", "N/A", "NA", "NONE"):
        bycode = [r for r in rows if r[1] == prod_id]
        if bycode:
            return bycode[0][:4] + ("code",)
    return None


def _queue_next_sl(fac):
    cursor.execute("SELECT MAX(sl_no) FROM inventory WHERE factory_name=%s", (fac,))
    a = cursor.fetchone()[0] or 0
    cursor.execute("SELECT MAX(sl_no) FROM import_queue WHERE factory_name=%s", (fac,))
    b = cursor.fetchone()[0] or 0
    return max(a, b) + 1


def _queue_add(fac, code, name, dept, cat, erp, phys, price, size=""):
    """Adds an unmatched item to the Unmatch / Import Queue.
    Returns False if the same pending item already exists."""
    # Duplicate = same ERP code AND same size (a real code only), or same name AND same size.
    # (Different sizes of one ERP code, and many rows with code 'N/A', are NOT duplicates.)
    cursor.execute("SELECT prod_id, item_name, COALESCE(size,'') FROM import_queue WHERE factory_name=%s AND status='Pending Approval'", (fac,))
    ns, nn = _norm_size(size), _norm_item_name(name)
    for q_code, q_name, q_size in cursor.fetchall():
        if _norm_size(q_size) != ns:
            continue
        if _norm_item_name(q_name) == nn or (not _is_blank_code(code) and str(q_code).strip().lower() == str(code).strip().lower()):
            return False
    sl = _queue_next_sl(fac)
    cursor.execute("""INSERT INTO import_queue (factory_name, sl_no, prod_id, item_name, size, department, category, erp_stock, current_stock, unit_price, status)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Pending Approval')""",
                   (fac, sl, code, name, size or "", dept, cat, erp, phys, price))
    return True


# ---------- Bulk import engine: every row is saved in Master Inventory (zero balance included) ----------
def _idx_add(idx, sl, code, name, size):
    e = {"sl": sl, "code": str(code or ""), "name": name or "", "size": size or "",
         "nn": _norm_item_name(name), "ns": _norm_size(size)}
    if not any(x is e for x in idx["all"]):
        idx["all"].append(e)
    _idx_reindex(idx, e)
    try:
        idx["max_sl"] = max(idx["max_sl"], int(sl))
    except (TypeError, ValueError):
        pass
    return e


def _idx_reindex(idx, e):
    def put(d, k):
        lst = d.setdefault(k, [])
        if not any(x is e for x in lst):
            lst.append(e)
    if e["nn"]:
        put(idx["by_name"], e["nn"])
    ck = e["code"].strip().lower()
    if ck:
        put(idx["by_code"], ck)
        idx["codes"].add(ck)
        b = _code_base(e["code"], e["size"]).lower()
        if b:
            put(idx["by_code"], b)


def _load_inv_index(fac):
    """In-memory index of one unit's Master Inventory (fast matching for thousands of rows)."""
    idx = {"all": [], "by_name": {}, "by_code": {}, "codes": set(), "max_sl": 0, "temp_n": 0}
    cursor.execute("SELECT sl_no, prod_id, item_name, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (fac,))
    for sl, code, name, size in cursor.fetchall():
        _idx_add(idx, sl, code, name, size)
    cursor.execute("SELECT MAX(sl_no) FROM import_queue WHERE factory_name=%s", (fac,))
    q = cursor.fetchone()[0] or 0
    idx["max_sl"] = max(idx["max_sl"], q)
    return idx


def _idx_find(idx, code, name, size, claim_blank=True, loose=True):
    """Find the SAME product + SAME size. Different size of the same name / ERP code is a different item.
    claim_blank: an old row with no size may be matched (its size is then filled in).
    loose: when the file has no size, a single candidate is accepted."""
    ns, nn = _norm_size(size), _norm_item_name(name)
    ck = "" if _is_blank_code(code) else str(code).strip().lower()
    pools = []
    if ck:
        pools.append(idx["by_code"].get(ck, []))
    if nn:
        pools.append(idx["by_name"].get(nn, []))
    for pool in pools:
        for e in pool:
            if e["ns"] == ns:
                return e
    if claim_blank and ns:
        for pool in pools:
            for e in pool:
                if not e["ns"]:
                    return e
    if loose and not ns:
        for pool in pools:
            if len(pool) == 1:
                return pool[0]
    return None


def _idx_temp_code(idx):
    n = idx.get("temp_n", 0) + 1
    while f"temp-{n:04d}" in idx["codes"]:
        n += 1
    idx["temp_n"] = n
    return f"TEMP-{n:04d}"


def _unique_code(idx, code, size):
    """ERP code is kept exactly as given. If the same code is already used by ANOTHER size, it is stored
    as CODE-SIZE so that every size stays a separate, uniquely identifiable item."""
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


def _idx_insert(fac, idx, code, name, size, dept, cat, erp, phys, price, unit):
    final = _idx_temp_code(idx) if _is_blank_code(code) else _unique_code(idx, code, size)
    idx["max_sl"] += 1
    sl = idx["max_sl"]
    cursor.execute("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category, erp_stock, current_stock, unit_price, erp_status, unit_name)
                      VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ERP Pending', %s)""",
                   (sl, final, fac, name, size or "", dept or "Maintenance", cat or "Uncategorized (Edit Later)", erp, phys, price or 0.0, unit or "Pcs"))
    return _idx_add(idx, sl, final, name, size)


def _import_rows_to_master(fac, rows):
    """Saves EVERY row directly into Master Inventory of `fac` (and creates missing products in the other unit with stock 0).
    rows: list of dicts with keys code, name, size, phys (None = blank cell), erp, price, unit, dept, cat.
    - existing product + size  -> UPDATED in place (no new row). Blank stock cell keeps the old stock.
    - new product / new size   -> ADDED, zero balance included (blank stock = 0)
    Caller commits."""
    other = _other_factory(fac)
    idx, oidx = _load_inv_index(fac), _load_inv_index(other)
    st = {"updated": 0, "added": 0, "added_zero": 0, "mirrored": 0, "dup_rows": 0,
          "no_size": 0, "size_filled": 0, "code_fixed": 0, "queue_cleared": 0}
    touched = set()
    for r in rows:
        code = "" if _is_blank_code(r["code"]) else str(r["code"]).strip()
        name = r["name"] or code
        size = r["size"] or ""
        e = _idx_find(idx, code, name, size)
        if e:
            if e["sl"] in touched:
                st["dup_rows"] += 1
            touched.add(e["sl"])
            new_size = size if (size and not e["ns"]) else None
            new_code = _unique_code(idx, code, size or e["size"]) if (code and e["code"].upper().startswith("TEMP-")) else None
            cursor.execute("""UPDATE inventory SET current_stock=COALESCE(%s, current_stock), erp_stock=COALESCE(%s, erp_stock),
                                     unit_price=COALESCE(%s, unit_price), unit_name=COALESCE(%s, unit_name),
                                     size=COALESCE(%s, size), prod_id=COALESCE(%s, prod_id)
                              WHERE sl_no=%s AND factory_name=%s""",
                           (r["phys"], r["erp"], r["price"], r["unit"], new_size, new_code, e["sl"], fac))
            if new_size:
                e["size"], e["ns"] = new_size, _norm_size(new_size)
                st["size_filled"] += 1
            if new_code:
                old_code = e["code"]
                cursor.execute("UPDATE transactions SET prod_id=%s WHERE sl_no=%s AND factory_name=%s", (new_code, e["sl"], fac))
                cursor.execute("UPDATE requisition_tracking SET prod_id=%s WHERE factory_name=%s AND prod_id=%s", (new_code, fac, old_code))
                e["code"] = new_code
                st["code_fixed"] += 1
            _idx_reindex(idx, e)
            st["updated"] += 1
        else:
            phys0 = r["phys"] if r["phys"] is not None else 0.0
            erp0 = r["erp"] if r["erp"] is not None else phys0
            e = _idx_insert(fac, idx, code, name, size, r["dept"], r["cat"], erp0, phys0, r["price"], r["unit"])
            touched.add(e["sl"])
            st["added"] += 1
            if phys0 == 0:
                st["added_zero"] += 1
            if not size:
                st["no_size"] += 1
            if _idx_find(oidx, code, name, size, claim_blank=False, loose=False) is None:
                _idx_insert(other, oidx, code, name, size, r["dept"], r["cat"], 0.0, 0.0, r["price"], r["unit"])
                st["mirrored"] += 1
    # old rows still waiting in the Unmatch Queue that are now in Master Inventory are closed
    cursor.execute("SELECT id, prod_id, item_name, COALESCE(size,'') FROM import_queue WHERE factory_name=%s AND status='Pending Approval'", (fac,))
    for q_id, q_code, q_name, q_size in cursor.fetchall():
        if _idx_find(idx, q_code, q_name, q_size, claim_blank=False, loose=False) is not None:
            cursor.execute("UPDATE import_queue SET status='Approved' WHERE id=%s", (q_id,))
            st["queue_cleared"] += 1
    return st


def make_field(win, label, value="", width=36):
    tk.Label(win, text=label, bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=25, pady=(6, 1))
    e = tk.Entry(win, width=width, font=("Arial", 9))
    e.pack(anchor="w", padx=25)
    e.insert(0, value)
    return e


# ================= MAIN APPLICATION WINDOW =================
root = tk.Tk()
root.title("KC & Windy Smart Stock Tracker & Budget Control [Upgraded Secure Edition] - Repair Module v2")
root.geometry("1450x920")
root.config(bg="#f4f6f9")

selected_factory = tk.StringVar(value="KC Washing Plant")
current_user_role = tk.StringVar(value="Store Officer")
current_authenticated_user = tk.StringVar(value="Officer_Sagor")


def is_logged_in():
    return bool(current_authenticated_user.get()) and current_user_role.get() != "Guest"


def require_login():
    if not is_logged_in():
        messagebox.showerror("Login Required", "Please login first (🔑 Login) to perform this action.")
        return False
    return True


def _save_template(df, initial):
    fp = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=initial, filetypes=[("Excel Files", "*.xlsx")])
    if fp:
        try:
            df.to_excel(fp, index=False)
            messagebox.showinfo("Template Saved", f"Format file saved:\n{fp}\n\nFill it with your data and import it.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save template: {e}")


def apply_session(user, role):
    current_authenticated_user.set(user)
    current_user_role.set(role)
    lbl_current_role_display.config(text=f"Logged In: {user} [{role}]", fg="#68d391")
    entry_officer.config(state="normal")
    entry_officer.delete(0, tk.END)
    entry_officer.insert(0, user)
    entry_officer.config(state="readonly")
    refresh_data()


def logout_user():
    if not is_logged_in():
        messagebox.showinfo("Logout", "No user is currently logged in.")
        return
    u = current_authenticated_user.get()
    _audit("LOGOUT", f"User {u} logged out.")
    conn.commit()
    current_authenticated_user.set("")
    current_user_role.set("Guest")
    lbl_current_role_display.config(text="Not Logged In", fg="#fc8181")
    entry_officer.config(state="normal")
    entry_officer.delete(0, tk.END)
    entry_officer.insert(0, "-")
    entry_officer.config(state="readonly")
    messagebox.showinfo("Logout", "Logged out successfully. Please login again to continue.")


def change_manager_password():
    win = tk.Toplevel(root)
    win.title("Change Store Manager Password")
    win.geometry("380x330")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text="Change Store Manager Password", font=("Arial", 11, "bold"), bg="white", fg="#1b3b6f").pack(pady=10)
    e_old = make_field(win, "Current Manager Password:", "", 30)
    e_old.config(show="*")
    e_new = make_field(win, "New Password (min 6 characters):", "", 30)
    e_new.config(show="*")
    e_cnf = make_field(win, "Confirm New Password:", "", 30)
    e_cnf.config(show="*")

    def save():
        old, new, cnf = e_old.get(), e_new.get(), e_cnf.get()
        if not verify_manager_password(old):
            messagebox.showerror("Access Denied", "Current manager password is incorrect!", parent=win)
            return
        if len(new) < 6:
            messagebox.showerror("Error", "New password must be at least 6 characters!", parent=win)
            return
        if new != cnf:
            messagebox.showerror("Error", "New password and confirm password do not match!", parent=win)
            return
        try:
            cursor.execute("UPDATE users SET password=%s WHERE role='Store Manager'", (hash_password(new),))
            if cursor.rowcount == 0:
                cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s)",
                               ("Store_Manager", hash_password(new), "Store Manager", "Manager Admin"))
            _audit("CHANGE_MANAGER_PWD", "Store Manager password was changed.")
            conn.commit()
            messagebox.showinfo("Success", "Manager password changed successfully!", parent=win)
            win.destroy()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to change password: {e}", parent=win)

    tk.Button(win, text="Save New Password", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=15)


style = ttk.Style()
style.theme_use("default")
style.configure("TNotebook.Tab", font=("Arial", 9, "bold"), padding=[8, 4], background="#e0e0e0")
style.map("TNotebook.Tab", background=[("selected", "#1b3b6f")], foreground=[("selected", "white")])

header_frame = tk.Frame(root, bg="#1b3b6f", pady=6)
header_frame.pack(fill="x")

title_lbl = tk.Label(header_frame, text="KC & WINDY SMART STOCK TRACKER & BUDGET CONTROL", font=("Arial", 13, "bold"), bg="#1b3b6f", fg="white")
title_lbl.pack()

author_lbl = tk.Label(header_frame, text="Designed & Created By: MD. Sagor Ali", font=("Arial", 8, "italic"), bg="#1b3b6f", fg="#a0c4ff")
author_lbl.pack(pady=(1, 0))

auth_toolbar = tk.Frame(root, bg="#2d3748", pady=4)
auth_toolbar.pack(fill="x")

tk.Label(auth_toolbar, text=" 🔐 Authentication & Access Control: ", font=("Arial", 8, "bold"), bg="#2d3748", fg="white").pack(side="left", padx=10)


def open_login_window():
    login_win = tk.Toplevel(root)
    login_win.title("Secure Login Portal")
    login_win.geometry("350x280")
    login_win.config(bg="white")
    login_win.grab_set()

    tk.Label(login_win, text="System Login", font=("Arial", 11, "bold"), bg="white", fg="#1b3b6f").pack(pady=10)
    tk.Label(login_win, text="Username:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_user = tk.Entry(login_win, width=30, font=("Arial", 9))
    e_user.pack(padx=30)
    e_user.insert(0, current_authenticated_user.get())

    tk.Label(login_win, text="Password:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_pass = tk.Entry(login_win, width=30, show="*", font=("Arial", 9))
    e_pass.pack(padx=30)

    def verify_login():
        u = e_user.get().strip()
        p = e_pass.get().strip()
        cursor.execute("SELECT password, role FROM users WHERE username=%s", (u,))
        res = cursor.fetchone()
        if res and verify_password(res[0], p):
            role = res[1]
            _audit("LOGIN", f"User {u} logged in successfully as {role}.")
            conn.commit()
            apply_session(u, role)
            messagebox.showinfo("Login Success", f"Welcome {u}!\nActive Role: {role}")
            login_win.destroy()
        else:
            messagebox.showerror("Login Failed", "Invalid Username or Password!")

    e_pass.bind("<Return>", lambda e: verify_login())
    tk.Button(login_win, text="Login", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), width=15, command=verify_login).pack(pady=15)


def open_registration_window():
    reg_win = tk.Toplevel(root)
    reg_win.title("Officer Account Registration")
    reg_win.geometry("380x350")
    reg_win.config(bg="white")
    reg_win.grab_set()

    tk.Label(reg_win, text="Register New Officer Account", font=("Arial", 11, "bold"), bg="white", fg="#1b3b6f").pack(pady=10)

    tk.Label(reg_win, text="Full Name:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_fname = tk.Entry(reg_win, width=32, font=("Arial", 9))
    e_fname.pack(padx=30)

    tk.Label(reg_win, text="Username (Unique):", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_user = tk.Entry(reg_win, width=32, font=("Arial", 9))
    e_user.pack(padx=30)

    tk.Label(reg_win, text="Password:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_pass = tk.Entry(reg_win, width=32, show="*", font=("Arial", 9))
    e_pass.pack(padx=30)

    tk.Label(reg_win, text="Confirm Password:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_cpass = tk.Entry(reg_win, width=32, show="*", font=("Arial", 9))
    e_cpass.pack(padx=30)

    tk.Label(reg_win, text="Note: Default role is restricted to Store Officer.", font=("Arial", 7, "italic"), bg="white", fg="#666").pack(anchor="w", padx=30, pady=2)

    def register_user():
        fname = e_fname.get().strip()
        user = e_user.get().strip()
        pwd = e_pass.get().strip()
        cpwd = e_cpass.get().strip()

        if not fname or not user or not pwd:
            messagebox.showerror("Error", "All fields are required!")
            return
        if pwd != cpwd:
            messagebox.showerror("Error", "Passwords do not match!")
            return

        cursor.execute("SELECT id FROM users WHERE username=%s", (user,))
        if cursor.fetchone():
            messagebox.showerror("Error", "Username already exists! Please choose another.")
            return

        try:
            cursor.execute("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s)",
                           (user, hash_password(pwd), "Store Officer", fname))
            _audit("REGISTER", f"New Store Officer account registered: {user}")
            conn.commit()
            messagebox.showinfo("Success", "Account registered successfully! You can now log in.")
            reg_win.destroy()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to register account: {e}")

    tk.Button(reg_win, text="Register Account", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=18, command=register_user).pack(pady=15)


btn_login = tk.Button(auth_toolbar, text="🔑 Login", bg="#2b6cb0", fg="white", font=("Arial", 8, "bold"), command=open_login_window)
btn_login.pack(side="left", padx=5)

btn_logout = tk.Button(auth_toolbar, text="🚪 Logout", bg="#c53030", fg="white", font=("Arial", 8, "bold"), command=logout_user)
btn_logout.pack(side="left", padx=5)

btn_reg = tk.Button(auth_toolbar, text="📝 Register Account", bg="#2f855a", fg="white", font=("Arial", 8, "bold"), command=open_registration_window)
btn_reg.pack(side="left", padx=5)

btn_chg_pw = tk.Button(auth_toolbar, text="🔒 Change Manager Password", bg="#6b46c1", fg="white", font=("Arial", 8, "bold"), command=change_manager_password)
btn_chg_pw.pack(side="left", padx=5)

lbl_current_role_display = tk.Label(auth_toolbar, text="Logged In: Officer_Sagor [Store Officer]", font=("Arial", 8, "bold"), bg="#2d3748", fg="#68d391")
lbl_current_role_display.pack(side="right", padx=15)

factory_toolbar = tk.Frame(root, bg="#d9e2ec", pady=4)
factory_toolbar.pack(fill="x")

tk.Label(factory_toolbar, text=" 🏭 Select Active Factory: ", font=("Arial", 9, "bold"), bg="#d9e2ec", fg="#1b3b6f").pack(side="left", padx=10)


def on_factory_change(event=None):
    _ds_sync_factory()          # defined later; called at event time only
    refresh_data()              # defined later; called at event time only


combo_factory_global = ttk.Combobox(factory_toolbar, values=["KC Washing Plant", "Windy Washing LTD", "🌟 CONSOLIDATED (Both Factories)"], textvariable=selected_factory, width=35, font=("Arial", 9, "bold"), state="readonly")
combo_factory_global.pack(side="left", padx=5)
combo_factory_global.bind("<<ComboboxSelected>>", on_factory_change)

lbl_active_display = tk.Label(factory_toolbar, text="Active View: KC Washing Plant", font=("Arial", 9, "bold"), bg="#d9e2ec", fg="#0d47a1")
lbl_active_display.pack(side="right", padx=15)

budget_frame = tk.LabelFrame(root, text=" 1. Financial & Budget Control & Analytics Panel ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=10, pady=5)
budget_frame.pack(fill="x", padx=10, pady=4)

lbl_budget_val = tk.Label(budget_frame, text="Total Budget: 0.00 BDT  |  Consumption Cost: 0.00 BDT  |  Remaining: 0.00 BDT  |  Utilization: 0.0%  |  Status: SAFE", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f")
lbl_budget_val.pack(anchor="w")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True, padx=10, pady=4)

tab_trans = ttk.Frame(notebook)
tab_inventory = ttk.Frame(notebook)
tab_audit = ttk.Frame(notebook)
tab_issue_ledger = ttk.Frame(notebook)
tab_transfer_history = ttk.Frame(notebook)
tab_req_track = ttk.Frame(notebook)
tab_repair = ttk.Frame(notebook)
tab_monthly_report = ttk.Frame(notebook)
tab_forecast = ttk.Frame(notebook)
tab_category_budget = ttk.Frame(notebook)
tab_daily_sheet = ttk.Frame(notebook)

notebook.add(tab_trans, text="[1] TRANSACTIONS")
notebook.add(tab_inventory, text="[2] INVENTORY")
notebook.add(tab_audit, text="[3] ERP AUDIT")
notebook.add(tab_issue_ledger, text="[4] ISSUE LEDGER")
notebook.add(tab_transfer_history, text="[5] TRANSFER HISTORY")
notebook.add(tab_req_track, text="[6] REQUISITION")
notebook.add(tab_repair, text="[7] REPAIR")
notebook.add(tab_monthly_report, text="[8] LEDGER")
notebook.add(tab_forecast, text="[9] FORECAST")
notebook.add(tab_category_budget, text="[10] BUDGET")
notebook.add(tab_daily_sheet, text="[11] DAILY WORK SHEET")

# ================= TAB 1: TRANSACTIONS =================
EMPTY_PROD_TXT = "Product: --\nSize: --\nERP Code: --\nStock: -- | Short Item QTY: --"

mid_frame = tk.Frame(tab_trans, bg="#f4f6f9")
mid_frame.pack(fill="both", expand=True, padx=5, pady=5)

form_frame = tk.LabelFrame(mid_frame, text=" New Transaction & Entry Panel ", font=("Arial", 9, "bold"), bg="white", padx=10, pady=6)
form_frame.pack(side="left", fill="y", padx=(0, 5))

tk.Label(form_frame, text="Authenticated Officer:", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky="w", pady=2)
entry_officer = tk.Entry(form_frame, width=22, font=("Arial", 9))
entry_officer.grid(row=0, column=1, pady=2, padx=2)
entry_officer.insert(0, current_authenticated_user.get())
entry_officer.config(state="readonly")

tk.Label(form_frame, text="Search (Name / Size / ERP / SL):", bg="white", font=("Arial", 8, "bold")).grid(row=1, column=0, sticky="w", pady=2)
entry_search = tk.Entry(form_frame, width=22, font=("Arial", 9))
entry_search.grid(row=1, column=1, pady=2, padx=2)

tk.Label(form_frame, text="SL No / ERP Code:", bg="white", font=("Arial", 8, "bold")).grid(row=2, column=0, sticky="w", pady=2)
entry_item = tk.Entry(form_frame, width=22, font=("Arial", 9))
entry_item.grid(row=2, column=1, pady=2, padx=2)

lbl_prod_info = tk.Label(form_frame, text=EMPTY_PROD_TXT, bg="#e8f4fd", fg="#0d47a1", font=("Arial", 8, "bold"), padx=4, pady=3, justify="left")
lbl_prod_info.grid(row=3, column=0, columnspan=2, sticky="we", pady=3)

tk.Label(form_frame, text="Quantity (QTY):", bg="white", font=("Arial", 8, "bold")).grid(row=4, column=0, sticky="w", pady=2)
entry_qty = tk.Entry(form_frame, width=22, font=("Arial", 9))
entry_qty.grid(row=4, column=1, pady=2, padx=2)

tk.Label(form_frame, text="Transaction Type:", bg="white", font=("Arial", 9, "bold"), fg="#1b3b6f").grid(row=5, column=0, sticky="w", pady=4)
combo_type = ttk.Combobox(form_frame, values=list(TRANS_TYPE_LABELS.values()), width=30, font=("Arial", 9, "bold"), state="readonly")
combo_type.grid(row=5, column=1, pady=4, padx=2)
combo_type.current(0)

tk.Label(form_frame, text="Date (DD-Mon-YYYY):", bg="white", font=("Arial", 8, "bold")).grid(row=6, column=0, sticky="w", pady=2)
tx_date_var = tk.StringVar(value=datetime.now().strftime("%d-%b-%Y"))
tx_date_frame = tk.Frame(form_frame, bg="white")
tx_date_frame.grid(row=6, column=1, sticky="w", pady=2, padx=2)
tx_date_entry = tk.Entry(tx_date_frame, textvariable=tx_date_var, width=13, font=("Arial", 9))
tx_date_entry.pack(side="left")
tk.Button(tx_date_frame, text="Today", bg="#718096", fg="white", font=("Arial", 7, "bold"),
          command=lambda: tx_date_var.set(datetime.now().strftime("%d-%b-%Y"))).pack(side="left", padx=3)

chk_verify_var = tk.BooleanVar()
chk_verify = tk.Checkbutton(form_frame, text="Physically Verified (3-Day Cooldown Check)", variable=chk_verify_var, bg="white", fg="#b71c1c", font=("Arial", 8, "bold"), justify="left")
chk_verify.grid(row=7, column=0, columnspan=2, sticky="w", pady=6)

tk.Label(form_frame, text="Activity Notes / Remarks:", bg="white", font=("Arial", 8, "bold"), fg="#333333").grid(row=8, column=0, sticky="w", pady=2)
text_notes = tk.Text(form_frame, width=21, height=2, font=("Arial", 9))
text_notes.grid(row=8, column=1, pady=2, padx=2)


def _prod_label_text(name, fac, size, code, stock, erp):
    short = max((erp or 0) - (stock or 0), 0)
    return (f"Product: {name} [{fac}]\nSize: {size or '-'}\nERP Code: {code}\n"
            f"Stock: {stock:g} | Short Item QTY: {short:g}")


def fetch_product_info(event=None):
    try:
        val = entry_item.get().strip()
        fac = selected_factory.get()
        if not val:
            lbl_prod_info.config(text=EMPTY_PROD_TXT, fg="gray", bg="#f1f1f1")
            return
        row, cands = _resolve_item(fac, val)
        if row:
            lbl_prod_info.config(text=_prod_label_text(row[3], row[2], row[4], row[1], row[5], row[6]), fg="#0d47a1", bg="#e8f4fd")
        elif len(cands) > 1:
            lbl_prod_info.config(text=f"{len(cands)} items match this code/name.\nType the exact SL No to pick one.", fg="#b45309", bg="#fff8e1")
        else:
            lbl_prod_info.config(text="Item not found in active factory!", fg="red", bg="#fde8e8")
    except Exception:
        lbl_prod_info.config(text="Product: [Enter SL/ERP] | Stock: --", fg="gray", bg="#f1f1f1")


entry_item.bind("<KeyRelease>", fetch_product_info)


def search_item_db(event=None):
    keyword = entry_search.get().strip()
    if not keyword:
        return
    row, cands = _resolve_item(selected_factory.get(), keyword)
    if row:
        entry_item.delete(0, tk.END)
        entry_item.insert(0, str(row[0]))
        lbl_prod_info.config(text=_prod_label_text(row[3], row[2], row[4], row[1], row[5], row[6]), fg="#0d47a1", bg="#e8f4fd")
    elif len(cands) > 1:
        lbl_prod_info.config(text=f"{len(cands)} items match '{keyword}'.\nType more letters or the exact SL No.", fg="#b45309", bg="#fff8e1")


entry_search.bind("<KeyRelease>", search_item_db)

right_top_frame = tk.LabelFrame(mid_frame, text=" Historical & Recent Transactions (Right-Click to Delete by Manager) ", font=("Arial", 9, "bold"), bg="white", padx=5, pady=5)
right_top_frame.pack(side="top", fill="both", expand=True)

columns_recent = ("ID", "Factory", "Officer", "SL", "ERP Code", "Item Name", "Qty", "Type", "Verification Status", "Notes", "Date & Time")
tree_recent = ttk.Treeview(right_top_frame, columns=columns_recent, show="headings", height=5)
col_w_recent = [40, 110, 70, 30, 80, 150, 50, 150, 100, 90, 110]
for col, w in zip(columns_recent, col_w_recent):
    tree_recent.heading(col, text=col)
    align = "e" if col in ["ID", "SL", "Qty"] else "w"
    tree_recent.column(col, width=w, anchor=align, stretch=True)
tree_recent.pack(fill="both", expand=True, pady=(0, 2))


def _delete_transaction_by_id(trans_id):
    """Manager-only delete of a transaction; stock is reverted."""
    if not ask_manager_password("Enter Password for Store Manager to Delete Transaction:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can delete transactions.")
        return
    try:
        cursor.execute("SELECT factory_name, sl_no, qty, trans_type FROM transactions WHERE id=%s", (trans_id,))
        t_data = cursor.fetchone()
        if t_data:
            fac, sl_no, qty, t_type = t_data
            if t_type in ["Supplier. Rec", "Internal Rec", "Stock Adjustment (+)"]:
                cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, fac))
            elif t_type in ["Issued", "Internal Issue", "Stock Adjustment (-)"]:
                cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, fac))
            cursor.execute("DELETE FROM transactions WHERE id=%s", (trans_id,))
            _audit("DELETE_TRANS", f"Deleted transaction ID {trans_id}")
            conn.commit()
            messagebox.showinfo("Success", f"Transaction ID {trans_id} deleted successfully and stock reverted!")
            refresh_data()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Failed to delete transaction: {e}")


def delete_selected_transaction(event=None):
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access and cannot delete transactions!")
        return
    selected_item = tree_recent.selection()
    if not selected_item:
        messagebox.showerror("Selection Error", "Please select a transaction from the list to delete!")
        return
    _delete_transaction_by_id(tree_recent.item(selected_item[0], "values")[0])


def edit_transaction_popup(t_id):
    """Manager edit of a transaction's date and remarks (quantity is not changed, so stock stays correct)."""
    cursor.execute("SELECT id, factory_name, item_name, qty, trans_type, date, notes FROM transactions WHERE id=%s", (t_id,))
    r = cursor.fetchone()
    if not r:
        messagebox.showerror("Not Found", "Transaction not found. Please refresh.")
        return
    win = tk.Toplevel(root)
    win.title(f"Edit Transaction ID {r[0]}")
    win.geometry("460x300")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text=f"{r[2]}  |  {r[1]}", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    tk.Label(win, text=f"Type: {_tlabel(r[4])}   Qty: {r[3]:g}  (quantity is locked; delete & re-enter to change it)",
             font=("Arial", 8, "italic"), bg="white", fg="#666").pack()
    e_date = make_field(win, "Date (DD-Mon-YYYY):", r[5] or "", 20)
    e_notes = make_field(win, "Remarks / Notes:", r[6] or "", 44)

    def save():
        d = e_date.get().strip()
        try:
            datetime.strptime(d, "%d-%b-%Y")
        except ValueError:
            messagebox.showerror("Error", "Date must be in DD-Mon-YYYY format!", parent=win)
            return
        if not ask_manager_password("Enter Store Manager Password to save this transaction:"):
            messagebox.showerror("Access Denied", "Incorrect Password!", parent=win)
            return
        try:
            cursor.execute("UPDATE transactions SET date=%s, notes=%s WHERE id=%s", (d, e_notes.get().strip(), t_id))
            _audit("EDIT_TRANS", f"Transaction ID {t_id} edited (date {r[5]} -> {d})")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to save: {e}", parent=win)
            return
        win.destroy()
        messagebox.showinfo("Success", "Transaction updated.")
        refresh_data()

    tk.Button(win, text="Save Changes", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=20, command=save).pack(pady=14)


def edit_selected_transaction():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access!")
        return
    sel = tree_recent.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a transaction from the list first!")
        return
    edit_transaction_popup(tree_recent.item(sel[0], "values")[0])


tree_recent.bind("<Button-3>", delete_selected_transaction)


def export_report_excel():
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT * FROM transactions")
    else:
        cursor.execute("SELECT * FROM transactions WHERE factory_name=%s", (fac,))
    rows = cursor.fetchall()
    cols = ["ID", "Factory", "Officer", "SL", "ERP Code", "Item Name", "Qty", "Type", "Day", "Notes",
            "Date", "Time", "Verification", "ERP GRN Status", "ERP GRN Date"]
    df_trans = pd.DataFrame(rows, columns=cols)
    df_trans["Type"] = df_trans["Type"].map(_tlabel)
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
    if file_path:
        df_trans.to_excel(file_path, index=False)
        messagebox.showinfo("Success", f"Factory Report exported to Excel successfully!\nPath: {file_path}")


def export_report_pdf():
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT * FROM transactions")
    else:
        cursor.execute("SELECT * FROM transactions WHERE factory_name=%s", (fac,))
    rows = cursor.fetchall()
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Document", "*.pdf"), ("All Files", "*.*")])
    if file_path:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("========================================================\n")
            f.write(f"       OFFICIAL TRANSACTION REPORT: {fac}               \n")
            f.write("========================================================\n")
            f.write(f"Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}\n")
            f.write("--------------------------------------------------------\n\n")
            for r in rows:
                f.write(f"ID: {r[0]} | Fac: {r[1]} | Officer: {r[2]} | Item: {r[5]}\n")
                f.write(f"Qty: {r[6]} | Type: {_tlabel(r[7])} | Date: {r[10]} {r[11]} | Verif: {r[12]}\n")
                f.write("-" * 55 + "\n")
        messagebox.showinfo("Success", f"Official Report PDF saved successfully!\nPath: {file_path}")


tk.Button(right_top_frame, text="Export Excel", bg="#2e7d32", fg="white", font=("Arial", 8, "bold"), command=lambda: export_report_excel()).pack(side="right", padx=2)
tk.Button(right_top_frame, text="Export PDF", bg="#b71c1c", fg="white", font=("Arial", 8, "bold"), command=lambda: export_report_pdf()).pack(side="right", padx=2)
tk.Button(right_top_frame, text="✏️ Edit Selected (Manager)", bg="#d97706", fg="white", font=("Arial", 8, "bold"), command=lambda: edit_selected_transaction()).pack(side="right", padx=2)

# Save button (the save_transaction function itself is defined later in this file)
btn_save = tk.Button(form_frame, text="Save & Update Stock", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"),
                     command=lambda: save_transaction())
btn_save.grid(row=9, column=0, columnspan=2, pady=8, sticky="we")

# Low stock & negative stock alerts panel (filled by refresh_data)
alert_frame = tk.LabelFrame(tab_trans, text=" 🚨 DEDICATED LOW STOCK & NEGATIVE STOCK ALERTS PANEL ", font=("Arial", 9, "bold"), bg="white", fg="#cc0000", padx=5, pady=3)
alert_frame.pack(fill="both", expand=True, padx=5, pady=3)

columns_alert = ("Factory", "SL", "ERP Code", "Item Name", "Size", "Stock", "Status")
tree_alert = ttk.Treeview(alert_frame, columns=columns_alert, show="headings", height=4)
col_w_alert = [130, 40, 80, 260, 80, 70, 140]
for col, w in zip(columns_alert, col_w_alert):
    tree_alert.heading(col, text=col)
    align = "e" if col in ["SL", "Stock"] else "w"
    tree_alert.column(col, width=w, anchor=align, stretch=True)
tree_alert.pack(fill="both", expand=True)


# ================= TAB 2: INVENTORY MASTER =================
inv_frame = tk.Frame(tab_inventory, bg="white", padx=5, pady=5)
inv_frame.pack(fill="both", expand=True)

inv_top_action_bar = tk.Frame(inv_frame, bg="white", pady=2)
inv_top_action_bar.pack(fill="x", pady=(0, 3))


def download_opening_stock_format():
    df = pd.DataFrame([{
        "SL No": 1, "ERP Code": "ERP-0001", "Item Name": "Example Item", "Size": "XL (mandatory)", "Department": "Maintenance",
        "Category": "Maintenance Spare Parts", "Opening Physical Stock": 10, "ERP Stock": 10,
        "Unit Price": 150.0, "Unit": "Pcs"
    }])
    _save_template(df, "Opening_Physical_Stock_Format")


ERP_IMPORT_GUIDE = """ERP PRODUCT IMPORT GUIDE (Excel / CSV)

1. Use the 'Download Import Format' button. Keep the column headers exactly as they are.
2. Columns:
   - ERP Code  : ERP product code. Leave blank ONLY if the code is not yet known.
   - Item Name : Product name exactly as in ERP.
   - Size      : Recommended. Same name with a different size is a different product.
                 Example: 'Polo Shirt' + 'M' and 'Polo Shirt' + 'XL' are two items.
   - Opening Physical Stock / ERP Stock / Unit Price / Unit (Pcs or Kg)
3. Rows that match an existing item (by ERP Code + Size, or by Name + Size) UPDATE that item.
   No new row is created for it - a zero-stock item simply gets its new stock.
4. Rows that do NOT match are ADDED to Master Inventory directly - every row is saved,
   including items with ZERO or BLANK stock (blank stock = 0 balance). Nothing is hidden or lost.
   - Items without a Size are saved too; they are counted under 'Items without Size' so you can add the size later.
   - Items without an ERP Code get a temporary code (TEMP-0001 ...) that can be replaced later.
5. New items are automatically created in BOTH KC Washing and Windy Washing (stock 0 in the other unit).
6. One ERP Code with several sizes: the first size keeps the code as given, the other sizes are stored as
   CODE-SIZE (example ERP-0001-M) so each size is a separate item. Re-importing still matches them by Code + Size.
   The same Name + Size is never added twice in one unit (the database also enforces this).
   (The Unmatch / Import Queue is now used only by the ERP Balance import.)
7. Items already in stock but with no ERP code can be fixed later using
   'Edit Selected Item (Manager)' in the Master Inventory tab.
8. Serial matching: SL No is always the Master Inventory SL. Type an exact SL No in Transactions or
   double-click a row in the Daily Work Sheet to issue that exact item."""


def show_erp_import_guide():
    messagebox.showinfo("ERP Import Guideline", ERP_IMPORT_GUIDE)


def import_opening_physical_stock():
    if not require_login():
        return
    role = current_user_role.get()
    if role in ["Auditor", "Store Officer"]:
        messagebox.showerror("Permission Denied", f"{role} role cannot import inventory without Manager approval!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error", "Please select a specific factory before importing the opening stock!")
        return

    file_path = filedialog.askopenfilename(
        title=f"Select Opening Physical Stock Excel/CSV for {fac}",
        filetypes=[("Excel & CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")],
    )
    if not file_path:
        return

    backup_path = f"windy_store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        _backup_database(backup_path)
    except Exception as e:
        messagebox.showwarning("Backup Warning", f"Could not create backup: {e}")

    try:
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path, dtype=object)
        else:
            df = pd.read_excel(file_path, sheet_name=0, dtype=object)
    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to read the file: {e}")
        return

    cols = {
        "code": _find_col(df, ["erp code", "erp_code", "prod_id", "product id", "item code", "code"]),
        "name": _find_col(df, ["item name", "item_name", "description", "product name", "item"]),
        "size": _find_col(df, ["size", "item size", "product size", "sizes"]),
        "phys": _find_col(df, ["opening physical stock", "physical stock", "opening stock", "current stock", "current_stock", "physical qty", "qty", "stock"]),
        "erp": _find_col(df, ["erp stock", "erp_stock", "erp balance", "erp_balance"]),
        "price": _find_col(df, ["unit price", "unit_price", "price"]),
        "unit": _find_col(df, ["unit", "uom", "unit name"]),
        "dept": _find_col(df, ["department"]),
        "cat": _find_col(df, ["category"]),
    }
    if not cols["phys"]:
        messagebox.showerror("Format Error",
                             "'Opening Physical Stock' column not found in the file.\n\n"
                             f"Columns found: {', '.join(str(c) for c in df.columns)}\n\n"
                             "Click '📄 Download Import Format' to get the correct file layout.")
        return
    if not cols["code"] and not cols["name"]:
        messagebox.showerror("Format Error", "ERP Code or Item Name column is required to match items.")
        return
    if not cols["size"]:
        messagebox.showwarning("Size Column Missing",
                               "No 'Size' column was found. Items will be saved WITHOUT size (they are counted as 'Items without Size' "
                               "and the size can be added later with 'Edit Selected Item').")

    skipped = 0
    rows = []
    for _, row in df.iterrows():
        code = _txt(row[cols["code"]]) if cols["code"] else ""
        name = _txt(row[cols["name"]]) if cols["name"] else ""
        size = _txt(row[cols["size"]]) if cols["size"] else ""
        if _is_blank_code(code) and not name:
            skipped += 1
            continue
        raw_phys = row[cols["phys"]]
        if _txt(raw_phys) != "" and _num(raw_phys) is None:      # text that is not a number
            skipped += 1
            continue
        raw_erp = row[cols["erp"]] if cols["erp"] else None
        if raw_erp is not None and _txt(raw_erp) != "" and _num(raw_erp) is None:
            raw_erp = None
        unit = _txt(row[cols["unit"]]) if cols["unit"] else ""
        rows.append({
            "code": code, "name": name, "size": size,
            "phys": _num(raw_phys),                              # None = blank cell (zero balance for NEW items)
            "erp": _num(raw_erp) if raw_erp is not None else None,
            "price": _num(row[cols["price"]]) if cols["price"] else None,
            "unit": unit if unit in ("Pcs", "Kg") else None,
            "dept": _txt(row[cols["dept"]]) if cols["dept"] else "",
            "cat": _txt(row[cols["cat"]]) if cols["cat"] else "",
        })

    try:
        st = _import_rows_to_master(fac, rows)
        _audit("IMPORT_OPENING_STOCK", f"{fac}: file rows {len(df)}, added {st['added']} (zero balance {st['added_zero']}), updated {st['updated']}, "
                                       f"copied to other unit {st['mirrored']} from {os.path.basename(file_path)}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Import Error", f"Import failed and was rolled back:\n{e}")
        return

    cursor.execute("SELECT COUNT(*), SUM(CASE WHEN COALESCE(current_stock,0)<=0 THEN 1 ELSE 0 END) FROM inventory WHERE factory_name=%s", (fac,))
    tot_items, zero_items = cursor.fetchone()
    extra = ""
    if st["dup_rows"]:
        extra += f"\n- Repeated rows in the file (same item + size, last row used): {st['dup_rows']}"
    if st["size_filled"]:
        extra += f"\n- Old items whose Size was filled in: {st['size_filled']}"
    if st["code_fixed"]:
        extra += f"\n- Temporary ERP codes replaced by real ERP codes: {st['code_fixed']}"
    if st["queue_cleared"]:
        extra += f"\n- Old Unmatch Queue rows now found in Master (closed): {st['queue_cleared']}"
    if st["no_size"]:
        extra += f"\n- Saved WITHOUT size (please add size later): {st['no_size']}"
    messagebox.showinfo("Import Summary", f"Opening Physical Stock import completed for {fac}!\n\n"
                                          f"- Rows read from file: {len(df)}\n"
                                          f"- NEW items added to Master Inventory: {st['added']}  (of which zero balance: {st['added_zero']})\n"
                                          f"- Existing items updated (no duplicate created): {st['updated']}\n"
                                          f"- Also created in the other unit (stock 0): {st['mirrored']}\n"
                                          f"- Skipped (empty / invalid rows): {skipped}{extra}\n\n"
                                          f"Master Inventory of {fac} now has {tot_items} items ({int(zero_items or 0)} with zero / no stock).\n\n"
                                          f"Backup: {backup_path}")
    refresh_data()


btn_import_master = tk.Button(inv_top_action_bar, text="📥 Import Opening Physical Stock", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: import_opening_physical_stock())
btn_import_master.pack(side="left", padx=2)

btn_import_fmt = tk.Button(inv_top_action_bar, text="📄 Download Import Format", bg="#2b6cb0", fg="white", font=("Arial", 9, "bold"), command=lambda: download_opening_stock_format())
btn_import_fmt.pack(side="left", padx=5)

btn_import_guide = tk.Button(inv_top_action_bar, text="📘 ERP Import Guideline", bg="#4a5568", fg="white", font=("Arial", 9, "bold"), command=lambda: show_erp_import_guide())
btn_import_guide.pack(side="left", padx=5)


def open_add_item_window():
    if not require_login():
        return
    role = current_user_role.get()
    if role == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot add new items!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error", "Please select a specific factory to add a new item!")
        return

    add_win = tk.Toplevel(root)
    add_win.title(f"Add New Item Manually - {fac}")
    add_win.geometry("420x520")
    add_win.config(bg="white")

    tk.Label(add_win, text="SL No (Auto-Generated):", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_sl = tk.Entry(add_win, width=30, font=("Arial", 9))
    e_sl.pack(padx=20)
    e_sl.insert(0, str(_queue_next_sl(fac)))

    tk.Label(add_win, text="ERP Code / Product ID (blank = temporary code, edit later):", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_code = tk.Entry(add_win, width=30, font=("Arial", 9))
    e_code.pack(padx=20)

    tk.Label(add_win, text="Item Name (mandatory):", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_name = tk.Entry(add_win, width=30, font=("Arial", 9))
    e_name.pack(padx=20)

    tk.Label(add_win, text="Size (mandatory):", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_size = tk.Entry(add_win, width=30, font=("Arial", 9))
    e_size.pack(padx=20)

    tk.Label(add_win, text="Department:", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_dept = ttk.Combobox(add_win, values=["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"], width=28, state="readonly")
    e_dept.pack(padx=20)
    e_dept.current(0)

    tk.Label(add_win, text="Category:", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    e_cat = ttk.Combobox(add_win, values=["Maintenance Spare Parts", "Electrical Accessories", "Utilities Spare Parts", "Stationeries Items", "Production Consumable Items", "Safety and Security", "Cleaning Goods"], width=28, state="readonly")
    e_cat.pack(padx=20)
    e_cat.current(0)

    tk.Label(add_win, text="Initial Stock Qty & Unit Price:", bg="white", font=("Arial", 9, "bold")).pack(anchor="w", padx=20, pady=4)
    frame_vals = tk.Frame(add_win, bg="white")
    frame_vals.pack(padx=20, anchor="w")
    e_stk = tk.Entry(frame_vals, width=12, font=("Arial", 9))
    e_stk.pack(side="left", padx=(0, 10))
    e_stk.insert(0, "0")
    e_prc = tk.Entry(frame_vals, width=12, font=("Arial", 9))
    e_prc.pack(side="left")
    e_prc.insert(0, "0.0")

    def save_new_item():
        try:
            sl = int(e_sl.get().strip())
            code = e_code.get().strip()
            name = e_name.get().strip()
            size = e_size.get().strip()
            dept = e_dept.get().strip()
            cat = e_cat.get().strip()
            stk = float(e_stk.get().strip())
            prc = float(e_prc.get().strip())
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numeric values for SL, Stock and Price!")
            return
        if not name or not size:
            messagebox.showerror("Error", "Item Name and Size are required!")
            return

        # NEW: the same product + size already exists (e.g. a zero-stock row imported earlier)
        # -> do NOT create a duplicate; add the stock to that existing row instead.
        ex = _find_item_row(fac, name, size)
        if ex:
            if messagebox.askyesno("Item Already Exists",
                                   f"'{name}' [{size}] আগে থেকেই আছে (SL {ex[0]}, Current Stock {ex[2]:g}).\n\n"
                                   "নতুন আইটেম না বানিয়ে এই আইটেমেই স্টক যোগ করবেন?", parent=add_win):
                try:
                    now = datetime.now()
                    cursor.execute("UPDATE inventory SET current_stock=COALESCE(current_stock,0)+%s, unit_price=CASE WHEN %s>0 THEN %s ELSE unit_price END "
                                   "WHERE sl_no=%s AND factory_name=%s", (stk, prc, prc, ex[0], fac))
                    if stk > 0:
                        _insert_transaction(fac, current_authenticated_user.get(), ex[0], ex[1], name, stk, "Stock Adjustment (+)", now.day,
                                            "Stock added to existing item (Add New Item)", now.strftime("%d-%b-%Y"), now.strftime("%I:%M %p"), "Verified", "Not Required")
                    _audit("ADD_STOCK_EXISTING", f"{fac}: {name} [{size}] SL {ex[0]} +{stk:g} (no duplicate created)")
                    conn.commit()
                except Exception as e:
                    conn.rollback()
                    messagebox.showerror("Database Error", f"Failed to update: {e}", parent=add_win)
                    return
                messagebox.showinfo("Success", f"Stock added to existing SL {ex[0]} (no duplicate created).", parent=add_win)
                add_win.destroy()
                refresh_data()
            return

        if not code:
            code = _next_temp_code(fac)
        cursor.execute("SELECT * FROM inventory WHERE (sl_no=%s OR prod_id=%s) AND factory_name=%s", (sl, code, fac))
        if cursor.fetchone():
            messagebox.showerror("Duplicate Error", f"Duplicate SL No [{sl}] or ERP Code [{code}] already exists in {fac}!")
            return
        try:
            cursor.execute("INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category, erp_stock, current_stock, unit_price, erp_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                           (sl, code, fac, name, size, dept, cat, stk, stk, prc, "ERP Pending"))
            mirrored = _mirror_to_other(fac, code, name, size, dept, cat, prc)
            _audit("ADD_ITEM", f"{fac}: added {name} [{size}] [{code}]" + (" + copied to other unit" if mirrored else ""))
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to add item: {e}", parent=add_win)
            return
        messagebox.showinfo("Success", "New item added successfully!" + ("\nAlso created in the other unit (stock 0)." if mirrored else ""))
        add_win.destroy()
        refresh_data()

    tk.Button(add_win, text="Save Item", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=save_new_item).pack(pady=12)


btn_add_item_manual = tk.Button(inv_top_action_bar, text="+ Add New Item Manually", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: open_add_item_window())
btn_add_item_manual.pack(side="left", padx=5)


def _open_edit_inventory(fac, sl, old_code):
    """Opens the edit window for one inventory item (manager password must be checked by the caller)."""
    cursor.execute("""SELECT sl_no, prod_id, factory_name, item_name, department, category, erp_stock, current_stock, unit_price,
                      COALESCE(NULLIF(unit_name, ''), 'Pcs'), COALESCE(size,'') FROM inventory WHERE sl_no=%s AND prod_id=%s AND factory_name=%s""", (sl, old_code, fac))
    r = cursor.fetchone()
    if not r:
        messagebox.showerror("Not Found", "Item not found. Please refresh and try again.")
        return

    win = tk.Toplevel(root)
    win.title(f"Edit Inventory Item - {r[3]}")
    win.geometry("460x680")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text=f"Edit Item  |  {fac}  |  SL {r[0]}", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    tk.Label(win, text="Add the ERP Code and Size here when they are known. Past transactions will also be updated.",
             font=("Arial", 7, "italic"), bg="white", fg="#666").pack()
    e_code = make_field(win, "ERP Code / Product ID:", r[1] or "", 40)
    e_name = make_field(win, "Item Name:", r[3] or "", 40)
    e_size = make_field(win, "Size (mandatory):", r[10] or "", 40)
    tk.Label(win, text="Department:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=25, pady=(6, 1))
    e_dept = ttk.Combobox(win, values=["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"], width=38)
    e_dept.pack(anchor="w", padx=25)
    e_dept.set(r[4] or "Maintenance")
    e_cat = make_field(win, "Category:", r[5] or "", 40)
    e_erp = make_field(win, "ERP Stock:", f"{(r[6] or 0):g}", 20)
    e_phys = make_field(win, "Physical (Current) Stock:", f"{(r[7] or 0):g}", 20)
    e_price = make_field(win, "Unit Price (BDT):", f"{(r[8] or 0):g}", 20)
    tk.Label(win, text="Unit:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=25, pady=(6, 1))
    e_unit = ttk.Combobox(win, values=["Pcs", "Kg"], width=18, state="readonly")
    e_unit.pack(anchor="w", padx=25)
    e_unit.set(r[9] if r[9] in ("Pcs", "Kg") else "Pcs")

    def save():
        new_code = e_code.get().strip() or r[1]
        new_name = e_name.get().strip()
        new_size = e_size.get().strip()
        if not new_name or not new_size:
            messagebox.showerror("Error", "Item Name and Size are required!", parent=win)
            return
        try:
            erp_v = float(e_erp.get().strip() or 0)
            phys_v = float(e_phys.get().strip() or 0)
            price_v = float(e_price.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Error", "Stock and price must be numbers!", parent=win)
            return
        if _item_exists(fac, new_name, new_size, exclude_sl=r[0]):
            messagebox.showerror("Duplicate", f"'{new_name}' with size '{new_size}' already exists in {fac}!", parent=win)
            return
        cursor.execute("SELECT sl_no FROM inventory WHERE prod_id=%s AND factory_name=%s AND sl_no<>%s", (new_code, fac, r[0]))
        if cursor.fetchone():
            messagebox.showerror("Duplicate", f"ERP Code '{new_code}' already exists in {fac}!", parent=win)
            return
        try:
            cursor.execute("""UPDATE inventory SET prod_id=%s, item_name=%s, size=%s, department=%s, category=%s, erp_stock=%s, current_stock=%s,
                              unit_price=%s, unit_name=%s WHERE sl_no=%s AND factory_name=%s""",
                           (new_code, new_name, new_size, e_dept.get().strip(), e_cat.get().strip(), erp_v, phys_v, price_v, e_unit.get(), r[0], fac))
            if new_code != r[1] or new_name != r[3]:
                cursor.execute("UPDATE transactions SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (new_code, new_name, r[0], fac))
                if r[1]:
                    cursor.execute("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND prod_id=%s", (new_code, new_name, fac, r[1]))
            _audit("EDIT_INVENTORY", f"{fac} SL {r[0]}: [{r[1]}] {r[3]} [{r[10]}] -> [{new_code}] {new_name} [{new_size}]")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to update: {e}", parent=win)
            return
        win.destroy()
        messagebox.showinfo("Success", "Inventory item updated successfully!")
        refresh_data()

    tk.Button(win, text="Save Changes", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=14)


def edit_inventory_item():
    """Manager: edit an inventory item (ERP code, name, size, stock, price, unit)."""
    if not require_login():
        return
    sel = tree_inv.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item from Master Inventory first!")
        return
    if not ask_manager_password("Enter Store Manager Password to Edit Inventory Item:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can edit inventory.")
        return
    vals = tree_inv.item(sel[0], "values")
    _open_edit_inventory(vals[0], vals[1], vals[2])


btn_edit_inv = tk.Button(inv_top_action_bar, text="✏️ Edit Selected Item (Manager)", bg="#d97706", fg="white", font=("Arial", 9, "bold"), command=lambda: edit_inventory_item())
btn_edit_inv.pack(side="left", padx=5)


# ================= ERP MATCH & CHECK (is this product / size already in our system?) =================
def _ec_load():
    """Loads the Master Inventory of BOTH units (zero stock included) for fast checking."""
    data = {}
    for fac in ("KC Washing Plant", "Windy Washing LTD"):
        idx = {"all": [], "by_name": {}, "by_code": {}, "codes": set(), "max_sl": 0, "temp_n": 0}
        cursor.execute("SELECT sl_no, prod_id, item_name, COALESCE(size,''), COALESCE(erp_stock,0), COALESCE(current_stock,0) FROM inventory WHERE factory_name=%s ORDER BY item_name, sl_no", (fac,))
        for sl, code, name, size, erp, phys in cursor.fetchall():
            e = _idx_add(idx, sl, code, name, size)
            e["erp"], e["phys"] = erp, phys
        data[fac] = idx
    return data


def _ec_lookup(data, fac, name, size, code, fuzzy=True):
    """Returns (status, rows, note). status: FOUND | SIZE_MISSING | CODE_MATCH | SIMILAR | NOT_FOUND."""
    idx = data[fac]
    nn, ns = _norm_item_name(name), _norm_size(size)
    ck = "" if _is_blank_code(code) else str(code).strip().lower()
    name_rows = list(idx["by_name"].get(nn, [])) if nn else []
    code_rows = list(idx["by_code"].get(ck, [])) if ck else []
    base = name_rows or (code_rows if not nn else [])
    if base:
        base = sorted(base, key=lambda e: (e["ns"], e["sl"]))
        sizes = ", ".join(sorted({e["size"] or "(no size)" for e in base}))
        if ns:
            hit = [e for e in base if e["ns"] == ns]
            if hit:
                return "FOUND", hit + [e for e in base if e not in hit], f"Size '{size}' exists. All sizes in system: {sizes}"
            return "SIZE_MISSING", base, f"Product exists but size '{size}' is NOT in the list. Sizes in system: {sizes}"
        return "FOUND", base, f"Product exists. Sizes in system: {sizes}"
    if code_rows:
        hit = [e for e in code_rows if ns and e["ns"] == ns]
        return "CODE_MATCH", hit or code_rows, "Same ERP code exists but with a DIFFERENT product name - please check."
    similar = []
    if nn and len(nn) >= 3:
        similar = [e for k, lst in idx["by_name"].items() if nn in k or k in nn for e in lst][:60]
        if not similar and fuzzy:
            for k in difflib.get_close_matches(nn, list(idx["by_name"].keys()), n=5, cutoff=0.8):
                similar.extend(idx["by_name"][k])
    if similar:
        return "SIMILAR", similar, "Exact product not found. Similar names listed - check spelling."
    return "NOT_FOUND", [], "NOT in the system. This is a NEW product / size."


_EC_VERDICT = {
    "FOUND": ("✔ FOUND", "#1b5e20"), "SIZE_MISSING": ("⚠ SIZE NOT IN LIST", "#b45309"),
    "CODE_MATCH": ("⚠ CODE MATCH (name differs)", "#b45309"), "SIMILAR": ("≈ SIMILAR NAME ONLY", "#b45309"),
    "NOT_FOUND": ("✘ NOT FOUND - NEW ITEM", "#b71c1c"),
}


def open_erp_match_check():
    if not require_login():
        return
    win = tk.Toplevel(root)
    win.title("ERP Match & Check - is this product / size already in our system?")
    win.geometry("1040x640")
    win.config(bg="white")
    state = {"data": _ec_load()}

    top = tk.Frame(win, bg="white")
    top.pack(fill="x", padx=10, pady=(10, 4))
    v_name, v_size, v_code = tk.StringVar(), tk.StringVar(), tk.StringVar()
    for lbl, var, w in (("Product Name:", v_name, 34), ("Size:", v_size, 12), ("ERP Code:", v_code, 18)):
        tk.Label(top, text=lbl, bg="white", font=("Arial", 9, "bold")).pack(side="left", padx=(6, 2))
        ent = tk.Entry(top, textvariable=var, width=w, font=("Arial", 10))
        ent.pack(side="left", padx=2)
        ent.bind("<Return>", lambda e: run_check(True))
        ent.bind("<KeyRelease>", lambda e: run_check(False) if e.keysym != "Return" else None)
        if var is v_name:
            ent.focus_set()

    verdict_frame = tk.Frame(win, bg="white")
    verdict_frame.pack(fill="x", padx=10, pady=2)
    lbl_v = {}
    for fac in ("KC Washing Plant", "Windy Washing LTD"):
        lbl_v[fac] = tk.Label(verdict_frame, text=f"{fac}: --", bg="#f1f1f1", fg="gray", font=("Arial", 9, "bold"), anchor="w", justify="left", padx=6, pady=4)
        lbl_v[fac].pack(fill="x", pady=1)

    cols = ("Unit", "SL No", "ERP Code", "Item Name", "Size", "ERP Stock", "Physical Stock", "Result")
    tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
    for c, w in zip(cols, (120, 55, 120, 280, 90, 80, 95, 190)):
        tree.heading(c, text=c)
        tree.column(c, width=w, anchor="e" if c in ("SL No", "ERP Stock", "Physical Stock") else "w", stretch=True)
    tree.tag_configure("hit", background="#e8f5e9")
    tree.tag_configure("zero", foreground="#777777")
    sb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y", padx=(0, 6), pady=4)
    tree.pack(fill="both", expand=True, padx=(10, 0), pady=4)

    def run_check(fuzzy):
        for i in tree.get_children():
            tree.delete(i)
        name, size, code = v_name.get().strip(), v_size.get().strip(), v_code.get().strip()
        if not name and _is_blank_code(code):
            for fac in lbl_v:
                lbl_v[fac].config(text=f"{fac}: --", fg="gray", bg="#f1f1f1")
            return
        for fac in ("KC Washing Plant", "Windy Washing LTD"):
            status, rows, note = _ec_lookup(state["data"], fac, name, size, code, fuzzy=fuzzy)
            text, color = _EC_VERDICT[status]
            lbl_v[fac].config(text=f"{fac}:  {text}   |   {note}", fg=color, bg="#f7f7f7")
            want = _norm_size(size)
            for e in rows[:400]:
                is_hit = status == "FOUND" and (not want or e["ns"] == want)
                tags = (("hit",) if is_hit else ()) + (("zero",) if (e["phys"] or 0) <= 0 else ())
                res = ("✔ EXACT" if (is_hit and want) else "same product" if status in ("FOUND", "SIZE_MISSING") else "similar / code")
                if (e["phys"] or 0) <= 0:
                    res += "  (zero stock)"
                tree.insert("", "end", values=(fac, e["sl"], e["code"], e["name"], e["size"], f"{e['erp']:g}", f"{e['phys']:g}", res), tags=tags)

    def reload_data():
        state["data"] = _ec_load()
        run_check(True)

    def check_list_from_file():
        path = filedialog.askopenfilename(parent=win, title="Select list to check (Excel / CSV: Item Name, Size, ERP Code)",
                                          filetypes=[("Excel & CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")])
        if not path:
            return
        try:
            df = pd.read_csv(path, dtype=object) if path.lower().endswith(".csv") else pd.read_excel(path, sheet_name=0, dtype=object)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read the file: {e}", parent=win)
            return
        c_name = _find_col(df, ["item name", "item_name", "description", "product name", "item", "product"])
        c_size = _find_col(df, ["size", "item size", "product size", "sizes"])
        c_code = _find_col(df, ["erp code", "erp_code", "prod_id", "product code", "item code", "code"])
        if not c_name and not c_code:
            messagebox.showerror("Format Error", "Item Name or ERP Code column is required.", parent=win)
            return
        out, counts = [], {}
        for _, row in df.iterrows():
            name = _txt(row[c_name]) if c_name else ""
            size = _txt(row[c_size]) if c_size else ""
            code = _txt(row[c_code]) if c_code else ""
            if not name and _is_blank_code(code):
                continue
            rec = {"Item Name": name, "Size": size, "ERP Code": code}
            for tag, fac in (("KC", "KC Washing Plant"), ("Windy", "Windy Washing LTD")):
                status, rows, note = _ec_lookup(state["data"], fac, name, size, code, fuzzy=True)
                hit = next((e for e in rows if status == "FOUND" and (not size or e["ns"] == _norm_size(size))), None)
                rec[f"{tag} Result"] = _EC_VERDICT[status][0].replace("✔ ", "").replace("⚠ ", "").replace("✘ ", "").replace("≈ ", "")
                rec[f"{tag} SL No"] = hit["sl"] if hit else ""
                rec[f"{tag} ERP Code (system)"] = hit["code"] if hit else ""
                rec[f"{tag} Physical Stock"] = hit["phys"] if hit else ""
                rec[f"{tag} ERP Stock"] = hit["erp"] if hit else ""
                rec[f"{tag} Note"] = note
                counts[(tag, status)] = counts.get((tag, status), 0) + 1
            out.append(rec)
        if not out:
            messagebox.showinfo("Check List", "No rows found in the file.", parent=win)
            return
        save = filedialog.asksaveasfilename(parent=win, defaultextension=".xlsx", initialfile="ERP_Match_Check_Result.xlsx", filetypes=[("Excel Files", "*.xlsx")])
        if not save:
            return
        try:
            pd.DataFrame(out).to_excel(save, index=False)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save result: {e}", parent=win)
            return

        def n(tag, st_):
            return counts.get((tag, st_), 0)
        messagebox.showinfo("Check List Result",
                            f"Checked {len(out)} rows.\n\nKC Washing: found {n('KC', 'FOUND')} | size missing {n('KC', 'SIZE_MISSING')} | "
                            f"similar/code {n('KC', 'SIMILAR') + n('KC', 'CODE_MATCH')} | NOT found {n('KC', 'NOT_FOUND')}\n"
                            f"Windy Washing: found {n('Windy', 'FOUND')} | size missing {n('Windy', 'SIZE_MISSING')} | "
                            f"similar/code {n('Windy', 'SIMILAR') + n('Windy', 'CODE_MATCH')} | NOT found {n('Windy', 'NOT_FOUND')}\n\nSaved: {save}", parent=win)

    bar = tk.Frame(top, bg="white")
    bar.pack(side="right")
    tk.Button(bar, text="🔍 Check", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: run_check(True)).pack(side="left", padx=2)
    tk.Button(bar, text="📋 Check List from Excel", bg="#2b6cb0", fg="white", font=("Arial", 8, "bold"), command=check_list_from_file).pack(side="left", padx=2)
    tk.Button(bar, text="🔄 Reload", bg="#718096", fg="white", font=("Arial", 8, "bold"), command=reload_data).pack(side="left", padx=2)


btn_erp_check = tk.Button(inv_top_action_bar, text="🔎 ERP Match & Check", bg="#6b46c1", fg="white", font=("Arial", 9, "bold"), command=lambda: open_erp_match_check())
btn_erp_check.pack(side="left", padx=5)


def export_inventory_report():
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, erp_status FROM inventory")
    else:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, erp_status FROM inventory WHERE factory_name=%s", (fac,))
    rows = cursor.fetchall()

    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx"), ("PDF Document", "*.pdf")])
    if not file_path:
        return
    try:
        if file_path.endswith('.xlsx'):
            data_list = []
            for r in rows:
                f_name, sl, p_id, name, size, dept, cat, erp_stk, phys_stk, price, stat = r
                var_qty = phys_stk - erp_stk
                data_list.append({
                    "Factory": f_name, "SL No": sl, "ERP Code": p_id, "Item Name": name, "Size": size,
                    "Department": dept, "Category": cat, "ERP Stock": erp_stk, "Physical Stock": phys_stk,
                    "Variance Qty": var_qty, "Unit Price": price, "ERP Value": erp_stk * price,
                    "Physical Value": phys_stk * price, "Variance Value": var_qty * price, "ERP Status": stat
                })
            pd.DataFrame(data_list).to_excel(file_path, index=False)
            messagebox.showinfo("Success", f"Inventory Report exported to Excel successfully!\nPath: {file_path}")
        elif file_path.endswith('.pdf'):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("========================================================================\n")
                f.write(f"       INVENTORY REPORT & VARIANCE: {fac}\n")
                f.write("========================================================================\n")
                f.write(f"Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}\n")
                f.write("------------------------------------------------------------------------\n\n")
                for r in rows:
                    f_name, sl, p_id, name, size, dept, cat, erp_stk, phys_stk, price, stat = r
                    var_qty = phys_stk - erp_stk
                    f.write(f"Fac: {f_name} | Code: {p_id} | Item: {name} [{size}]\n")
                    f.write(f"ERP Stock: {erp_stk} | Physical: {phys_stk} | Variance: {var_qty} | Var Value: {var_qty * price:,.2f} BDT\n")
                    f.write("-" * 70 + "\n")
            messagebox.showinfo("Success", f"Inventory Report exported to PDF successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export inventory report: {e}")


btn_export_inv = tk.Button(inv_top_action_bar, text="📥 Export Inventory Report", bg="#b71c1c", fg="white", font=("Arial", 9, "bold"), command=lambda: export_inventory_report())
btn_export_inv.pack(side="right", padx=5)

inv_summary_frame = tk.Frame(inv_frame, bg="#f8f9fa", padx=5, pady=5, relief="groove", bd=1)
inv_summary_frame.pack(fill="x", pady=(0, 5))

lbl_inv_summary = tk.Label(inv_summary_frame, text="Total Items: 0 | ERP Value: 0.00 BDT | Physical Value: 0.00 BDT | Variance Value: 0.00 BDT", font=("Arial", 9, "bold"), bg="#f8f9fa", fg="#1b3b6f")
lbl_inv_summary.pack(anchor="w", padx=5, pady=2)

# Inventory search bar
inv_search_var = tk.StringVar()
inv_search_bar = tk.Frame(inv_frame, bg="white")
inv_search_bar.pack(fill="x", pady=(0, 3))
tk.Label(inv_search_bar, text="Search (Item / Size / ERP Code / Dept / Category):", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(2, 4))
inv_search_entry = tk.Entry(inv_search_bar, textvariable=inv_search_var, width=34, font=("Arial", 9))
inv_search_entry.pack(side="left", padx=(0, 4))
tk.Button(inv_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: refresh_data()).pack(side="left", padx=2)
tk.Button(inv_search_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 8, "bold"),
          command=lambda: (inv_search_var.set(""), refresh_data())).pack(side="left", padx=2)
inv_search_entry.bind("<Return>", lambda e: refresh_data())
INV_STOCK_FILTERS = ["All Items (incl. Zero Stock)", "Zero / No Stock Only", "In Stock Only (> 0)", "Items without Size"]
inv_stock_filter_var = tk.StringVar(value=INV_STOCK_FILTERS[0])
tk.Label(inv_search_bar, text="  Show:", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(8, 2))
inv_stock_filter_combo = ttk.Combobox(inv_search_bar, textvariable=inv_stock_filter_var, values=INV_STOCK_FILTERS, width=26, state="readonly")
inv_stock_filter_combo.pack(side="left", padx=2)
inv_stock_filter_combo.bind("<<ComboboxSelected>>", lambda e: refresh_data())

inv_sub_notebook = ttk.Notebook(inv_frame)
inv_sub_notebook.pack(fill="both", expand=True, pady=(2, 0))

sub_tab_all = ttk.Frame(inv_sub_notebook)
sub_tab_pending = ttk.Frame(inv_sub_notebook)
sub_tab_queue = ttk.Frame(inv_sub_notebook)

inv_sub_notebook.add(sub_tab_all, text="📋 All Master Inventory")
inv_sub_notebook.add(sub_tab_pending, text="⏳ ERP PO Pending Items")
inv_sub_notebook.add(sub_tab_queue, text="📥 Unmatch / Import Queue")

columns_inv = ("Factory", "SL No", "ERP Code", "Item Name", "Size", "Department", "Category", "ERP Stock Qty", "Physical Stock Qty", "Stock Variance Qty", "Unit Price (BDT)", "ERP Stock Value", "Physical Value", "Variance Value", "ERP Status")
tree_inv = ttk.Treeview(sub_tab_all, columns=columns_inv, show="headings", height=13)
col_widths_inv = [110, 45, 85, 150, 70, 110, 140, 75, 75, 75, 85, 95, 95, 85, 100]
for col, w in zip(columns_inv, col_widths_inv):
    tree_inv.heading(col, text=col)
    align = "w" if col in ("Item Name", "Category", "Department", "Factory", "ERP Status", "Size") else "e"
    tree_inv.column(col, width=w, anchor=align, stretch=True)
tree_inv.pack(fill="both", expand=True, side="left", pady=(2, 0))

inv_scrollbar = ttk.Scrollbar(sub_tab_all, orient="vertical", command=tree_inv.yview)
inv_scrollbar.pack(side="right", fill="y", pady=(2, 0))
tree_inv.configure(yscrollcommand=inv_scrollbar.set)

columns_pending = ("Factory", "SL No", "ERP Code", "Item Name", "Size", "Department", "Category", "ERP Stock Qty", "Physical Stock Qty", "Unit Price (BDT)", "ERP Status")
tree_pending = ttk.Treeview(sub_tab_pending, columns=columns_pending, show="headings", height=13)
col_widths_pending = [110, 45, 90, 200, 70, 110, 140, 90, 90, 95, 100]
for col, w in zip(columns_pending, col_widths_pending):
    tree_pending.heading(col, text=col)
    align = "w" if col in ("Item Name", "Category", "Department", "Factory", "ERP Status", "Size") else "e"
    tree_pending.column(col, width=w, anchor=align, stretch=True)
tree_pending.pack(fill="both", expand=True, side="left", pady=(2, 0))

pending_scrollbar = ttk.Scrollbar(sub_tab_pending, orient="vertical", command=tree_pending.yview)
pending_scrollbar.pack(side="right", fill="y", pady=(2, 0))
tree_pending.configure(yscrollcommand=pending_scrollbar.set)

columns_queue = ("Queue ID", "Factory", "SL No", "ERP Code", "Item Name", "Size", "Department", "Category", "ERP Stock", "Physical Stock", "Unit Price", "Status")
tree_queue = ttk.Treeview(sub_tab_queue, columns=columns_queue, show="headings", height=13)
col_widths_queue = [65, 110, 45, 90, 180, 70, 110, 130, 80, 80, 85, 100]
for col, w in zip(columns_queue, col_widths_queue):
    tree_queue.heading(col, text=col)
    align = "w" if col in ("Item Name", "Category", "Department", "Factory", "Status", "Size") else "e"
    tree_queue.column(col, width=w, anchor=align, stretch=True)
tree_queue.tag_configure("approved", background="#e8f5e9")
tree_queue.tag_configure("nosize", background="#fff8e1")
tree_queue.pack(fill="both", expand=True, side="left", pady=(2, 0))

queue_scrollbar = ttk.Scrollbar(sub_tab_queue, orient="vertical", command=tree_queue.yview)
queue_scrollbar.pack(side="right", fill="y", pady=(2, 0))
tree_queue.configure(yscrollcommand=queue_scrollbar.set)


def edit_queue_item():
    """Edit an unmatched item before it is approved (name, size, ERP code, stock, price)."""
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot edit queue items!")
        return
    sel = tree_queue.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item from the Import Queue first!")
        return
    q_id = tree_queue.item(sel[0], "values")[0]
    cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, department, category, erp_stock, current_stock, unit_price, status, COALESCE(size,'') FROM import_queue WHERE id=%s", (q_id,))
    q = cursor.fetchone()
    if not q:
        return
    if q[9] == "Approved":
        messagebox.showinfo("Already Approved", "This item is already approved and saved in Master Inventory.\nUse '✏️ Edit Selected Item (Manager)' in the Master Inventory tab to change it.")
        return

    win = tk.Toplevel(root)
    win.title(f"Edit Queue Item - {q[3]}")
    win.geometry("450x620")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text="Edit Unmatched Item (before approval)", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    e_code = make_field(win, "ERP Code / Product ID (N/A = add later):", "" if q[2] in (None, "N/A") else q[2], 40)
    e_name = make_field(win, "Item Name:", q[3] or "", 40)
    e_size = make_field(win, "Size (mandatory before approval):", q[10] or "", 40)
    tk.Label(win, text="Department:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=25, pady=(6, 1))
    e_dept = ttk.Combobox(win, values=["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"], width=38)
    e_dept.pack(anchor="w", padx=25)
    e_dept.set(q[4] or "Maintenance")
    e_cat = make_field(win, "Category:", q[5] or "", 40)
    e_erp = make_field(win, "ERP Stock:", f"{(q[6] or 0):g}", 20)
    e_phys = make_field(win, "Physical Stock:", f"{(q[7] or 0):g}", 20)
    e_price = make_field(win, "Unit Price (BDT):", f"{(q[8] or 0):g}", 20)

    def save():
        try:
            erp_v = float(e_erp.get().strip() or 0)
            phys_v = float(e_phys.get().strip() or 0)
            price_v = float(e_price.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Error", "Stock and price must be numbers!", parent=win)
            return
        name = e_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Item Name is required!", parent=win)
            return
        try:
            cursor.execute("""UPDATE import_queue SET prod_id=%s, item_name=%s, size=%s, department=%s, category=%s, erp_stock=%s, current_stock=%s, unit_price=%s
                              WHERE id=%s""", (e_code.get().strip() or "N/A", name, e_size.get().strip(), e_dept.get().strip(), e_cat.get().strip(),
                                              erp_v, phys_v, price_v, q_id))
            _audit("EDIT_QUEUE", f"Queue ID {q_id} edited: {name} [{e_size.get().strip()}]")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to save: {e}", parent=win)
            return
        win.destroy()
        refresh_data()

    tk.Button(win, text="Save Changes", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=14)


def approve_queue_item():
    """Approve an unmatched item into Master Inventory (size required). The item is also created in the other unit."""
    if not require_login():
        return
    if current_user_role.get() in ["Auditor", "Store Officer"]:
        messagebox.showerror("Permission Denied", "Store Manager approval required to approve queued items into Master Inventory!")
        return
    sel = tree_queue.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item from the Import Queue to approve!")
        return
    if not ask_manager_password("Enter Store Manager Password to Approve Item:"):
        messagebox.showerror("Access Denied", "Incorrect Password!")
        return

    q_id = tree_queue.item(sel[0], "values")[0]
    cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, department, category, erp_stock, current_stock, unit_price, status, COALESCE(size,'') FROM import_queue WHERE id=%s", (q_id,))
    q_data = cursor.fetchone()
    if not q_data:
        return
    fac, sl, p_id, name, dept, cat, erp_s, curr_s, price, status, size = q_data
    if status == "Approved":
        messagebox.showinfo("Info", "This item is already approved.")
        return
    if not (size or "").strip():
        messagebox.showerror("Size Required", "Size is mandatory. Please press 'Edit' and enter the Size first.")
        return
    if p_id in (None, "", "N/A", "NA", "-"):
        p_id = _next_temp_code(fac)
    if _item_exists(fac, name, size):
        messagebox.showerror("Duplicate", f"'{name}' with size '{size}' already exists in Master Inventory of {fac}.")
        return
    cursor.execute("SELECT 1 FROM inventory WHERE prod_id=%s AND factory_name=%s", (p_id, fac))
    if cursor.fetchone():
        messagebox.showerror("Duplicate", f"ERP Code '{p_id}' already exists in Master Inventory of {fac}. Edit the queue item code first.")
        return
    cursor.execute("SELECT 1 FROM inventory WHERE sl_no=%s AND factory_name=%s", (sl, fac))
    if cursor.fetchone():
        sl = _queue_next_sl(fac)
    try:
        cursor.execute("""
            INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category, erp_stock, current_stock, unit_price, erp_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'ERP Pending')
        """, (sl, p_id, fac, name, size, dept, cat, erp_s, curr_s, price))
        cursor.execute("UPDATE import_queue SET status='Approved', sl_no=%s, prod_id=%s WHERE id=%s", (sl, p_id, q_id))
        mirrored = _mirror_to_other(fac, p_id, name, size, dept, cat, price)
        _audit("APPROVE_QUEUE", f"Approved {name} [{size}] [{p_id}] into {fac}" + (" + copied to other unit" if mirrored else ""))
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Approval failed and was rolled back: {e}")
        return
    messagebox.showinfo("Success", f"Item [{name}] approved and moved to Master Inventory!" + ("\nIt was also created in the other unit." if mirrored else ""))
    refresh_data()


def delete_queue_item():
    """Manager: delete a pending (not yet approved) queue row."""
    if not require_login():
        return
    if current_user_role.get() in ["Auditor", "Store Officer"]:
        messagebox.showerror("Permission Denied", "Only Store Manager can delete queue items!")
        return
    sel = tree_queue.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item from the Import Queue to delete!")
        return
    q_id, name = tree_queue.item(sel[0], "values")[0], tree_queue.item(sel[0], "values")[4]
    cursor.execute("SELECT status FROM import_queue WHERE id=%s", (q_id,))
    r = cursor.fetchone()
    if not r:
        return
    if r[0] == "Approved":
        messagebox.showinfo("Not Allowed", "Approved rows are kept as history. Only pending rows can be deleted.")
        return
    if not ask_manager_password("Enter Store Manager Password to delete this queue item:"):
        messagebox.showerror("Access Denied", "Incorrect Password!")
        return
    if not messagebox.askyesno("Confirm Delete", f"Delete '{name}' from the Import Queue?"):
        return
    try:
        cursor.execute("DELETE FROM import_queue WHERE id=%s", (q_id,))
        _audit("DELETE_QUEUE", f"Deleted queue ID {q_id}: {name}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to delete: {e}")
        return
    refresh_data()


btn_approve_q = tk.Button(sub_tab_queue, text="✔️ Approve Selected Item to Master Inventory", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: approve_queue_item())
btn_approve_q.pack(side="bottom", fill="x", pady=2)
btn_delete_q = tk.Button(sub_tab_queue, text="🗑️ Delete Selected Queue Item (Manager)", bg="#c53030", fg="white", font=("Arial", 9, "bold"), command=lambda: delete_queue_item())
btn_delete_q.pack(side="bottom", fill="x", pady=2)
btn_edit_q = tk.Button(sub_tab_queue, text="✏️ Edit Selected Unmatched Item (Name / Size / ERP Code)", bg="#d97706", fg="white", font=("Arial", 9, "bold"), command=lambda: edit_queue_item())
btn_edit_q.pack(side="bottom", fill="x", pady=2)


def _delete_inventory_item(fac, sl, p_id, name):
    """Deletes one master inventory item (manager password must be checked by the caller)."""
    if messagebox.askyesno("Manager Inventory Action", f"Selected Item: {name} [{p_id}] in {fac}\n\nDo you want to DELETE this item?"):
        cursor.execute("DELETE FROM inventory WHERE sl_no=%s AND prod_id=%s AND factory_name=%s", (sl, p_id, fac))
        _audit("DELETE_INVENTORY", f"Deleted {name} [{p_id}] from {fac}")
        conn.commit()
        messagebox.showinfo("Success", "Inventory item deleted successfully by Manager!")
        refresh_data()


def inventory_manager_action(event=None):
    selected_item = tree_inv.selection()
    if not selected_item:
        messagebox.showerror("Selection Error", "Please select an item from Master Inventory first!")
        return
    if not require_login():
        return
    if not ask_manager_password("Enter Store Manager Password to Delete Inventory:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can modify inventory.")
        return
    item_vals = tree_inv.item(selected_item[0], "values")
    _delete_inventory_item(item_vals[0], item_vals[1], item_vals[2], item_vals[3])


tree_inv.bind("<Button-3>", inventory_manager_action)

# ================= TAB 3: ERP AUDIT =================
audit_frame = tk.Frame(tab_audit, bg="white", padx=5, pady=5)
audit_frame.pack(fill="both", expand=True)

audit_top_summary_frame = tk.Frame(audit_frame, bg="#e8f4fd", padx=5, pady=5, relief="groove", bd=1)
audit_top_summary_frame.pack(fill="x", pady=(0, 4))

lbl_audit_main_summary = tk.Label(audit_top_summary_frame, text="Total Mismatched: 0 | Short Items: 0 | Excess Items: 0 | Short Value: 0.00 BDT | Excess Value: 0.00 BDT | Open Tasks: 0 | Unmatch Pending: 0",
                                  font=("Arial", 9, "bold"), bg="#e8f4fd", fg="#0d47a1")
lbl_audit_main_summary.pack(anchor="w")

lbl_audit_formula = tk.Label(audit_top_summary_frame,
                             text="Formula:  Variance Qty = Physical (Current) Stock − ERP Balance   |   Negative = Short   |   Positive = Excess   |   Value = Variance Qty × Unit Price   |   ERP codes not found in Master go to Unmatch Queue",
                             font=("Arial", 8, "italic"), bg="#e8f4fd", fg="#2c5282")
lbl_audit_formula.pack(anchor="w")

audit_action_bar = tk.Frame(audit_frame, bg="white")
audit_action_bar.pack(fill="x", pady=2)


def download_erp_format():
    df = pd.DataFrame([{"ERP Code": "ERP-0001", "Item Name": "Example Item", "Size": "XL (mandatory)", "ERP Balance": 10}])
    _save_template(df, "ERP_Balance_Format")


def import_erp_balance_excel():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot import ERP balance!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error", "Please select a specific factory before importing ERP Balance!")
        return
    file_path = filedialog.askopenfilename(
        title=f"Select ERP Balance Excel/CSV for {fac}",
        filetypes=[("Excel & CSV Files", "*.xlsx *.xls *.csv"), ("All Files", "*.*")],
    )
    if not file_path:
        return

    backup_path = f"windy_store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        _backup_database(backup_path)
    except Exception as e:
        messagebox.showwarning("Backup Warning", f"Could not create backup: {e}")

    try:
        if file_path.lower().endswith('.csv'):
            df = pd.read_csv(file_path, dtype=object)
        else:
            df = pd.read_excel(file_path, sheet_name=0, dtype=object)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to read the file: {e}")
        return

    c_code = _find_col(df, ["erp code", "erp_code", "prod_id", "product code", "item code", "code"])
    c_name = _find_col(df, ["item name", "item_name", "description", "product name", "item"])
    c_size = _find_col(df, ["size", "item size", "product size", "sizes"])
    c_bal = _find_col(df, ["erp balance", "erp_balance", "erp stock", "erp_stock", "balance", "qty", "stock"])
    if not c_bal:
        messagebox.showerror("Format Error", "'ERP Balance' column not found.\n\n"
                                             f"Columns found: {', '.join(str(c) for c in df.columns)}\n\n"
                                             "Click '📄 ERP Import Format' to get the correct layout.")
        return
    if not c_code and not c_name:
        messagebox.showerror("Format Error", "ERP Code or Item Name column is required.")
        return

    matched = queued = dup = skipped = 0
    matched_sl = set()
    queued_names = []
    try:
        idx = _load_inv_index(fac)
        for _, row in df.iterrows():
            code = _txt(row[c_code]) if c_code else ""
            name = _txt(row[c_name]) if c_name else ""
            size = _txt(row[c_size]) if c_size else ""
            bal = _num_blank0(row[c_bal])          # blank balance = 0 (zero balance item in ERP)
            if (_is_blank_code(code) and not name) or bal is None:
                skipped += 1
                continue
            e = _idx_find(idx, code, name, size)
            if e:
                new_size = size if (size and not e["ns"]) else None
                cursor.execute("UPDATE inventory SET erp_stock=%s, size=COALESCE(%s, size) WHERE sl_no=%s AND factory_name=%s", (bal, new_size, e["sl"], fac))
                if new_size:
                    e["size"], e["ns"] = new_size, _norm_size(new_size)
                    _idx_reindex(idx, e)
                matched += 1
                matched_sl.add(e["sl"])
            else:
                if _queue_add(fac, code or "N/A", name or code, "Maintenance", "Uncategorized (Edit Later)", bal, 0.0, 0.0, size):
                    queued += 1
                    queued_names.append(f"{name or code} [{size or 'NO SIZE'}]")
                else:
                    dup += 1
        cursor.execute("SELECT COUNT(*) FROM inventory WHERE factory_name=%s", (fac,))
        not_in_erp = cursor.fetchone()[0] - len(matched_sl)
        _audit("IMPORT_ERP_BALANCE", f"{fac}: matched {matched}, unmatched queued {queued} from {os.path.basename(file_path)}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Failed to import ERP balance (rolled back): {e}")
        return

    preview = ""
    if queued_names:
        preview = "\n\nIn ERP but NOT in Master (Unmatch Queue – approve after checking):\n- " + "\n- ".join(queued_names[:10])
        if len(queued_names) > 10:
            preview += f"\n... and {len(queued_names) - 10} more"
    messagebox.showinfo("ERP Balance Import Summary",
                        f"ERP Balance import completed for {fac}!\n\n"
                        f"- ERP balance matched & updated: {matched}\n"
                        f"- Sent to Unmatch Queue: {queued}\n"
                        f"- Already waiting in queue: {dup}\n"
                        f"- Skipped (blank / invalid rows): {skipped}\n"
                        f"- Master items NOT in this ERP file (ERP balance unchanged): {not_in_erp}\n\n"
                        f"Backup: {backup_path}{preview}")
    refresh_data()


def mark_erp_done_selected():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot modify ERP status!")
        return
    sel = tree_audit_all.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item from the audit list!")
        return
    item_vals = tree_audit_all.item(sel[0], "values")
    fac, p_id = item_vals[0], item_vals[2]
    cursor.execute("UPDATE inventory SET erp_status='ERP GRN Done' WHERE prod_id=%s AND factory_name=%s", (p_id, fac))
    _audit("ERP_STATUS_DONE", f"{fac}: {p_id} marked ERP GRN Done")
    conn.commit()
    messagebox.showinfo("Success", f"ERP Status updated to 'ERP GRN Done' for Product Code: {p_id}!")
    refresh_data()


def assign_correction_task_popup():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot assign correction tasks!")
        return
    sel = tree_audit_all.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a mismatched item from Audit list!")
        return
    item_vals = tree_audit_all.item(sel[0], "values")
    fac, p_id, name, v_qty, v_type = item_vals[0], item_vals[2], item_vals[3], item_vals[6], item_vals[11]
    if v_type == "Matched":
        messagebox.showinfo("Info", "Selected item is already Matched! No correction task needed.")
        return
    v_val_txt = item_vals[8] if v_type == "Shortage" else item_vals[9]
    try:
        v_val = float(str(v_val_txt).replace(" BDT", "").replace(",", "") or 0)
    except ValueError:
        v_val = 0.0

    win = tk.Toplevel(root)
    win.title(f"Assign Stock Correction Task - [{p_id}]")
    win.geometry("450x450")
    win.config(bg="white")

    tk.Label(win, text=f"Item: {name}\nFactory: {fac} | Variance: {v_qty} [{v_type}]", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f").pack(pady=10)

    tk.Label(win, text="Assigned Store Officer:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    c_off = ttk.Combobox(win, values=["Officer_Sagor", "Officer_Rahim", "Manager Admin"], width=35, state="readonly")
    c_off.pack(padx=30)
    c_off.current(0)

    tk.Label(win, text="Correction Deadline:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    c_dead = ttk.Combobox(win, values=["1 Day", "2 Days", "3 Days", "7 Days", "15 Days", "Custom Date"], width=35, state="readonly")
    c_dead.pack(padx=30)
    c_dead.current(1)

    tk.Label(win, text="Priority:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    c_prio = ttk.Combobox(win, values=["Critical", "High", "Medium", "Low"], width=35, state="readonly")
    c_prio.pack(padx=30)
    c_prio.current(1)

    tk.Label(win, text="Root Cause / Remarks:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=30, pady=2)
    e_rem = tk.Entry(win, width=37, font=("Arial", 9))
    e_rem.pack(padx=30)
    e_rem.insert(0, "Physical recount and verification required")

    def save_task():
        t_date = datetime.now().strftime('%d-%m-%Y')
        try:
            cursor.execute("""
                INSERT INTO audit_correction_tasks (factory_name, prod_id, item_name, variance_type, variance_qty, variance_value, root_cause, corrective_action, assigned_officer, task_date, target_date, status, manager_remarks, priority, verification_status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'In Progress', %s, %s, 'Pending')
            """, (fac, p_id, name, v_type, float(v_qty), v_val, e_rem.get(), "Verify physical count & documents",
                  c_off.get(), t_date, c_dead.get(), e_rem.get(), c_prio.get()))
            _audit("ASSIGN_TASK", f"{fac}: correction task for {name} [{p_id}] assigned to {c_off.get()}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to assign task: {e}", parent=win)
            return
        messagebox.showinfo("Success", "Stock Correction Task assigned successfully!")
        win.destroy()
        refresh_data()

    tk.Button(win, text="Assign Task", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=20, command=save_task).pack(pady=20)


def export_audit_report():
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, unit_price, erp_status, COALESCE(size,'') FROM inventory")
    else:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, unit_price, erp_status, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (fac,))
    rows = cursor.fetchall()

    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx"), ("PDF Document", "*.pdf")])
    if not file_path:
        return
    try:
        if file_path.endswith('.xlsx'):
            data_list = []
            for f_name, sl, p_id, name, erp_stk, curr_stk, price, erp_stat, size in rows:
                price = price if price else 0.0
                variance = curr_stk - erp_stk
                var_val = variance * price
                data_list.append({
                    "Factory": f_name, "SL No": sl, "ERP Code": p_id, "Item Name": name, "Size": size,
                    "ERP Stock": erp_stk, "Physical Stock": curr_stk, "Variance Qty": variance,
                    "Unit Price": price, "Shortage Value": abs(var_val) if variance < 0 else 0.0,
                    "Excess Value": var_val if variance > 0 else 0.0,
                    "ERP Status": erp_stat, "Variance Type": "Shortage" if variance < 0 else ("Excess" if variance > 0 else "Matched")
                })
            pd.DataFrame(data_list).to_excel(file_path, index=False)
            messagebox.showinfo("Success", f"Audit Report exported to Excel successfully!\nPath: {file_path}")
        elif file_path.endswith('.pdf'):
            with open(file_path, "w", encoding="utf-8") as f:
                f.write("========================================================================\n")
                f.write("       ERP VS PHYSICAL AUDIT & CORRECTION REPORT\n")
                f.write("========================================================================\n")
                f.write(f"Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}\n")
                f.write("------------------------------------------------------------------------\n\n")
                for f_name, sl, p_id, name, erp_stk, curr_stk, price, erp_stat, size in rows:
                    f.write(f"Fac: {f_name} | Code: {p_id} | Item: {name} [{size}] | Var: {curr_stk - erp_stk}\n")
            messagebox.showinfo("Success", f"Audit Report exported to PDF successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export audit report: {e}")


btn_import_erp_bal = tk.Button(audit_action_bar, text="📥 Import ERP Balance", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: import_erp_balance_excel())
btn_import_erp_bal.pack(side="left", padx=2)

btn_erp_fmt = tk.Button(audit_action_bar, text="📄 ERP Import Format", bg="#2b6cb0", fg="white", font=("Arial", 8, "bold"), command=lambda: download_erp_format())
btn_erp_fmt.pack(side="left", padx=2)

btn_erp_done = tk.Button(audit_action_bar, text="✔️ Mark ERP GRN Done", bg="#2e7d32", fg="white", font=("Arial", 8, "bold"), command=lambda: mark_erp_done_selected())
btn_erp_done.pack(side="left", padx=5)

btn_assign_task = tk.Button(audit_action_bar, text="📋 Assign Correction Task", bg="#d69e2e", fg="white", font=("Arial", 8, "bold"), command=lambda: assign_correction_task_popup())
btn_assign_task.pack(side="left", padx=5)

btn_export_audit = tk.Button(audit_action_bar, text="📥 Export Audit & Correction Excel/PDF", bg="#b71c1c", fg="white", font=("Arial", 8, "bold"), command=lambda: export_audit_report())
btn_export_audit.pack(side="right", padx=5)


# ----- Adjust / Edit / Delete actions for the audit slides -----
def _active_audit_tree():
    """Returns the Treeview of the audit sub-tab that is currently open."""
    try:
        idx = audit_sub_notebook.index(audit_sub_notebook.select())
    except tk.TclError:
        return None
    return {0: tree_audit_all, 1: tree_audit_short, 2: tree_audit_excess, 3: tree_audit_matched,
            4: tree_audit_pending, 5: tree_audit_plan, 6: tree_audit_closed, 7: tree_aging}.get(idx)


def audit_adjust_variance():
    """Adjusts a Short / Excess item so that the Physical stock moves toward ERP. Creates a Stock Adjustment record."""
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot adjust stock!")
        return
    tree = _active_audit_tree()
    if tree not in (tree_audit_all, tree_audit_short, tree_audit_excess, tree_audit_pending, tree_audit_matched):
        messagebox.showinfo("Select Item", "Open an inventory audit tab (All / Short / Excess / Pending) and select an item.")
        return
    sel = tree.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select an item first!")
        return
    vals = tree.item(sel[0], "values")
    fac, sl, code = vals[0], vals[1], vals[2]
    cursor.execute("SELECT sl_no, current_stock, erp_stock, item_name FROM inventory WHERE sl_no=%s AND prod_id=%s AND factory_name=%s", (sl, code, fac))
    r = cursor.fetchone()
    if not r:
        messagebox.showerror("Not Found", "Item not found. Please refresh.")
        return
    _, cur, erp, name = r
    cur, erp = cur or 0.0, erp or 0.0
    variance = cur - erp
    if abs(variance) < 1e-9:
        messagebox.showinfo("Matched", "This item is already matched with ERP. No adjustment needed.")
        return
    kind = "Short" if variance < 0 else "Excess"
    if not ask_manager_password("Enter Store Manager Password to adjust variance:"):
        messagebox.showerror("Access Denied", "Incorrect Password!")
        return
    q_txt = simpledialog.askstring("Adjust Variance",
                                   f"{name}\n{kind} by {abs(variance):g}.\n\nEnter adjustment qty (1 to {abs(variance):g}).\n"
                                   "Use the full amount to match ERP, or a partial amount.",
                                   initialvalue=f"{abs(variance):g}", parent=root)
    if q_txt is None:
        return
    try:
        q = float(q_txt.strip())
        if q <= 0 or q > abs(variance) + 1e-9:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", f"Enter a number between 0 and {abs(variance):g}.")
        return
    if variance < 0:
        trans_type, new_cur = "Stock Adjustment (+)", cur + q
    else:
        trans_type, new_cur = "Stock Adjustment (-)", cur - q
    now = datetime.now()
    try:
        cursor.execute("UPDATE inventory SET current_stock=%s WHERE sl_no=%s AND factory_name=%s", (new_cur, sl, fac))
        _insert_transaction(fac, current_authenticated_user.get(), sl, code, name, q, trans_type, now.day,
                            f"ERP variance adjustment ({kind} {abs(variance):g}, adjusted {q:g})",
                            now.strftime("%d-%b-%Y"), now.strftime("%I:%M %p"), "Verified", "Not Required")
        _audit("ADJUST_VARIANCE", f"{fac}: {name} [{code}] {kind} adjusted by {q:g}; stock {cur:g} -> {new_cur:g}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Adjustment failed and was rolled back: {e}")
        return
    messagebox.showinfo("Success", f"Variance adjusted by {q:g}. Current stock is now {new_cur:g}.")
    refresh_data()


def audit_edit_selected():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access!")
        return
    tree = _active_audit_tree()
    if tree is None:
        return
    sel = tree.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a row first!")
        return
    vals = tree.item(sel[0], "values")
    if tree in (tree_audit_plan, tree_audit_closed):
        _edit_task_popup(vals[0])
    elif tree is tree_aging:
        edit_transaction_popup(vals[0])
    else:
        if not ask_manager_password("Enter Store Manager Password to Edit Inventory Item:"):
            messagebox.showerror("Access Denied", "Incorrect Password!")
            return
        _open_edit_inventory(vals[0], vals[1], vals[2])


def audit_delete_selected():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access!")
        return
    tree = _active_audit_tree()
    if tree is None:
        return
    sel = tree.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a row first!")
        return
    vals = tree.item(sel[0], "values")
    if tree in (tree_audit_plan, tree_audit_closed):
        if not ask_manager_password("Enter Store Manager Password to delete this correction task:"):
            messagebox.showerror("Access Denied", "Incorrect Password!")
            return
        if messagebox.askyesno("Confirm", f"Delete correction task ID {vals[0]}?"):
            cursor.execute("DELETE FROM audit_correction_tasks WHERE id=%s", (vals[0],))
            _audit("DELETE_TASK", f"Deleted correction task ID {vals[0]}")
            conn.commit()
            refresh_data()
    elif tree is tree_aging:
        _delete_transaction_by_id(vals[0])
    else:
        if not ask_manager_password("Enter Store Manager Password to Delete Inventory:"):
            messagebox.showerror("Access Denied", "Incorrect Password!")
            return
        _delete_inventory_item(vals[0], vals[1], vals[2], vals[3])


btn_adjust = tk.Button(audit_action_bar, text="⚖️ Adjust Variance to ERP", bg="#805ad5", fg="white", font=("Arial", 8, "bold"), command=lambda: audit_adjust_variance())
btn_adjust.pack(side="left", padx=5)
btn_audit_edit = tk.Button(audit_action_bar, text="✏️ Edit Selected", bg="#d97706", fg="white", font=("Arial", 8, "bold"), command=lambda: audit_edit_selected())
btn_audit_edit.pack(side="left", padx=2)
btn_audit_delete = tk.Button(audit_action_bar, text="🗑️ Delete Selected", bg="#c53030", fg="white", font=("Arial", 8, "bold"), command=lambda: audit_delete_selected())
btn_audit_delete.pack(side="left", padx=2)

# ----- audit search bar -----
audit_search_var = tk.StringVar()
audit_search_bar = tk.Frame(audit_frame, bg="white")
audit_search_bar.pack(fill="x", pady=2)
tk.Label(audit_search_bar, text="Search (Item / Size / ERP Code / Factory):", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(2, 4))
audit_search_entry = tk.Entry(audit_search_bar, textvariable=audit_search_var, width=34, font=("Arial", 9))
audit_search_entry.pack(side="left", padx=(0, 4))
tk.Button(audit_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: refresh_data()).pack(side="left", padx=2)
tk.Button(audit_search_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 8, "bold"),
          command=lambda: (audit_search_var.set(""), refresh_data())).pack(side="left", padx=2)
audit_search_entry.bind("<Return>", lambda e: refresh_data())

audit_sub_notebook = ttk.Notebook(audit_frame)
audit_sub_notebook.pack(fill="both", expand=True, pady=(2, 0))

sub_audit_all = ttk.Frame(audit_sub_notebook)
sub_audit_short = ttk.Frame(audit_sub_notebook)
sub_audit_excess = ttk.Frame(audit_sub_notebook)
sub_audit_matched = ttk.Frame(audit_sub_notebook)
sub_audit_pending = ttk.Frame(audit_sub_notebook)
sub_audit_plan = ttk.Frame(audit_sub_notebook)
sub_audit_closed = ttk.Frame(audit_sub_notebook)
sub_audit_aging = ttk.Frame(audit_sub_notebook)

audit_sub_notebook.add(sub_audit_all, text="📋 All Audit Items")
audit_sub_notebook.add(sub_audit_short, text="🔴 Short Items")
audit_sub_notebook.add(sub_audit_excess, text="🟠 Excess Items")
audit_sub_notebook.add(sub_audit_matched, text="🟢 Matched Items")
audit_sub_notebook.add(sub_audit_pending, text="🟡 ERP / GRN Pending")
audit_sub_notebook.add(sub_audit_plan, text="📋 Correction Plan")
audit_sub_notebook.add(sub_audit_closed, text="✅ Corrected / Closed")
audit_sub_notebook.add(sub_audit_aging, text="⏱ Receipt Aging (ERP Gap)")

columns_audit_gen = ("Factory", "SL", "ERP Code", "Item Name", "ERP Stock", "Physical Stock", "Variance Qty", "Unit Price", "Shortage Value", "Excess Value", "ERP Status", "Variance Type")


def create_audit_tree(parent):
    tree = ttk.Treeview(parent, columns=columns_audit_gen, show="headings", height=13)
    widths = [110, 35, 80, 160, 75, 75, 75, 75, 95, 95, 95, 90]
    for col, w in zip(columns_audit_gen, widths):
        tree.heading(col, text=col)
        align = "w" if "Name" in col or "Status" in col or "Factory" in col else "e"
        tree.column(col, width=w, anchor=align, stretch=True)
    tree.pack(fill="both", expand=True, side="left", pady=(2, 0))
    sc = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    sc.pack(side="right", fill="y", pady=(2, 0))
    tree.configure(yscrollcommand=sc.set)
    return tree


tree_audit_all = create_audit_tree(sub_audit_all)
tree_audit_short = create_audit_tree(sub_audit_short)
tree_audit_excess = create_audit_tree(sub_audit_excess)
tree_audit_matched = create_audit_tree(sub_audit_matched)
tree_audit_pending = create_audit_tree(sub_audit_pending)
tree_audit_closed = create_audit_tree(sub_audit_closed)

columns_plan = ("Task ID", "Factory", "ERP Code", "Item Name", "Variance Type", "Variance Qty", "Variance Value", "Assigned Officer", "Target Deadline", "Status", "Priority", "Remarks")
tree_audit_plan = ttk.Treeview(sub_audit_plan, columns=columns_plan, show="headings", height=13)
widths_plan = [55, 110, 80, 160, 90, 70, 95, 100, 95, 95, 75, 120]
for col, w in zip(columns_plan, widths_plan):
    tree_audit_plan.heading(col, text=col)
    align = "w" if "Name" in col or "Status" in col or "Factory" in col or "Officer" in col else "e"
    tree_audit_plan.column(col, width=w, anchor=align, stretch=True)
tree_audit_plan.pack(fill="both", expand=True, side="left", pady=(2, 0))
plan_sc = ttk.Scrollbar(sub_audit_plan, orient="vertical", command=tree_audit_plan.yview)
plan_sc.pack(side="right", fill="y", pady=(2, 0))
tree_audit_plan.configure(yscrollcommand=plan_sc.set)


def _edit_task_popup(t_id):
    """Manager edit of a correction task: target date, priority and remarks."""
    cursor.execute("SELECT id, item_name, target_date, priority, manager_remarks FROM audit_correction_tasks WHERE id=%s", (t_id,))
    t = cursor.fetchone()
    if not t:
        return
    if not ask_manager_password("Enter Store Manager Password to edit this task:"):
        messagebox.showerror("Access Denied", "Incorrect Password!")
        return
    win = tk.Toplevel(root)
    win.title(f"Edit Correction Task {t[0]}")
    win.geometry("420x330")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text=f"Task {t[0]}: {t[1]}", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", wraplength=380).pack(pady=10)
    e_target = make_field(win, "Target Deadline (text, e.g. 20-Oct-2026):", t[2] or "", 30)
    tk.Label(win, text="Priority:", bg="white", font=("Arial", 8, "bold")).pack(anchor="w", padx=25, pady=(6, 1))
    c_prio = ttk.Combobox(win, values=["Critical", "High", "Medium", "Low"], width=28, state="readonly")
    c_prio.pack(anchor="w", padx=25)
    c_prio.set(t[3] or "Medium")
    e_rem = make_field(win, "Manager Remarks:", t[4] or "", 40)

    def save():
        try:
            cursor.execute("UPDATE audit_correction_tasks SET target_date=%s, priority=%s, manager_remarks=%s WHERE id=%s",
                           (e_target.get().strip(), c_prio.get(), e_rem.get().strip(), t_id))
            _audit("EDIT_TASK", f"Correction task ID {t_id} edited")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to save: {e}", parent=win)
            return
        win.destroy()
        refresh_data()

    tk.Button(win, text="Save Changes", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=20, command=save).pack(pady=14)


def manager_verify_and_close_task():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot verify correction tasks!")
        return
    sel = tree_audit_plan.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a correction task from the plan!")
        return
    if not ask_manager_password("Enter Store Manager Password to Verify & Close Task:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Manager verification required.")
        return
    t_id = tree_audit_plan.item(sel[0], "values")[0]
    cursor.execute("UPDATE audit_correction_tasks SET status='Closed', verification_status='Verified by Manager' WHERE id=%s", (t_id,))
    _audit("CLOSE_TASK", f"Correction task ID {t_id} verified and closed")
    conn.commit()
    messagebox.showinfo("Success", f"Correction Task ID {t_id} verified and closed successfully!")
    refresh_data()


btn_close_task = tk.Button(sub_audit_plan, text="✅ Verify & Close Selected Task (Manager Only)", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: manager_verify_and_close_task())
btn_close_task.pack(side="bottom", fill="x", pady=2)

# --- Receipt Aging (ERP timing gap) ---
aging_top = tk.Frame(sub_audit_aging, bg="white")
aging_top.pack(fill="x", pady=(2, 2))
tk.Label(aging_top, text="Goods received in factory but ERP PO / GRN not yet posted. Red = pending more than 7 days.",
         bg="white", fg="#744210", font=("Arial", 8, "bold")).pack(side="left", padx=4)

columns_aging = ("Tx ID", "Factory", "Receipt Date", "Item Name", "ERP Code", "Qty Received", "Officer", "Days Pending", "ERP Status")
tree_aging = ttk.Treeview(sub_audit_aging, columns=columns_aging, show="headings", height=12)
for col, w in zip(columns_aging, [55, 110, 95, 220, 90, 90, 100, 90, 160]):
    tree_aging.heading(col, text=col)
    tree_aging.column(col, width=w, anchor="e" if col in ("Tx ID", "Qty Received", "Days Pending") else "w", stretch=True)
tree_aging.tag_configure("late", background="#fde8e8")
tree_aging.pack(fill="both", expand=True, side="left", pady=(2, 0))
aging_sc = ttk.Scrollbar(sub_audit_aging, orient="vertical", command=tree_aging.yview)
aging_sc.pack(side="right", fill="y", pady=(2, 0))
tree_aging.configure(yscrollcommand=aging_sc.set)

lbl_aging_summary = tk.Label(sub_audit_aging, text="", font=("Arial", 8, "bold"), bg="white", fg="#1b3b6f", anchor="w")
lbl_aging_summary.pack(side="bottom", fill="x")


def mark_erp_grn_done():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role cannot modify ERP status!")
        return
    sel = tree_aging.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a receipt from the Receipt Aging list!")
        return
    t_id = tree_aging.item(sel[0], "values")[0]
    d_txt = simpledialog.askstring("ERP PO / GRN Date", "Date when ERP PO / GRN was posted (DD-Mon-YYYY):", initialvalue=datetime.now().strftime("%d-%b-%Y"))
    if not d_txt:
        return
    try:
        d_obj = datetime.strptime(d_txt.strip(), "%d-%b-%Y")
    except ValueError:
        messagebox.showerror("Error", "Date must be in DD-Mon-YYYY format (e.g. 12-Oct-2026).")
        return
    cursor.execute("UPDATE transactions SET erp_grn_status='Done', erp_grn_date=%s WHERE id=%s", (d_obj.strftime("%d-%b-%Y"), t_id))
    _audit("ERP_GRN_DONE", f"Receipt transaction ID {t_id} marked ERP GRN Done on {d_obj.strftime('%d-%b-%Y')}")
    conn.commit()
    messagebox.showinfo("Success", "Receipt marked as ERP GRN Done.")
    refresh_data()


btn_aging_done = tk.Button(sub_audit_aging, text="✔️ Mark ERP PO / GRN Done for Selected Receipt", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: mark_erp_grn_done())
btn_aging_done.pack(side="bottom", fill="x", pady=2)


def load_erp_aging():
    for i in tree_aging.get_children():
        tree_aging.delete(i)
    fac = selected_factory.get()
    q = "SELECT id, factory_name, date, item_name, prod_id, qty, officer_name FROM transactions WHERE trans_type='Supplier. Rec' AND erp_grn_status='Pending'"
    params = []
    if "CONSOLIDATED" not in fac:
        q += " AND factory_name=%s"
        params.append(fac)
    q += " ORDER BY id DESC"
    cursor.execute(q, params)
    today = datetime.now().date()
    total_qty, late, count = 0.0, 0, 0
    for t_id, f_name, d, name, code, qty, off in cursor.fetchall():
        try:
            days = max((today - datetime.strptime(str(d).strip(), "%d-%b-%Y").date()).days, 0)
        except ValueError:
            days = 0
        is_late = days > 7
        late += 1 if is_late else 0
        count += 1
        total_qty += qty or 0
        tree_aging.insert("", "end", values=(t_id, f_name, d, name, code, f"{(qty or 0):g}", off, f"{days} Days",
                                             "⚠ ERP pending - follow up" if is_late else "ERP pending"),
                          tags=("late",) if is_late else ())
    lbl_aging_summary.config(text=f"Receipts waiting for ERP: {count}  |  Over 7 days: {late}  |  Total qty waiting: {total_qty:g}")


# ================= TAB 4: ISSUE LEDGER =================
issue_ledger_frame = tk.Frame(tab_issue_ledger, bg="white", padx=5, pady=5)
issue_ledger_frame.pack(fill="both", expand=True)

il_top_bar = tk.Frame(issue_ledger_frame, bg="white", pady=3)
il_top_bar.pack(fill="x")
tk.Label(il_top_bar, text="Issue Ledger & Pre-ERP PO/GRN Entry Tracking Hub", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(side="left")


def export_issue_ledger():
    fac = selected_factory.get()
    base = ("SELECT t.id, t.date, t.time, t.factory_name, t.item_name, t.prod_id, t.sl_no, t.qty, i.unit_price, t.officer_name, t.trans_type, t.notes, t.verification_status "
            "FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name")
    if "CONSOLIDATED" in fac:
        cursor.execute(base)
    else:
        cursor.execute(base + " WHERE t.factory_name=%s", (fac,))
    rows = cursor.fetchall()
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel Files", "*.xlsx")])
    if file_path:
        data_list = []
        for r in rows:
            u_price = r[8] if r[8] else 0.0
            data_list.append({
                "Tx ID": r[0], "Date": r[1], "Time": r[2], "Factory": r[3], "Item Name": r[4],
                "ERP Code": r[5], "SL No": r[6], "Qty Issued": r[7], "Unit Price": u_price,
                "Total Value": (r[7] or 0) * u_price, "Officer": r[9], "Type": _tlabel(r[10]), "Notes": r[11], "ERP Status": r[12]
            })
        pd.DataFrame(data_list).to_excel(file_path, index=False)
        messagebox.showinfo("Success", f"Issue Ledger exported successfully to {file_path}")


tk.Button(il_top_bar, text="📥 Export Issue Ledger", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: export_issue_ledger()).pack(side="right", padx=5)

# --- Item-wise Monthly Issue Search (with PDF & Excel download) ---
MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
il_search_results = []
il_search_meta = {}


def get_month_options():
    options = set()
    cur_year = datetime.now().year
    for m in MONTH_NAMES:
        options.add(f"{m}-{cur_year}")
    try:
        cursor.execute("SELECT DISTINCT date FROM transactions WHERE date IS NOT NULL")
        for (d,) in cursor.fetchall():
            try:
                dt = datetime.strptime(str(d).strip(), "%d-%b-%Y")
                options.add(f"{MONTH_NAMES[dt.month - 1]}-{dt.year}")
            except ValueError:
                continue
    except Exception:
        conn.rollback()
    return sorted(options, key=lambda s: datetime.strptime(s, "%b-%Y"), reverse=True)


il_search_frame = tk.LabelFrame(issue_ledger_frame, text=" 🔍 Item-wise Monthly Issue Search ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=5, pady=4)
il_search_frame.pack(fill="x", pady=(2, 4))

il_search_bar = tk.Frame(il_search_frame, bg="white")
il_search_bar.pack(fill="x")

tk.Label(il_search_bar, text="Item Name:", font=("Arial", 8, "bold"), bg="white").pack(side="left", padx=(2, 3))
il_item_var = tk.StringVar()
il_item_entry = tk.Entry(il_search_bar, textvariable=il_item_var, width=28, font=("Arial", 9))
il_item_entry.pack(side="left", padx=(0, 10))

tk.Label(il_search_bar, text="Month Selection:", font=("Arial", 8, "bold"), bg="white").pack(side="left", padx=(2, 3))
il_month_var = tk.StringVar()
il_month_combo = ttk.Combobox(il_search_bar, textvariable=il_month_var, values=get_month_options(), width=12, state="readonly", font=("Arial", 9))
il_month_combo.pack(side="left", padx=(0, 10))
_cur_opt = f"{MONTH_NAMES[datetime.now().month - 1]}-{datetime.now().year}"
if _cur_opt in il_month_combo["values"]:
    il_month_combo.set(_cur_opt)


def search_issue_ledger(event=None):
    item_text = il_item_var.get().strip()
    month_text = il_month_var.get().strip()
    if not item_text:
        messagebox.showwarning("Input Required", "Please enter an Item Name to search!")
        return
    if not month_text:
        messagebox.showwarning("Input Required", "Please select a Month!")
        return
    try:
        sel_dt = datetime.strptime(month_text, "%b-%Y")
    except ValueError:
        messagebox.showerror("Error", "Invalid month selection!")
        return

    fac = selected_factory.get()
    query = "SELECT t.date, t.item_name, t.factory_name, t.qty FROM transactions t WHERE t.trans_type ILIKE '%%Issue%%' AND LOWER(t.item_name) ILIKE %s"
    params = [f"%{item_text.lower()}%"]
    if "CONSOLIDATED" not in fac:
        query += " AND t.factory_name = %s"
        params.append(fac)
    cursor.execute(query, params)

    grouped = {}
    for d, name, f_name, qty in cursor.fetchall():
        try:
            dt = datetime.strptime(str(d).strip(), "%d-%b-%Y")
        except ValueError:
            continue
        if dt.month == sel_dt.month and dt.year == sel_dt.year:
            key = (dt, name, f_name)
            grouped[key] = grouped.get(key, 0.0) + (qty or 0.0)

    il_search_results.clear()
    for (dt, name, f_name) in sorted(grouped.keys(), key=lambda k: (k[0], k[1], k[2])):
        il_search_results.append((dt.strftime("%d-%b-%Y"), name, f_name, grouped[(dt, name, f_name)]))
    il_search_meta.clear()
    il_search_meta.update({"item": item_text, "month": month_text, "factory": fac})

    for row_id in tree_il_search.get_children():
        tree_il_search.delete(row_id)
    total = 0.0
    for d, name, f_name, qty in il_search_results:
        tree_il_search.insert("", "end", values=(d, name, f_name, f"{qty:g}"))
        total += qty
    lbl_il_search_total.config(text=f"Total Issued Qty: {total:g}  |  Issue Days: {len(set(r[0] for r in il_search_results))}  |  Records: {len(il_search_results)}")
    if not il_search_results:
        messagebox.showinfo("No Records", f"No issue records found for '{item_text}' in {month_text}.")


def export_il_search_excel():
    if not il_search_results:
        messagebox.showwarning("No Data", "Please run a search first. There are no results to download!")
        return
    default_name = f"Issue_Search_{il_search_meta['item']}_{il_search_meta['month']}".replace(" ", "_")
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=default_name, filetypes=[("Excel Files", "*.xlsx")])
    if not file_path:
        return
    try:
        df = pd.DataFrame(il_search_results, columns=["Date", "Item Name", "Factory", "Qty Issued"])
        total_row = pd.DataFrame([{"Date": "TOTAL", "Item Name": "", "Factory": "", "Qty Issued": df["Qty Issued"].sum()}])
        pd.concat([df, total_row], ignore_index=True).to_excel(file_path, index=False)
        messagebox.showinfo("Success", f"Search result exported to Excel successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export Excel: {e}")


def export_il_search_pdf():
    if not il_search_results:
        messagebox.showwarning("No Data", "Please run a search first. There are no results to download!")
        return
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        messagebox.showerror("Missing Library", "PDF export requires the 'reportlab' library.\nInstall it with:  pip install reportlab")
        return
    default_name = f"Issue_Search_{il_search_meta['item']}_{il_search_meta['month']}".replace(" ", "_")
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=default_name, filetypes=[("PDF Document", "*.pdf")])
    if not file_path:
        return
    try:
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(file_path, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)
        total = sum(r[3] for r in il_search_results)
        elements = [
            Paragraph("Item-wise Monthly Issue Report", styles["Title"]),
            Paragraph(f"<b>Item:</b> {html_lib.escape(il_search_meta['item'])} &nbsp;&nbsp; <b>Month:</b> {il_search_meta['month']} &nbsp;&nbsp; <b>Factory:</b> {html_lib.escape(il_search_meta['factory'])}", styles["Normal"]),
            Paragraph(f"Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}", styles["Normal"]),
            Spacer(1, 12),
        ]
        data = [["Date", "Item Name", "Factory", "Qty Issued"]]
        for d, name, f_name, qty in il_search_results:
            data.append([d, Paragraph(html_lib.escape(str(name)), styles["Normal"]), Paragraph(html_lib.escape(str(f_name)), styles["Normal"]), f"{qty:g}"])
        data.append(["TOTAL", "", "", f"{total:g}"])
        table = Table(data, repeatRows=1, colWidths=[80, 200, 140, 70])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3b6f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e2e8f0")),
            ("ALIGN", (3, 0), (3, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        elements.append(table)
        doc.build(elements)
        messagebox.showinfo("Success", f"Search result exported to PDF successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {e}")


tk.Button(il_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), width=10, command=lambda: search_issue_ledger()).pack(side="left", padx=3)
tk.Button(il_search_bar, text="Download PDF", bg="#b71c1c", fg="white", font=("Arial", 9, "bold"), command=lambda: export_il_search_pdf()).pack(side="left", padx=3)
tk.Button(il_search_bar, text="Download Excel", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: export_il_search_excel()).pack(side="left", padx=3)
il_item_entry.bind("<Return>", search_issue_ledger)

columns_il_search = ("Date", "Item Name", "Factory", "Qty Issued")
tree_il_search = ttk.Treeview(il_search_frame, columns=columns_il_search, show="headings", height=5)
for col, w in zip(columns_il_search, [110, 280, 150, 90]):
    tree_il_search.heading(col, text=col)
    tree_il_search.column(col, width=w, anchor="e" if col == "Qty Issued" else "w", stretch=True)
tree_il_search.pack(fill="x", side="left", expand=True, pady=(4, 0))
il_search_sc = ttk.Scrollbar(il_search_frame, orient="vertical", command=tree_il_search.yview)
il_search_sc.pack(side="right", fill="y", pady=(4, 0))
tree_il_search.configure(yscrollcommand=il_search_sc.set)

lbl_il_search_total = tk.Label(issue_ledger_frame, text="Total Issued Qty: 0  |  Issue Days: 0  |  Records: 0", font=("Arial", 8, "bold"), bg="white", fg="#1b3b6f", anchor="w")
lbl_il_search_total.pack(fill="x", padx=5)

columns_il = ("Tx ID", "Date", "Time", "Factory", "Item Name", "ERP Code", "SL No", "Qty Issued", "Unit Price", "Total Value", "Officer", "Type", "Remarks", "ERP Status")
tree_il = ttk.Treeview(issue_ledger_frame, columns=columns_il, show="headings", height=16)
col_widths_il = [55, 85, 75, 110, 160, 85, 45, 65, 75, 85, 90, 180, 110, 95]
for col, w in zip(columns_il, col_widths_il):
    tree_il.heading(col, text=col)
    align = "w" if "Name" in col or "Factory" in col or "Officer" in col or "Status" in col or col == "Type" else "e"
    tree_il.column(col, width=w, anchor=align, stretch=True)
tree_il.pack(fill="both", expand=True, side="left", pady=(2, 0))
il_sc = ttk.Scrollbar(issue_ledger_frame, orient="vertical", command=tree_il.yview)
il_sc.pack(side="right", fill="y", pady=(2, 0))
tree_il.configure(yscrollcommand=il_sc.set)


def load_issue_ledger():
    for item in tree_il.get_children():
        tree_il.delete(item)
    fac = selected_factory.get()
    query = ("SELECT t.id, t.date, t.time, t.factory_name, t.item_name, t.prod_id, t.sl_no, t.qty, i.unit_price, t.officer_name, t.trans_type, t.notes, t.verification_status "
             "FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name WHERE t.trans_type ILIKE '%%Issue%%'")
    params = []
    if "CONSOLIDATED" not in fac:
        query += " AND t.factory_name = %s"
        params.append(fac)
    query += " ORDER BY t.id DESC"
    cursor.execute(query, params)
    for r in cursor.fetchall():
        price = r[8] if r[8] else 0.0
        val = (r[7] or 0) * price
        erp_stat = "ERP PO Pending" if "Pending" in str(r[11]) else "ERP GRN Completed"
        tree_il.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4], r[5], r[6], r[7], f"{price:,.2f}", f"{val:,.2f} BDT", r[9], _tlabel(r[10]), r[11], erp_stat))


# ================= TAB 5: TRANSFER HISTORY =================
transfer_frame = tk.Frame(tab_transfer_history, bg="white", padx=5, pady=5)
transfer_frame.pack(fill="both", expand=True)

tf_top_bar = tk.Frame(transfer_frame, bg="white", pady=3)
tf_top_bar.pack(fill="x")
tk.Label(tf_top_bar, text="Inter-Unit Stock Transfer History (KC Washing & Windy Washing)", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(side="left")

columns_tf = ("Transfer Ref", "Source Factory", "Dest Factory", "ERP Code", "Item Name", "Quantity", "Date & Time", "Initiated By", "Status", "Notes")
tree_tf = ttk.Treeview(transfer_frame, columns=columns_tf, show="headings", height=16)
col_widths_tf = [110, 120, 120, 85, 180, 65, 110, 90, 90, 140]
for col, w in zip(columns_tf, col_widths_tf):
    tree_tf.heading(col, text=col)
    align = "w" if "Factory" in col or "Name" in col or "By" in col or "Status" in col else "e"
    tree_tf.column(col, width=w, anchor=align, stretch=True)
tree_tf.pack(fill="both", expand=True, side="left", pady=(2, 0))
tf_sc = ttk.Scrollbar(transfer_frame, orient="vertical", command=tree_tf.yview)
tf_sc.pack(side="right", fill="y", pady=(2, 0))
tree_tf.configure(yscrollcommand=tf_sc.set)

tf_search_var = tk.StringVar()


def _tf_selected():
    sel = tree_tf.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a transfer entry from the list first!")
        return None
    ref = tree_tf.item(sel[0], "values")[0]
    cursor.execute("SELECT id, transfer_ref, source_factory, dest_factory, prod_id, item_name, qty, transfer_date, transfer_time, initiated_by, status, notes FROM inter_factory_transfers WHERE transfer_ref=%s", (str(ref),))
    row = cursor.fetchone()
    if not row:
        messagebox.showerror("Not Found", "This transfer entry no longer exists. The list will be refreshed.")
        load_transfer_history()
    return row


def _tf_resolve_items(row):
    """Finds the inventory rows touched by a transfer. Returns (source_item, dest_item).
    Matching is by product NAME + SIZE."""
    (_id, ref, src_fac, dst_fac, prod_id, item_name, qty, t_date, t_time, by, status, notes) = row
    size = _item_size(src_fac, prod_id, item_name)
    dest = _find_same_item_in_other_unit(prod_id, item_name, dst_fac, size)
    src_item = None
    m = re.search(r"source item:\s*(.+?)\s*\[([^\]]*)\]", notes or "")
    if m:
        s_name, s_code = m.group(1).strip(), m.group(2).strip()
        cursor.execute("SELECT sl_no, prod_id, item_name, current_stock FROM inventory WHERE factory_name=%s AND prod_id=%s", (src_fac, s_code))
        cands = [r for r in cursor.fetchall() if _norm_item_name(r[2]) == _norm_item_name(s_name)]
        if cands:
            src_item = cands[0] + ("exact",)
    if not src_item:
        src_item = _find_same_item_in_other_unit(prod_id, item_name, src_fac, size)
    return src_item, dest


def _tf_check_manager(action_text):
    if not require_login():
        return False
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access and cannot edit or delete transfer entries!")
        return False
    if not ask_manager_password(f"Enter Store Manager password to {action_text}:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can edit or delete transfer entries.")
        return False
    return True


def delete_transfer_entry():
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access and cannot delete transfer entries!")
        return
    row = _tf_selected()
    if not row:
        return
    t_id, ref, src_fac, dst_fac, prod_id, item_name, qty, t_date, t_time, by, status, notes = row
    qty = qty or 0
    src_item, dest = _tf_resolve_items(row)
    reverse = True
    if not src_item or not dest:
        if not messagebox.askyesno("Stock Items Not Found",
                                   "The inventory item(s) of this transfer could not be found, so the stock balance cannot be reversed automatically.\n\n"
                                   "Delete the transfer record ONLY (no stock change)?"):
            return
        reverse = False
    else:
        msg = (f"Delete transfer {ref}?\n\n{item_name} [{prod_id}]  -  {qty:g} pcs\n{src_fac}  ->  {dst_fac}\n\n"
               f"Balance will be REVERSED automatically:\n"
               f"  {dst_fac}: {dest[3]:g} -> {dest[3] - qty:g}\n"
               f"  {src_fac}: {src_item[3]:g} -> {src_item[3] + qty:g}\n")
        if dest[3] - qty < 0:
            msg += f"\n⚠️ WARNING: {dst_fac} stock will become NEGATIVE ({dest[3] - qty:g}) because part of this stock was already issued.\n"
        msg += "\n(The related issue entry in [1] TRANSACTIONS is not touched.)"
        if not messagebox.askyesno("Confirm Delete & Reverse Balance", msg):
            return
    if not _tf_check_manager("delete this transfer entry"):
        return
    try:
        if reverse:
            cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (qty, dest[0], dst_fac))
            cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (qty, src_item[0], src_fac))
        cursor.execute("DELETE FROM inter_factory_transfers WHERE id=%s", (t_id,))
        _audit("DELETE_TRANSFER", f"Deleted transfer {ref}: {qty:g} pcs of {item_name} [{prod_id}] {src_fac} -> {dst_fac}" + (" (balance reversed)" if reverse else " (record only)"))
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Failed to delete transfer entry (nothing was changed): {e}")
        return
    messagebox.showinfo("Success", f"Transfer {ref} deleted" + (" and stock balance reversed!" if reverse else " (record only)."))
    refresh_data()


def edit_transfer_entry(event=None):
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access and cannot edit transfer entries!")
        return
    row = _tf_selected()
    if not row:
        return
    t_id, ref, src_fac, dst_fac, prod_id, item_name, old_qty, t_date, t_time, by, status, notes = row
    old_qty = old_qty or 0
    win = tk.Toplevel(root)
    win.title(f"Edit Transfer {ref}")
    win.geometry("470x330")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text=f"{item_name} [{prod_id}]", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 0))
    tk.Label(win, text=f"{src_fac}  ->  {dst_fac}", font=("Arial", 8), bg="white", fg="#555").pack()
    f = tk.Frame(win, bg="white")
    f.pack(padx=15, pady=10, fill="x")
    ents = {}
    for i, (lbl, key, val, w) in enumerate([("Quantity:", "qty", f"{old_qty:g}", 12), ("Date (DD-Mon-YYYY):", "date", t_date or "", 16),
                                           ("Time:", "time", t_time or "", 12), ("Notes:", "notes", notes or "", 40)]):
        tk.Label(f, text=lbl, font=("Arial", 9, "bold"), bg="white").grid(row=i, column=0, sticky="w", pady=4)
        e = tk.Entry(f, width=w, font=("Arial", 9))
        e.insert(0, val)
        e.grid(row=i, column=1, sticky="w", padx=6, pady=4)
        ents[key] = e
    tk.Label(win, text="Changing the quantity adjusts both factory stock balances automatically.", font=("Arial", 8, "italic"), bg="white", fg="#b71c1c").pack()

    def save_edit():
        try:
            new_qty = float(ents["qty"].get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid numeric quantity!", parent=win)
            return
        if new_qty <= 0:
            messagebox.showerror("Error", "Quantity must be greater than zero!", parent=win)
            return
        new_date = ents["date"].get().strip()
        try:
            datetime.strptime(new_date, "%d-%b-%Y")
        except ValueError:
            messagebox.showerror("Error", "Date must be in DD-Mon-YYYY format (e.g. 12-Oct-2026).", parent=win)
            return
        new_time = ents["time"].get().strip()
        new_notes = ents["notes"].get().strip()
        delta = new_qty - old_qty
        src_item = dest = None
        if abs(delta) > 1e-9:
            src_item, dest = _tf_resolve_items(row)
            if not src_item or not dest:
                messagebox.showerror("Stock Items Not Found", "The inventory item(s) of this transfer could not be found, so the quantity cannot be changed.", parent=win)
                return
            if delta > 0 and src_item[3] < delta:
                messagebox.showerror("Insufficient Stock", f"{src_fac} has only {src_item[3]:g} pcs, but {delta:g} more pcs are needed for this change.", parent=win)
                return
            if delta < 0 and dest[3] + delta < 0:
                if not messagebox.askyesno("Negative Stock Warning", f"{dst_fac} stock will become NEGATIVE ({dest[3] + delta:g}). Continue?", parent=win):
                    return
        if not _tf_check_manager("save changes to this transfer entry"):
            return
        try:
            if abs(delta) > 1e-9:
                cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (delta, dest[0], dst_fac))
                cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (delta, src_item[0], src_fac))
            cursor.execute("UPDATE inter_factory_transfers SET qty=%s, transfer_date=%s, transfer_time=%s, notes=%s WHERE id=%s", (new_qty, new_date, new_time, new_notes, t_id))
            _audit("EDIT_TRANSFER", f"Edited transfer {ref}: qty {old_qty:g} -> {new_qty:g}, date {t_date} -> {new_date}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Failed to update transfer entry (nothing was changed): {e}", parent=win)
            return
        win.destroy()
        messagebox.showinfo("Success", f"Transfer {ref} updated successfully!")
        refresh_data()

    bf = tk.Frame(win, bg="white")
    bf.pack(pady=10)
    tk.Button(bf, text="Save Changes", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), width=14, command=save_edit).pack(side="left", padx=5)
    tk.Button(bf, text="Cancel", bg="#718096", fg="white", font=("Arial", 9, "bold"), width=10, command=win.destroy).pack(side="left", padx=5)


def export_transfer_pdf():
    items = tree_tf.get_children()
    if not items:
        messagebox.showwarning("No Data", "There are no transfer entries in the table to download!")
        return
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        messagebox.showerror("Missing Library", "PDF export requires the 'reportlab' library.\nInstall it with:  pip install reportlab")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile=f"Transfer_History_{datetime.now().strftime('%Y%m%d_%H%M')}", filetypes=[("PDF Document", "*.pdf")])
    if not file_path:
        return
    try:
        styles = getSampleStyleSheet()
        cell = ParagraphStyle("tfcell", parent=styles["Normal"], fontSize=7, leading=8.5)
        esc = html_lib.escape
        rows = [tree_tf.item(i, "values") for i in items]
        total_qty = 0.0
        for r in rows:
            try:
                total_qty += float(r[5])
            except (TypeError, ValueError):
                pass
        flt = tf_search_var.get().strip()
        doc = SimpleDocTemplate(file_path, pagesize=landscape(A4), leftMargin=36, rightMargin=36, topMargin=30, bottomMargin=30)
        elements = [
            Paragraph("Inter-Unit Stock Transfer History", styles["Title"]),
            Paragraph(f"<b>Search Filter:</b> {esc(flt) if flt else 'None (all)'} &nbsp;&nbsp; <b>Records:</b> {len(rows)} &nbsp;&nbsp; <b>Total Qty Transferred:</b> {total_qty:g} &nbsp;&nbsp; <b>Printed by:</b> {esc(current_authenticated_user.get())}", styles["Normal"]),
            Paragraph(f"Generated: {datetime.now().strftime('%d-%b-%Y %I:%M %p')}", styles["Normal"]),
            Spacer(1, 10),
        ]
        data = [list(columns_tf)]
        for r in rows:
            data.append([Paragraph(esc(str(v)), cell) for v in r])
        table = Table(data, repeatRows=1, colWidths=[95, 70, 70, 50, 120, 35, 75, 60, 50, 145])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3b6f")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        elements.append(table)
        doc.build(elements)
        messagebox.showinfo("Success", f"Transfer history exported to PDF successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {e}")


def load_transfer_history():
    for item in tree_tf.get_children():
        tree_tf.delete(item)
    cursor.execute("SELECT transfer_ref, source_factory, dest_factory, prod_id, item_name, qty, transfer_date, transfer_time, initiated_by, status, notes FROM inter_factory_transfers ORDER BY id DESC")
    tf_kw = tf_search_var.get().strip().lower()
    for r in cursor.fetchall():
        dt_str = f"{r[6]} {r[7]}"
        if tf_kw and tf_kw not in " ".join(str(x) for x in (r[0], r[1], r[2], r[3], r[4], r[5], dt_str, r[8], r[9], r[10])).lower():
            continue
        tree_tf.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4], r[5], dt_str, r[8], r[9], r[10]))


def search_transfer_history(event=None):
    load_transfer_history()


def reset_transfer_search():
    tf_search_var.set("")
    load_transfer_history()


tk.Button(tf_top_bar, text="Download PDF", bg="#b71c1c", fg="white", font=("Arial", 9, "bold"), command=lambda: export_transfer_pdf()).pack(side="right", padx=3)
tk.Button(tf_top_bar, text="🗑 Delete", bg="#c62828", fg="white", font=("Arial", 9, "bold"), command=lambda: delete_transfer_entry()).pack(side="right", padx=3)
tk.Button(tf_top_bar, text="✏️ Edit", bg="#ef6c00", fg="white", font=("Arial", 9, "bold"), command=lambda: edit_transfer_entry()).pack(side="right", padx=3)
tk.Button(tf_top_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 9, "bold"), command=lambda: reset_transfer_search()).pack(side="right", padx=3)
tk.Button(tf_top_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: search_transfer_history()).pack(side="right", padx=3)
tf_search_entry = tk.Entry(tf_top_bar, textvariable=tf_search_var, width=22, font=("Arial", 9))
tf_search_entry.pack(side="right", padx=3)
tk.Label(tf_top_bar, text="Search:", font=("Arial", 9, "bold"), bg="white").pack(side="right")
tf_search_entry.bind("<Return>", search_transfer_history)
tree_tf.bind("<Double-1>", edit_transfer_entry)


# ================= REQUISITION: SETTINGS & CONSTANTS =================
REQ_PO_ALERT_DAYS = 7
REQ_DATE_FMT = "%d-%b-%Y"
REQ_AUDIT_EDIT_ROLES = ("Executive",)


def _req_get_setting(key, default=""):
    cursor.execute("SELECT setting_value FROM req_settings WHERE setting_key=%s", (key,))
    row = cursor.fetchone()
    return row[0] if row and row[0] is not None else default


def _req_set_setting(key, value):
    cursor.execute("INSERT INTO req_settings (setting_key, setting_value) VALUES (%s, %s) ON CONFLICT (setting_key) DO UPDATE SET setting_value = EXCLUDED.setting_value", (key, value))
    conn.commit()


rq_state = {"rows": {}}
rq_search_var = tk.StringVar()


def _req_parse_date(text):
    t = str(text or "").strip()
    if not t or t.lower() in ("none", "pending po", "not received"):
        return None
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    return None


def _req_calc(r):
    req_q = r["req_qty"] or 0.0
    aud_q = r["aud_qty"] or 0.0
    rec_q = r["rec_qty"] or 0.0
    base = aud_q if aud_q > 0 else req_q
    pending = max(base - rec_q, 0.0)
    now = datetime.now()
    d_req, d_po = _req_parse_date(r["req_date"]), _req_parse_date(r["po_date"])
    age = max((now - d_req).days, 0) if d_req else 0
    if d_req and d_po:
        delay = max((d_po - d_req).days, 0)
    else:
        delay = age
    since_po = max((now - d_po).days, 0) if d_po else 0
    if rec_q > 0 and pending <= 0:
        status = "Fully Received"
    elif rec_q > 0:
        status = "Partially Received"
    elif d_po:
        status = "PO Issued - Awaiting Delivery"
    elif aud_q > 0:
        status = "Audit Approved - PO Pending"
    else:
        status = "Req Created - Audit Pending"
    return {"base": base, "pending": pending, "age": age, "delay": delay, "since_po": since_po, "calc_status": status}


def _rq_create_inventory_item(fac, code, name, dept):
    cursor.execute("SELECT MAX(sl_no) FROM inventory WHERE factory_name=%s", (fac,))
    next_sl = (cursor.fetchone()[0] or 0) + 1
    if not code:
        n = next_sl
        while True:
            code = f"TEMP-{n:04d}"
            cursor.execute("SELECT 1 FROM inventory WHERE prod_id=%s AND factory_name=%s", (code, fac))
            if not cursor.fetchone():
                break
            n += 1
    cursor.execute("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, department, category, erp_stock, current_stock, unit_price, erp_status, size)
                      VALUES (%s, %s, %s, %s, %s, %s, 0, 0, 0, 'ERP Pending', '')""",
                   (next_sl, code, fac, name, dept, "Uncategorized (Edit Later)"))
    return code


def _rq_is_temp_code(code):
    return (not code) or str(code).upper().startswith("TEMP-")


def _rq_log(action, details):
    _audit(action, details)


def _rq_manager_authorized(prompt):
    return ask_manager_password(prompt)


def _rq_field(win, label, value="", width=36):
    return make_field(win, label, value, width)


# ================= REQUISITION: IMPORT (Excel / CSV / PDF) =================
REQ_IMPORT_LABELS = [
    ("req_no", "Requisition No"),
    ("item", "Item Description (Product Name)"),
    ("code", "ERP Code (optional)"),
    ("qty", "Req Qty"),
    ("dept", "Department (optional)"),
    ("date", "Req Date (optional)"),
]
REQ_IMPORT_KEYS = {
    "req_no": ["reqno", "requisitionno", "requisitionnumber", "rqsnno", "rqsnnumber", "reqnumber", "requisitionid", "requisitionnum",
               "indentno", "prno", "reqnum", "rqsn", "requisition"],
    "item": ["itemname", "itemdescription", "productname", "materialdescription", "materialname", "productdescription", "itemdesc",
             "nameofitem", "description", "particulars", "product", "material", "item"],
    "code": ["erpcode", "itemcode", "productcode", "materialcode", "erpitemcode", "erpnumber", "erpno", "prodid", "partno", "itemno", "code"],
    "qty": ["reqqty", "requisitionqty", "requestedqty", "requiredqty", "reqquantity", "requisitionquantity", "quantity", "qty"],
    "dept": ["department", "departmentname", "dept"],
    "date": ["reqdate", "requisitiondate", "rqsndate", "date"],
}


def _req_norm(text):
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


def _req_cell(v):
    if v is None:
        return ""
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    if isinstance(v, datetime):
        return v.strftime(REQ_DATE_FMT)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def _req_read_raw(path, sheet=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return pd.read_csv(path, header=None, dtype=object, keep_default_na=False, encoding_errors="replace"), [], ""
    if ext == ".pdf":
        try:
            import pdfplumber
        except ImportError:
            raise RuntimeError("PDF import needs the 'pdfplumber' library.\nInstall it with:  pip install pdfplumber\n\nOr export the requisition as Excel/CSV and import that file.")
        rows, guess = [], ""
        with pdfplumber.open(path) as pdf:
            for pi, page in enumerate(pdf.pages):
                if pi == 0:
                    m = re.search(r"(?:requisition|req\.?|rqsn)\s*(?:no|number|#)\.?\s*[:#\-]\s*([A-Za-z0-9][A-Za-z0-9\-/]{2,})", page.extract_text() or "", re.I)
                    if m:
                        guess = m.group(1)
                for table in page.extract_tables():
                    for row in table:
                        rows.append(["" if c is None else str(c).replace("\n", " ").strip() for c in row])
        if not rows:
            raise RuntimeError("No table could be read from this PDF.\nPlease export the requisition as Excel/CSV and import that file.")
        width = max(len(r) for r in rows)
        return pd.DataFrame([r + [""] * (width - len(r)) for r in rows], dtype=object), [], guess
    xls = pd.ExcelFile(path)
    sheets = xls.sheet_names
    return xls.parse(sheet_name=sheet or sheets[0], header=None, dtype=object), sheets, ""


def _req_find_header_row(df):
    allkeys = {k for ks in REQ_IMPORT_KEYS.values() for k in ks}
    best, best_i = 0, 0
    for i in range(min(25, len(df))):
        score = sum(1 for v in df.iloc[i] if _req_norm(_req_cell(v)) in allkeys)
        if score > best:
            best, best_i = score, i
    return best_i


def _req_auto_map(headers):
    norm = [_req_norm(h) for h in headers]
    mapping, used = {}, set()
    for field, keys in REQ_IMPORT_KEYS.items():
        for key in keys:
            hit = next((i for i, n in enumerate(norm) if n == key and i not in used), None)
            if hit is not None:
                mapping[field] = hit
                used.add(hit)
                break
    for field, keys in REQ_IMPORT_KEYS.items():
        if field in mapping:
            continue
        for key in sorted(keys, key=len, reverse=True):
            hit = next((i for i, n in enumerate(norm) if n and key in n and i not in used), None)
            if hit is not None:
                mapping[field] = hit
                used.add(hit)
                break
    return mapping


def _req_guess_no(df, header_idx):
    pat = re.compile(r"(?:requisition|req\.?|rqsn)\s*(?:no|number|#)\.?\s*[:#\-]?\s*(.*)$", re.I)
    for ri in range(0, min(header_idx, 20)):
        cells = [_req_cell(v) for v in df.iloc[ri]]
        for ci, c in enumerate(cells):
            m = pat.match(c)
            if m:
                if m.group(1).strip():
                    return m.group(1).strip()
                for nxt in cells[ci + 1:]:
                    if nxt:
                        return nxt
    return ""


def _req_import_parse(df, header_idx, mapping, fixed, fac, auto_no, create_items):
    out, seen, new_seen = [], {}, set()
    last = {"req_no": "", "dept": "", "date": ""}
    ncols = df.shape[1]
    hn_item = ""
    if header_idx < len(df) and mapping.get("item") is not None and mapping["item"] < ncols:
        hn_item = _req_norm(_req_cell(df.iloc[header_idx, mapping["item"]]))

    def cell(row, field):
        ci = mapping.get(field)
        return _req_cell(row.iloc[ci]) if ci is not None and ci < ncols else ""

    for ridx in range(header_idx + 1, len(df)):
        row = df.iloc[ridx]
        item, code, qty_txt = cell(row, "item"), cell(row, "code"), cell(row, "qty")
        if code.upper() in ("N/A", "NA", "NONE", "-"):
            code = ""
        vals = {"req_no": "", "dept": "", "date": ""}
        for f in vals:
            if mapping.get(f) is not None:
                v = cell(row, f)
                if v:
                    last[f] = v
                vals[f] = last[f]
        if not item and not code and not qty_txt:
            continue
        if hn_item and item and _req_norm(item) == hn_item:
            continue
        req_no = vals["req_no"] or fixed.get("req_no") or auto_no
        dept = vals["dept"] or fixed.get("dept") or "Maintenance"
        d = _req_parse_date(vals["date"]) or _req_parse_date(fixed.get("date")) or datetime.now()
        m = re.search(r"\d+(?:\.\d+)?", qty_txt.replace(",", ""))
        qty = float(m.group()) if m else 0.0
        p = {"line": ridx + 1, "req_no": req_no, "item": item, "code": code, "qty": qty, "dept": dept,
             "date": d.strftime(REQ_DATE_FMT), "ok": False, "new": False, "result": ""}
        inv = _rq_find_inventory(fac, code, item)
        if not item and inv:
            p["item"] = item = inv[2]
        if not item:
            p["result"] = "Skipped: no item description"
        elif qty <= 0:
            p["result"] = "Skipped: no valid Req Qty"
        else:
            key = (req_no.lower(), item.lower())
            cursor.execute("SELECT id FROM requisition_tracking WHERE factory_name=%s AND req_no=%s AND LOWER(item_name)=LOWER(%s)", (fac, req_no, item))
            if key in seen:
                out[seen[key]]["qty"] += qty
                p["result"] = f"Merged into line {out[seen[key]]['line']} (qty added)"
            elif cursor.fetchone():
                p["result"] = "Already imported - skipped"
            else:
                p["ok"] = True
                seen[key] = len(out)
                if inv:
                    p["result"] = f"OK - linked to ERP code {inv[1]}"
                elif create_items and item.lower() not in new_seen:
                    new_seen.add(item.lower())
                    p["new"] = True
                    p["result"] = "OK - NEW item added to Inventory" + ("" if code else " (temporary ERP code, size to be added)")
                elif create_items:
                    p["result"] = "OK - item added by an earlier line"
                else:
                    p["result"] = "OK - not added to Inventory"
        out.append(p)
    return out


def open_requisition_import_dialog(path, fac):
    try:
        df, sheets, pdf_guess = _req_read_raw(path)
    except Exception as e:
        messagebox.showerror("Import Error", f"Failed to read the file:\n{e}")
        return
    state = {"df": df, "parsed": []}
    auto_no = f"RQSN-{datetime.now().strftime('%m%d-%H%M')}"

    win = tk.Toplevel(root)
    win.title(f"Import Requisition - {os.path.basename(path)}")
    win.geometry("1150x740")
    win.config(bg="white")
    win.grab_set()

    tk.Label(win, text=f"📥 Import Requisition   |   File: {os.path.basename(path)}   |   Factory: {fac}", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(anchor="w", padx=12, pady=(8, 1))
    tk.Label(win, text="Check that every field points to the correct column of your file. The preview shows exactly where each value will go. Nothing is saved until you press 'Import Now'.",
             font=("Arial", 8, "italic"), bg="white", fg="#666").pack(anchor="w", padx=12)

    sheet_var = tk.StringVar(value=sheets[0] if sheets else "")
    header_var = tk.StringVar(value="1")
    map_vars = {k: tk.StringVar(value="(none)") for k, _ in REQ_IMPORT_LABELS}
    fx_no_var = tk.StringVar(value=pdf_guess)
    fx_dept_var = tk.StringVar(value="Maintenance")
    fx_date_var = tk.StringVar(value=datetime.now().strftime(REQ_DATE_FMT))
    create_var = tk.BooleanVar(value=True)
    combos = {}

    ctl = tk.Frame(win, bg="white")
    ctl.pack(fill="x", padx=12, pady=(6, 2))
    if len(sheets) > 1:
        tk.Label(ctl, text="Sheet:", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky="w")
        sh_combo = ttk.Combobox(ctl, textvariable=sheet_var, values=sheets, width=24, state="readonly")
        sh_combo.grid(row=0, column=1, padx=(4, 14))
        sh_combo.bind("<<ComboboxSelected>>", lambda e: reload_sheet())
    tk.Label(ctl, text="Header row no. (row that contains the column names):", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=2, sticky="w")
    hdr_spin = tk.Spinbox(ctl, from_=1, to=60, width=5, textvariable=header_var, command=lambda: apply_header())
    hdr_spin.grid(row=0, column=3, padx=4)
    hdr_spin.bind("<Return>", lambda e: apply_header())
    hdr_spin.bind("<FocusOut>", lambda e: apply_header() if header_idx() != state.get("applied_hdr") else None)

    mp = tk.LabelFrame(win, text=" Column Mapping - which column of your file holds what ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=6, pady=4)
    mp.pack(fill="x", padx=12, pady=4)
    for i, (key, label) in enumerate(REQ_IMPORT_LABELS):
        r, c = divmod(i, 3)
        tk.Label(mp, text=label + ":", bg="white", font=("Arial", 8, "bold")).grid(row=r, column=c * 2, sticky="w", padx=(6, 2), pady=3)
        cb = ttk.Combobox(mp, textvariable=map_vars[key], width=30, state="readonly")
        cb.grid(row=r, column=c * 2 + 1, padx=(0, 12), pady=3)
        cb.bind("<<ComboboxSelected>>", lambda e: refresh_preview())
        combos[key] = cb

    fx = tk.LabelFrame(win, text=" Fixed values (used only when that field has no column in the file) ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=6, pady=4)
    fx.pack(fill="x", padx=12, pady=4)
    tk.Label(fx, text="Requisition No:", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky="w", padx=(6, 2))
    e_no = tk.Entry(fx, textvariable=fx_no_var, width=22, font=("Arial", 9))
    e_no.grid(row=0, column=1, padx=(0, 12))
    tk.Label(fx, text="Department:", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=2, sticky="w", padx=(6, 2))
    e_dp = ttk.Combobox(fx, textvariable=fx_dept_var, values=["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"], width=22)
    e_dp.grid(row=0, column=3, padx=(0, 12))
    tk.Label(fx, text="Req Date:", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=4, sticky="w", padx=(6, 2))
    e_dt = tk.Entry(fx, textvariable=fx_date_var, width=14, font=("Arial", 9))
    e_dt.grid(row=0, column=5, padx=(0, 12))
    tk.Checkbutton(fx, text="Add items not found in Inventory (temporary ERP code if code is missing)", variable=create_var, bg="white", font=("Arial", 8),
                   command=lambda: refresh_preview()).grid(row=1, column=0, columnspan=6, sticky="w", padx=4, pady=(3, 0))
    for w in (e_no, e_dt):
        w.bind("<KeyRelease>", lambda e: refresh_preview())
    e_dp.bind("<<ComboboxSelected>>", lambda e: refresh_preview())
    e_dp.bind("<KeyRelease>", lambda e: refresh_preview())

    pv_frame = tk.Frame(win, bg="white")
    pv_frame.pack(fill="both", expand=True, padx=12, pady=4)
    pv_cols = ("File Line", "Req No", "Item Description", "ERP Code", "Req Qty", "Department", "Req Date", "Result")
    tree_pv = ttk.Treeview(pv_frame, columns=pv_cols, show="headings", height=10)
    for col, w in zip(pv_cols, [60, 120, 280, 100, 70, 130, 90, 260]):
        tree_pv.heading(col, text=col)
        tree_pv.column(col, width=w, anchor="e" if col in ("File Line", "Req Qty") else "w", stretch=True)
    tree_pv.tag_configure("bad", foreground="#c53030")
    pv_sc = ttk.Scrollbar(pv_frame, orient="vertical", command=tree_pv.yview)
    tree_pv.configure(yscrollcommand=pv_sc.set)
    pv_sc.pack(side="right", fill="y")
    tree_pv.pack(side="left", fill="both", expand=True)

    lbl_sum = tk.Label(win, text="", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", anchor="w")
    lbl_sum.pack(fill="x", padx=12)

    def header_idx():
        try:
            return max(int(header_var.get()) - 1, 0)
        except ValueError:
            return 0

    def current_mapping():
        res = {}
        for key, var in map_vars.items():
            v = var.get()
            res[key] = int(v.split(":")[0]) - 1 if v and v != "(none)" and ":" in v else None
        return res

    def refresh_preview(*_):
        for i in tree_pv.get_children():
            tree_pv.delete(i)
        mapping = current_mapping()
        if (mapping["item"] is None and mapping["code"] is None) or mapping["qty"] is None:
            state["parsed"] = []
            lbl_sum.config(text="⚠ Please select the Item Description column and the Req Qty column to see the preview.", fg="#c53030")
            return
        parsed = _req_import_parse(state["df"], header_idx(), mapping,
                                   {"req_no": fx_no_var.get().strip(), "dept": fx_dept_var.get().strip(), "date": fx_date_var.get().strip()},
                                   fac, auto_no, create_var.get())
        state["parsed"] = parsed
        for p in parsed[:800]:
            tree_pv.insert("", "end", values=(p["line"], p["req_no"], p["item"], p["code"], f"{p['qty']:g}", p["dept"], p["date"], p["result"]),
                           tags=(() if p["ok"] else ("bad",)))
        ok = sum(1 for p in parsed if p["ok"])
        new = sum(1 for p in parsed if p["new"])
        dup = sum(1 for p in parsed if p["result"].startswith("Already"))
        bad = sum(1 for p in parsed if not p["ok"]) - dup
        lbl_sum.config(text=f"Lines to import: {ok}  |  New inventory items: {new}  |  Already imported: {dup}  |  Skipped / merged: {bad}", fg="#1b3b6f")

    def apply_header(auto_map=True):
        hi = header_idx()
        if hi >= len(state["df"]):
            return
        state["applied_hdr"] = hi
        heads = [_req_cell(v) for v in state["df"].iloc[hi]]
        labels = [f"{i + 1}: {h or '(blank)'}" for i, h in enumerate(heads)]
        for cb in combos.values():
            cb["values"] = ["(none)"] + labels
        if auto_map:
            m = _req_auto_map(heads)
            for key, var in map_vars.items():
                var.set(labels[m[key]] if key in m else "(none)")
            g = _req_guess_no(state["df"], hi)
            if g and not fx_no_var.get().strip():
                fx_no_var.set(g)
        refresh_preview()

    def reload_sheet():
        try:
            d, _, _ = _req_read_raw(path, sheet_var.get())
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to read the sheet:\n{e}", parent=win)
            return
        state["df"] = d
        header_var.set(str(_req_find_header_row(d) + 1))
        apply_header()

    def do_import():
        rows = [p for p in state["parsed"] if p["ok"]]
        if not rows:
            messagebox.showwarning("Nothing to Import", "There are no valid lines to import. Please check the column mapping.", parent=win)
            return
        if not messagebox.askyesno("Confirm Import", f"Import {len(rows)} requisition line(s) into {fac}?", parent=win):
            return
        conn.commit()
        backup_path = f"windy_store_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        try:
            _backup_database(backup_path)
        except Exception as e:
            backup_path = "not created"
            messagebox.showwarning("Backup Warning", f"Could not create backup: {e}", parent=win)
        try:
            new_items = 0
            for p in rows:
                inv = _rq_find_inventory(fac, p["code"], p["item"])
                if inv:
                    code = inv[1]
                elif create_var.get():
                    code = _rq_create_inventory_item(fac, p["code"], p["item"], p["dept"])
                    new_items += 1
                else:
                    code = p["code"]
                cursor.execute("""INSERT INTO requisition_tracking (factory_name, req_no, department, req_date, item_name, req_qty, audit_approved_qty,
                                  actual_received_qty, status, po_delay_days, prod_id) VALUES (%s, %s, %s, %s, %s, %s, 0, 0, 'Req Created - Audit Pending', 0, %s)""",
                               (fac, p["req_no"], p["dept"], p["date"], p["item"], p["qty"], code))
            _rq_log("IMPORT_REQUISITION", f"Imported {len(rows)} requisition line(s) from {os.path.basename(path)} into {fac} ({new_items} new inventory items)")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Import Error", f"Import failed and was rolled back:\n{e}", parent=win)
            return
        skipped = len(state["parsed"]) - len(rows)
        messagebox.showinfo("Import Completed",
                            f"Requisition import completed!\n\n- Lines imported: {len(rows)}\n- New items added to Inventory: {new_items}\n"
                            f"- Lines skipped / merged / already imported: {skipped}\n\nBackup: {backup_path}\n\n"
                            "Audit Approved Qty is 0 until Mr. Sattar (Executive) approves it.", parent=win)
        win.destroy()
        refresh_data()

    btns = tk.Frame(win, bg="white")
    btns.pack(fill="x", padx=12, pady=8)
    tk.Button(btns, text="✔️ Import Now", bg="#2e7d32", fg="white", font=("Arial", 10, "bold"), width=18, command=do_import).pack(side="left", padx=3)
    tk.Button(btns, text="Cancel", bg="#c53030", fg="white", font=("Arial", 9, "bold"), width=10, command=win.destroy).pack(side="left", padx=3)

    header_var.set(str(_req_find_header_row(df) + 1))
    apply_header()


def import_requisition_pdf_excel():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot import requisitions!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error", "Please select a specific factory before importing Requisitions!")
        return
    file_path = filedialog.askopenfilename(
        title="Select ERP Requisition File (PDF/Excel/CSV)",
        filetypes=[("Excel & CSV Files", "*.xlsx *.xls *.csv"), ("PDF Files", "*.pdf"), ("All Files", "*.*")]
    )
    if file_path:
        open_requisition_import_dialog(file_path, fac)


def cleanup_old_test_imports():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access!")
        return
    if not _rq_manager_authorized("Enter Store Manager Password to remove old test imports:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can remove old test imports.")
        return
    cursor.execute("SELECT COUNT(*) FROM requisition_tracking WHERE item_name='Imported Requisition Consumable' AND COALESCE(actual_received_qty,0)=0")
    n_req = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM import_queue WHERE prod_id='PENDING-REQ' AND item_name='Imported Requisition Item'")
    n_q = cursor.fetchone()[0]
    if n_req + n_q == 0:
        messagebox.showinfo("Nothing Found", "No old test-import rows were found.")
        return
    if not messagebox.askyesno("Confirm", f"Remove {n_req} old test requisition row(s) and {n_q} old test row(s) from the Import Queue?"):
        return
    cursor.execute("DELETE FROM requisition_tracking WHERE item_name='Imported Requisition Consumable' AND COALESCE(actual_received_qty,0)=0")
    cursor.execute("DELETE FROM import_queue WHERE prod_id='PENDING-REQ' AND item_name='Imported Requisition Item'")
    _rq_log("CLEANUP_TEST_IMPORTS", f"Removed {n_req} test requisition rows and {n_q} import-queue rows")
    conn.commit()
    refresh_data()


# ================= TAB 6: REQUISITION UI =================
req_frame = tk.Frame(tab_req_track, bg="white", padx=5, pady=5)
req_frame.pack(fill="both", expand=True)

req_top_panel = tk.Frame(req_frame, bg="white")
req_top_panel.pack(fill="x", pady=3)
tk.Label(req_top_panel, text="ERP Requisition, Audit Qty & Sourcing Received Tracking Hub", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(side="left")
tk.Button(req_top_panel, text="📥 Import Requisition", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: import_requisition_pdf_excel()).pack(side="right", padx=5)


def _rq_selected_row(show_error=True):
    sel = tree_req.selection()
    if not sel or sel[0] not in rq_state["rows"]:
        if show_error:
            messagebox.showerror("Selection Error", "Please select a requisition row from the table first!")
        return None
    return rq_state["rows"][sel[0]]


def _rq_dialog(title, geometry):
    win = tk.Toplevel(root)
    win.title(title)
    win.geometry(geometry)
    win.config(bg="white")
    win.grab_set()
    return win


def edit_audit_approved_popup():
    if not require_login():
        return
    if current_user_role.get() not in REQ_AUDIT_EDIT_ROLES:
        messagebox.showerror("Permission Denied", "Audit Approved Qty can be changed only by Mr. Sattar (Executive).\nPlease login with the Executive account.")
        return
    r = _rq_selected_row()
    if not r:
        return
    win = _rq_dialog(f"Audit Panel - Approved Qty [{r['req_no']}]", "430x330")
    tk.Label(win, text="AUDIT PANEL - Edit Audit Approved Qty", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    tk.Label(win, text=f"{r['item_name']}\nReq No: {r['req_no']}  |  {r['factory']}\nRequested: {r['req_qty']:g}   |   Currently Approved: {r['aud_qty']:g}   |   Received: {r['rec_qty']:g}",
             font=("Arial", 8), bg="#e8f4fd", fg="#0d47a1", justify="left", padx=8, pady=5).pack(fill="x", padx=25, pady=4)
    e_new = _rq_field(win, "New Audit Approved Qty:", f"{r['aud_qty']:g}", 20)
    e_rem = _rq_field(win, "Audit Remarks (saved in activity log):", "", 40)

    def use_full():
        e_new.delete(0, tk.END)
        e_new.insert(0, f"{r['req_qty']:g}")

    tk.Button(win, text="Approve Full Requested Qty", bg="#718096", fg="white", font=("Arial", 8, "bold"), command=use_full).pack(anchor="w", padx=25, pady=4)

    def save():
        try:
            new_q = float(e_new.get().strip())
            if new_q < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid approved quantity (0 or more)!", parent=win)
            return
        if new_q > r["req_qty"]:
            messagebox.showerror("Error", f"Approved Qty ({new_q:g}) cannot be more than the Requested Qty ({r['req_qty']:g})!", parent=win)
            return
        if new_q < r["rec_qty"] and not messagebox.askyesno("Confirm", f"Approved Qty ({new_q:g}) is less than the already received Qty ({r['rec_qty']:g}).\nContinue?", parent=win):
            return
        try:
            cursor.execute("UPDATE requisition_tracking SET audit_approved_qty=%s WHERE id=%s", (new_q, r["id"]))
            _rq_log("EDIT_AUDIT_APPROVED", f"Req {r['req_no']} / {r['item_name']} ({r['factory']}): Audit Approved Qty {r['aud_qty']:g} -> {new_q:g}. {e_rem.get().strip()}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to update: {e}", parent=win)
            return
        messagebox.showinfo("Success", "Audit Approved Qty updated successfully!", parent=win)
        win.destroy()
        refresh_data()

    tk.Button(win, text="Save Approved Qty", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=12)


def update_tracking_popup():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot update PO / receiving data!")
        return
    r = _rq_selected_row()
    if not r:
        return
    win = _rq_dialog(f"Update PO / Receiving [{r['req_no']}]", "450x400")
    tk.Label(win, text="PO & Receiving Tracking", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    tk.Label(win, text=f"{r['item_name']}\nReq No: {r['req_no']}  |  Req Date: {r['req_date']}\nApproved: {r['aud_qty']:g}   |   Received so far: {r['rec_qty']:g}   |   Pending: {r['pending']:g}",
             font=("Arial", 8), bg="#e8f4fd", fg="#0d47a1", justify="left", padx=8, pady=5).pack(fill="x", padx=25, pady=4)
    po_d0 = _req_parse_date(r["po_date"])
    po_txt = po_d0.strftime(REQ_DATE_FMT) if po_d0 else ""
    e_po = _rq_field(win, "HO PO Date (DD-Mon-YYYY, blank = PO not received yet):", po_txt, 22)
    e_rec = _rq_field(win, "Total Received Qty by Factory (so far):", f"{r['rec_qty']:g}", 22)
    rec_d0 = _req_parse_date(r.get("rec_date"))
    e_rdate = _rq_field(win, "Last Received Date (blank = today if qty received):", rec_d0.strftime(REQ_DATE_FMT) if rec_d0 else "", 22)

    def save():
        po_d = None
        if e_po.get().strip():
            po_d = _req_parse_date(e_po.get())
            if not po_d:
                messagebox.showerror("Error", "HO PO Date must be in DD-Mon-YYYY format!", parent=win)
                return
            d_req = _req_parse_date(r["req_date"])
            if d_req and po_d < d_req:
                messagebox.showerror("Error", "PO Date cannot be earlier than the Requisition Date!", parent=win)
                return
        try:
            rec_q = float(e_rec.get().strip() or 0)
            if rec_q < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid received quantity!", parent=win)
            return
        if rec_q > r["base"] and not messagebox.askyesno("Confirm", f"Received Qty ({rec_q:g}) is more than the expected Qty ({r['base']:g}).\nContinue?", parent=win):
            return
        rec_d = None
        if rec_q > 0:
            rec_d = _req_parse_date(e_rdate.get()) if e_rdate.get().strip() else datetime.now()
            if not rec_d:
                messagebox.showerror("Error", "Received Date must be in DD-Mon-YYYY format!", parent=win)
                return
        try:
            cursor.execute("UPDATE requisition_tracking SET po_date=%s, actual_received_qty=%s, received_date=%s WHERE id=%s",
                           (po_d.strftime(REQ_DATE_FMT) if po_d else None, rec_q, rec_d.strftime(REQ_DATE_FMT) if rec_d else None, r["id"]))
            _rq_log("UPDATE_REQ_TRACKING", f"Req {r['req_no']} / {r['item_name']} ({r['factory']}): PO date={po_d.strftime(REQ_DATE_FMT) if po_d else 'Pending'}, Received={rec_q:g}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to update: {e}", parent=win)
            return
        messagebox.showinfo("Success", "PO / receiving information updated successfully!", parent=win)
        win.destroy()
        refresh_data()

    tk.Button(win, text="Save Tracking Update", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=14)


def _rq_show_erp_check(fac, code, name):
    inv = _rq_find_inventory(fac, code, name)
    if not inv:
        messagebox.showinfo("ERP Balance Check", "This item is not linked to any inventory record, so no ERP balance is available.")
        return
    erp_b, phys = inv[3] or 0.0, inv[4] or 0.0
    msg = f"Item: {inv[2]}\nERP Code: {inv[1]}\n\nERP Stock (as per ERP): {erp_b:g}\nPhysical Stock: {phys:g}\nVariance (Physical - ERP): {phys - erp_b:+g}"
    if _rq_is_temp_code(inv[1]):
        msg += "\n\nNote: this is still a TEMPORARY code - ERP balance cannot match until the real ERP code is entered."
    elif erp_b == 0:
        msg += "\n\nERP stock is 0. Use [3] ERP AUDIT > Import ERP Balance to load ERP balances for this code."
    messagebox.showinfo("ERP Balance Check", msg)


def edit_requisition_popup():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot edit requisitions!")
        return
    r = _rq_selected_row()
    if not r:
        return
    win = _rq_dialog(f"Edit Item / ERP Code [{r['req_no']}]", "480x560")
    tk.Label(win, text=f"Edit Requisition / ERP Code Mapping\nFactory: {r['factory']}", font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f").pack(pady=(10, 2))
    e_no = _rq_field(win, "Requisition No:", r["req_no"] or "")
    e_dept = _rq_field(win, "Department:", r["department"] or "")
    e_date = _rq_field(win, "Req Date (DD-Mon-YYYY):", r["req_date"] or "")
    e_qty = _rq_field(win, "Req Qty:", f"{r['req_qty']:g}")
    e_item = _rq_field(win, "Item Description:", r["item_name"] or "", 46)
    e_code = _rq_field(win, "ERP Code / Number:", r["prod_id"] or "", 36)
    tk.Label(win, text="Tip: when the real ERP code arrives, replace the TEMP code here. The Inventory item and its past transactions are\nupdated too, then the ERP balance check is shown.",
             bg="white", fg="#666", font=("Arial", 7, "italic"), justify="left").pack(anchor="w", padx=25, pady=6)

    def save():
        new_no, new_dept = e_no.get().strip(), e_dept.get().strip() or "Maintenance"
        new_item, new_code = e_item.get().strip(), e_code.get().strip()
        d = _req_parse_date(e_date.get())
        if not new_no or not new_item:
            messagebox.showerror("Error", "Requisition No and Item Description are required!", parent=win)
            return
        if not d:
            messagebox.showerror("Error", "Req Date must be in DD-Mon-YYYY format!", parent=win)
            return
        try:
            qty = float(e_qty.get().strip())
            if qty <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid Req Qty greater than 0!", parent=win)
            return
        fac = r["factory"]
        old_code, old_name = (r["prod_id"] or "").strip(), r["item_name"]
        try:
            inv = _rq_find_inventory(fac, old_code, old_name)
            if new_code:
                if inv:
                    cursor.execute("SELECT item_name FROM inventory WHERE prod_id=%s AND factory_name=%s AND sl_no<>%s", (new_code, fac, inv[0]))
                else:
                    cursor.execute("SELECT item_name FROM inventory WHERE prod_id=%s AND factory_name=%s", (new_code, fac))
                dup = cursor.fetchone()
                if dup:
                    messagebox.showerror("Duplicate ERP Code", f"ERP Code '{new_code}' is already used by '{dup[0]}' in {fac}!", parent=win)
                    return
            final_code = new_code
            if inv:
                if not final_code:
                    final_code = inv[1]
                if final_code != inv[1] or new_item != inv[2]:
                    cursor.execute("UPDATE inventory SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (final_code, new_item, inv[0], fac))
                    cursor.execute("UPDATE transactions SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (final_code, new_item, inv[0], fac))
            elif messagebox.askyesno("Item not in Inventory", f"'{new_item}' is not in Inventory of {fac}.\nAdd it to Inventory now" + ("" if new_code else " (temporary ERP code)") + "?", parent=win):
                final_code = _rq_create_inventory_item(fac, new_code, new_item, new_dept)
            if old_code:
                cursor.execute("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND prod_id=%s", (final_code, new_item, fac, old_code))
            else:
                cursor.execute("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND LOWER(item_name)=LOWER(%s) AND COALESCE(prod_id,'')=''", (final_code, new_item, fac, old_name))
            cursor.execute("UPDATE requisition_tracking SET req_no=%s, department=%s, req_date=%s, req_qty=%s, item_name=%s, prod_id=%s WHERE id=%s",
                           (new_no, new_dept, d.strftime(REQ_DATE_FMT), qty, new_item, final_code, r["id"]))
            _rq_log("EDIT_REQUISITION", f"Req ID {r['id']} ({fac}): item '{old_name}' [{old_code or '-'}] -> '{new_item}' [{final_code or '-'}], Req No {new_no}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Database Error", f"Failed to update: {e}", parent=win)
            return
        win.destroy()
        refresh_data()
        if final_code:
            _rq_show_erp_check(fac, final_code, new_item)
        else:
            messagebox.showinfo("Success", "Requisition updated successfully!")

    tk.Button(win, text="Save Changes", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), width=22, command=save).pack(pady=10)


def delete_requisition():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot delete requisitions!")
        return
    r = _rq_selected_row()
    if not r:
        return
    if not _rq_manager_authorized("Enter Store Manager Password to Delete Requisition:"):
        messagebox.showerror("Access Denied", "Incorrect Password! Only Store Manager can delete requisitions.")
        return
    if not messagebox.askyesno("Confirm Delete", f"Delete requisition {r['req_no']} - {r['item_name']}?\nThis cannot be undone."):
        return
    try:
        cursor.execute("DELETE FROM requisition_tracking WHERE id=%s", (r["id"],))
        _rq_log("DELETE_REQUISITION", f"Deleted requisition ID {r['id']} ({r['req_no']} - {r['item_name']}, {r['factory']})")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to delete: {e}")
        return
    refresh_data()


def generate_sourcing_email():
    if not require_login():
        return
    sel = tree_req.selection()
    ids = sel if sel else tree_req.get_children()
    pool = [rq_state["rows"][i] for i in ids if i in rq_state["rows"]]
    pending = [r for r in pool if r["pending"] > 0]
    sec_a = [r for r in pending if not _req_parse_date(r["po_date"]) and r["aud_qty"] > 0]
    sec_b = [r for r in pending if _req_parse_date(r["po_date"])]
    if not sec_a and not sec_b:
        waiting_audit = sum(1 for r in pending if r["aud_qty"] <= 0 and not _req_parse_date(r["po_date"]))
        extra = f"\n\n{waiting_audit} item(s) are still waiting for Audit approval - a PO cannot be requested before approval." if waiting_audit else ""
        messagebox.showinfo("Send Sourcing Email", "No audit-approved item with pending PO / delivery was found in the " + ("selected rows." if sel else "current list.") + extra)
        return

    facs = sorted({r["factory"] for r in sec_a + sec_b})
    fac_label = " & ".join(facs)
    multi = len(facs) > 1
    cursor.execute("SELECT full_name, role FROM users WHERE username=%s", (current_authenticated_user.get(),))
    me = cursor.fetchone() or (current_authenticated_user.get(), current_user_role.get())

    def block(rows, mode):
        out = []
        for n, r in enumerate(sorted(rows, key=lambda x: -x["age"]), 1):
            code = r["prod_id"] if r["prod_id"] and not _rq_is_temp_code(r["prod_id"]) else "ERP code awaited"
            fac_txt = f" | {r['factory']}" if multi else ""
            if mode == "A":
                aging = f"Pending for {r['age']} day(s) since requisition"
            else:
                aging = f"PO Date: {r['po_date']} | Waiting {r['since_po']} day(s) since PO"
            out.append(f"{n}. {r['item_name']} (ERP: {code})\n"
                       f"   Req No: {r['req_no']} | Req Date: {r['req_date']}{fac_txt}\n"
                       f"   Approved Qty: {r['aud_qty']:g} | Received: {r['rec_qty']:g} | PENDING QTY: {r['pending']:g}\n"
                       f"   {aging}")
        return "\n\n".join(out)

    lines = ["Dear Sourcing Manager,", "", f"Greetings from {fac_label} Store.", ""]
    if sec_a:
        lines += [f"We would like to bring to your kind attention that the following {len(sec_a)} audit-approved requisition item(s) are still waiting for Purchase Order (PO) issuance. "
                  "Due to the PO delay, material delivery and GRN are on hold at our end.", "",
                  "A. PO NOT YET RECEIVED", "-" * 40, block(sec_a, "A"), ""]
    if sec_b:
        lines += [("Additionally, " if sec_a else "") + f"the following {len(sec_b)} item(s) have PO issued but the material is not yet fully delivered / GRN is pending:", "",
                  "B. PO ISSUED - DELIVERY / GRN PENDING", "-" * 40, block(sec_b, "B"), ""]
    total_pending = sum(r["pending"] for r in sec_a + sec_b)
    lines += [f"Total items pending: {len(sec_a) + len(sec_b)}  |  Total pending quantity: {total_pending:g}", "",
              "As these items are required for smooth maintenance and production operations, we would highly appreciate it if you could kindly expedite the PO process and share the expected PO date and delivery schedule.",
              "", "Thank you for your kind support and cooperation.", "", "Best regards,", f"{me[0]}", f"{me[1]}, {fac_label}", f"Date: {datetime.now().strftime('%d-%b-%Y')}"]
    subject = f"Urgent: PO Required for Pending Requisition Items - {fac_label} ({datetime.now().strftime('%d-%b-%Y')})"

    win = _rq_dialog("Sourcing Manager Email (Auto-Generated)", "820x680")
    top = tk.Frame(win, bg="white")
    top.pack(fill="x", padx=15, pady=(10, 2))
    tk.Label(top, text="To (Sourcing Manager email):", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=0, sticky="w")
    e_to = tk.Entry(top, width=52, font=("Arial", 9))
    e_to.grid(row=0, column=1, padx=6, pady=2)
    e_to.insert(0, _req_get_setting("sourcing_manager_email", ""))
    tk.Label(top, text="Subject:", bg="white", font=("Arial", 8, "bold")).grid(row=1, column=0, sticky="w")
    e_sub = tk.Entry(top, width=90, font=("Arial", 9))
    e_sub.grid(row=1, column=1, padx=6, pady=2)
    e_sub.insert(0, subject)
    body_frame = tk.Frame(win, bg="white")
    body_frame.pack(fill="both", expand=True, padx=15, pady=4)
    txt = tk.Text(body_frame, font=("Consolas", 9), wrap="word")
    sb = ttk.Scrollbar(body_frame, orient="vertical", command=txt.yview)
    txt.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    txt.pack(side="left", fill="both", expand=True)
    txt.insert("1.0", "\n".join(lines))

    def _remember_to():
        if e_to.get().strip():
            _req_set_setting("sourcing_manager_email", e_to.get().strip())

    def copy_email():
        _remember_to()
        root.clipboard_clear()
        root.clipboard_append(f"To: {e_to.get().strip()}\nSubject: {e_sub.get().strip()}\n\n{txt.get('1.0', tk.END).strip()}")
        messagebox.showinfo("Copied", "Email copied to clipboard. You can paste it into Outlook / Gmail.", parent=win)

    def open_mail_app():
        _remember_to()
        body = txt.get("1.0", tk.END).strip()
        root.clipboard_clear()
        root.clipboard_append(f"To: {e_to.get().strip()}\nSubject: {e_sub.get().strip()}\n\n{body}")
        mb = body

        def build(b):
            return f"mailto:{urllib.parse.quote(e_to.get().strip(), safe='@,;')}?subject={urllib.parse.quote(e_sub.get().strip(), safe='')}&body={urllib.parse.quote(b, safe='')}"
        url = build(mb)
        truncated = False
        while len(url) > 1900 and len(mb) > 200:
            mb = mb[:int(len(mb) * 0.8)]
            url = build(mb + "\n\n[...email is long - the full text is copied to your clipboard, please paste it here]")
            truncated = True
        webbrowser.open(url)
        if truncated:
            messagebox.showinfo("Long Email", "The email is long, so it was shortened in the mail app.\nThe FULL email is copied to your clipboard - paste it into the message body.", parent=win)

    def save_email_txt():
        _remember_to()
        fp = filedialog.asksaveasfilename(defaultextension=".txt", initialfile="Sourcing_Email", filetypes=[("Text File", "*.txt")], parent=win)
        if fp:
            with open(fp, "w", encoding="utf-8") as f:
                f.write(f"To: {e_to.get().strip()}\nSubject: {e_sub.get().strip()}\n\n{txt.get('1.0', tk.END).strip()}\n")
            messagebox.showinfo("Saved", f"Email saved to:\n{fp}", parent=win)

    btns = tk.Frame(win, bg="white")
    btns.pack(fill="x", padx=15, pady=8)
    tk.Button(btns, text="📋 Copy Email", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=copy_email).pack(side="left", padx=3)
    tk.Button(btns, text="✉️ Open in Mail App", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=open_mail_app).pack(side="left", padx=3)
    tk.Button(btns, text="💾 Save as .txt", bg="#718096", fg="white", font=("Arial", 9, "bold"), command=save_email_txt).pack(side="left", padx=3)
    tk.Button(btns, text="Close", bg="#c53030", fg="white", font=("Arial", 9, "bold"), command=lambda: (_remember_to(), win.destroy())).pack(side="right", padx=3)
    _rq_log("GENERATE_SOURCING_EMAIL", f"Generated sourcing email for {len(sec_a)} PO-pending and {len(sec_b)} delivery-pending items ({fac_label})")
    conn.commit()


req_btn_bar = tk.Frame(req_frame, bg="white")
req_btn_bar.pack(fill="x", pady=(0, 2))
tk.Button(req_btn_bar, text="✔️ Audit Approved Qty (Audit Panel)", bg="#d69e2e", fg="white", font=("Arial", 8, "bold"), command=lambda: edit_audit_approved_popup()).pack(side="left", padx=2)
tk.Button(req_btn_bar, text="🚚 Update PO / Receiving", bg="#2b6cb0", fg="white", font=("Arial", 8, "bold"), command=lambda: update_tracking_popup()).pack(side="left", padx=2)
tk.Button(req_btn_bar, text="✏️ Edit Item / ERP Code", bg="#d97706", fg="white", font=("Arial", 8, "bold"), command=lambda: edit_requisition_popup()).pack(side="left", padx=2)
tk.Button(req_btn_bar, text="🗑️ Delete", bg="#c53030", fg="white", font=("Arial", 8, "bold"), command=lambda: delete_requisition()).pack(side="left", padx=2)
tk.Button(req_btn_bar, text="🧹 Remove Old Test Imports", bg="#718096", fg="white", font=("Arial", 8, "bold"), command=lambda: cleanup_old_test_imports()).pack(side="left", padx=2)
tk.Button(req_btn_bar, text="📧 Send Sourcing Email", bg="#6b21a8", fg="white", font=("Arial", 9, "bold"), command=lambda: generate_sourcing_email()).pack(side="right", padx=2)

req_search_bar = tk.Frame(req_frame, bg="white")
req_search_bar.pack(fill="x", pady=(2, 3))
tk.Label(req_search_bar, text="Search by Requisition No:", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(2, 4))
rq_search_entry = tk.Entry(req_search_bar, textvariable=rq_search_var, width=26, font=("Arial", 9))
rq_search_entry.pack(side="left", padx=(0, 4))

columns_req = ("ID", "Factory", "Req No", "Department", "Req Date", "Item Description", "Req Qty", "Audit Approved Qty", "Actual Received Qty", "Pending Rec Qty", "HO PO Date", "Received Date", "Status", "Delay")


def search_requisitions(event=None):
    load_requisitions()


def reset_requisition_search():
    rq_search_var.set("")
    load_requisitions()


def export_requisition_excel():
    rows = [tree_req.item(i, "values") for i in tree_req.get_children()]
    if not rows:
        messagebox.showwarning("No Data", "There are no requisitions in the table to download!")
        return
    fp = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Requisition_Tracking_Report", filetypes=[("Excel Files", "*.xlsx")])
    if not fp:
        return
    try:
        pd.DataFrame(rows, columns=list(columns_req)).to_excel(fp, index=False)
        messagebox.showinfo("Success", f"Requisition report exported to Excel successfully!\nPath: {fp}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export Excel: {e}")


def export_requisition_pdf():
    rows = [tree_req.item(i, "values") for i in tree_req.get_children()]
    if not rows:
        messagebox.showwarning("No Data", "There are no requisitions in the table to download!")
        return
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        messagebox.showerror("Missing Library", "PDF export requires the 'reportlab' library.\nInstall it with:  pip install reportlab\n\n(You can also use the Print button.)")
        return
    fp = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="Requisition_Tracking_Report", filetypes=[("PDF Document", "*.pdf")])
    if not fp:
        return
    try:
        styles = getSampleStyleSheet()
        cell = ParagraphStyle("rqcell", parent=styles["Normal"], fontSize=6.5, leading=7.5)
        head = ParagraphStyle("rqhead", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
        doc = SimpleDocTemplate(fp, pagesize=landscape(A4), leftMargin=18, rightMargin=18, topMargin=22, bottomMargin=22)
        flt = rq_search_var.get().strip()
        elements = [
            Paragraph("ERP Requisition & Sourcing Tracking Report", styles["Title"]),
            Paragraph(f"<b>Factory:</b> {html_lib.escape(selected_factory.get())} &nbsp;&nbsp; <b>Req No Filter:</b> {html_lib.escape(flt) if flt else 'None (all)'} &nbsp;&nbsp; <b>Generated:</b> {datetime.now().strftime('%d-%b-%Y %I:%M %p')}", styles["Normal"]),
            Paragraph(html_lib.escape(lbl_req_summary.cget("text")), styles["Normal"]),
            Spacer(1, 8),
        ]
        data = [[Paragraph(c, head) for c in columns_req]]
        for r in rows:
            data.append([Paragraph(html_lib.escape(str(x)), cell) for x in r])
        widths = [22, 56, 56, 52, 46, 105, 32, 40, 40, 40, 46, 46, 70, 42]
        table = Table(data, repeatRows=1, colWidths=widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3b6f")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        elements.append(table)
        doc.build(elements)
        messagebox.showinfo("Success", f"Requisition report exported to PDF successfully!\nPath: {fp}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {e}")


def print_requisition_report():
    items = tree_req.get_children()
    if not items:
        messagebox.showwarning("No Data", "There are no requisitions in the table to print!")
        return
    esc = html_lib.escape
    flt = rq_search_var.get().strip()
    head = "".join(f"<th>{esc(c)}</th>" for c in columns_req)
    body = ""
    for i in items:
        r = rq_state["rows"].get(i)
        cls = ""
        if r:
            if r["calc_status"] == "Fully Received":
                cls = ' class="done"'
            elif r["calc_status"] == "Partially Received":
                cls = ' class="part"'
            elif not _req_parse_date(r["po_date"]) and r["delay"] > REQ_PO_ALERT_DAYS:
                cls = ' class="late"'
        body += f"<tr{cls}>" + "".join(f"<td>{esc(str(v))}</td>" for v in tree_req.item(i, "values")) + "</tr>"
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Requisition Tracking Report</title>
<style>
@page {{ size: A4 landscape; margin: 10mm; }}
body {{ font-family: Arial, sans-serif; font-size: 11px; color: #1a202c; }}
h2 {{ margin: 0 0 2px 0; color: #1b3b6f; }}
.meta {{ margin-bottom: 6px; color: #4a5568; }}
table {{ border-collapse: collapse; width: 100%; }}
th {{ background: #1b3b6f; color: #fff; padding: 4px; border: 1px solid #999; font-size: 10px; }}
td {{ padding: 3px 4px; border: 1px solid #bbb; }}
tr.late td {{ background: #fde8e8; }} tr.part td {{ background: #fff8e1; }} tr.done td {{ background: #e8f5e9; }}
.legend {{ margin-top: 8px; font-size: 10px; color: #4a5568; }}
</style></head><body>
<h2>ERP Requisition, Audit Qty &amp; Sourcing Received Tracking Report</h2>
<div class="meta"><b>Factory:</b> {esc(selected_factory.get())} &nbsp;|&nbsp; <b>Req No Filter:</b> {esc(flt) if flt else 'None (all)'} &nbsp;|&nbsp; <b>Printed by:</b> {esc(current_authenticated_user.get())} &nbsp;|&nbsp; <b>Date:</b> {datetime.now().strftime('%d-%b-%Y %I:%M %p')}</div>
<div class="meta">{esc(lbl_req_summary.cget('text'))}</div>
<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>
<div class="legend">Red = PO pending more than {REQ_PO_ALERT_DAYS} days | Yellow = partially received | Green = fully received. Delay = days since requisition while PO is pending (or days HO took to issue PO).</div>
<script>window.onload = function() {{ window.print(); }};</script></body></html>"""
    try:
        fp = os.path.join(tempfile.gettempdir(), f"Requisition_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(doc)
        webbrowser.open(Path(fp).as_uri())
    except Exception as e:
        messagebox.showerror("Print Error", f"Failed to prepare the print report: {e}")


tk.Button(req_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: search_requisitions()).pack(side="left", padx=2)
tk.Button(req_search_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 8, "bold"), command=lambda: reset_requisition_search()).pack(side="left", padx=2)
tk.Button(req_search_bar, text="🖨️ Print Report", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: print_requisition_report()).pack(side="right", padx=2)
tk.Button(req_search_bar, text="Download PDF", bg="#b71c1c", fg="white", font=("Arial", 9, "bold"), command=lambda: export_requisition_pdf()).pack(side="right", padx=2)
tk.Button(req_search_bar, text="Download Excel", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: export_requisition_excel()).pack(side="right", padx=2)
rq_search_entry.bind("<Return>", search_requisitions)

lbl_req_summary = tk.Label(req_frame, text="", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", anchor="w")
lbl_req_summary.pack(side="bottom", fill="x", pady=(3, 0))
lbl_req_detail = tk.Label(req_frame, text="Select a requisition row to see its ERP code mapping, ERP balance check and aging details.",
                          font=("Arial", 8), bg="#e8f4fd", fg="#0d47a1", anchor="w", justify="left", padx=6, pady=3)
lbl_req_detail.pack(side="bottom", fill="x", pady=(3, 0))

tree_req = ttk.Treeview(req_frame, columns=columns_req, show="headings", height=16)
col_widths_req = [40, 110, 110, 130, 85, 170, 60, 85, 85, 85, 85, 85, 170, 80]
for col, w in zip(columns_req, col_widths_req):
    tree_req.heading(col, text=col)
    tree_req.column(col, width=w, anchor="w", stretch=True)
tree_req.tag_configure("po_late", background="#fde8e8")
tree_req.tag_configure("partial", background="#fff8e1")
tree_req.tag_configure("done", background="#e8f5e9")
tree_req.pack(fill="both", expand=True, side="left", pady=(2, 0))
req_sc = ttk.Scrollbar(req_frame, orient="vertical", command=tree_req.yview)
req_sc.pack(side="right", fill="y", pady=(2, 0))
tree_req.configure(yscrollcommand=req_sc.set)


def show_req_detail(event=None):
    r = _rq_selected_row(show_error=False)
    if not r:
        lbl_req_detail.config(text="Select a requisition row to see its ERP code mapping, ERP balance check and aging details.")
        return
    code = (r["prod_id"] or "").strip()
    inv = _rq_find_inventory(r["factory"], code, r["item_name"])
    if inv:
        code = inv[1]
    if not code:
        code_txt = "Not mapped to inventory"
    elif _rq_is_temp_code(code):
        code_txt = f"{code} (temporary - real ERP code pending)"
    else:
        code_txt = code
    if inv:
        erp_b, phys = inv[3] or 0.0, inv[4] or 0.0
        bal_txt = f"ERP Balance: {erp_b:g} | Physical Stock: {phys:g} | Variance: {phys - erp_b:+g}"
    else:
        bal_txt = "ERP Balance: n/a (item not in inventory)"
    if _req_parse_date(r["po_date"]):
        aging = f"PO issued {r['delay']} day(s) after requisition; waiting {r['since_po']} day(s) for delivery since PO"
    else:
        aging = f"Requisition is {r['age']} day(s) old and HO PO is still PENDING"
    lbl_req_detail.config(text=f"Req {r['req_no']} | {r['item_name']} | ERP Code: {code_txt} | {bal_txt}\n"
                               f"Received {r['rec_qty']:g} of {r['base']:g} | Pending {r['pending']:g} | {aging}")


tree_req.bind("<<TreeviewSelect>>", show_req_detail)


def load_requisitions():
    for item in tree_req.get_children():
        tree_req.delete(item)
    rq_state["rows"].clear()
    fac = selected_factory.get()
    term = rq_search_var.get().strip().lower()
    q = ("SELECT id, factory_name, req_no, department, req_date, item_name, req_qty, audit_approved_qty, actual_received_qty, "
         "po_date, received_date, status, po_delay_days, COALESCE(prod_id,'') FROM requisition_tracking WHERE 1=1")
    params = []
    if "CONSOLIDATED" not in fac:
        q += " AND factory_name = %s"
        params.append(fac)
    if term:
        q += " AND LOWER(COALESCE(req_no,'')) ILIKE %s"
        params.append(f"%{term}%")
    q += " ORDER BY id DESC"
    cursor.execute(q, params)
    fetched = cursor.fetchall()

    total = full = part = po_wait = 0
    pending_total, max_delay, synced = 0.0, 0, False
    for (r_id, f_name, r_no, dept, r_date, i_name, req_q, aud_q, rec_q, po_d, rec_d, stat, delay_db, code) in fetched:
        r = {"id": r_id, "factory": f_name, "req_no": r_no, "department": dept, "req_date": r_date, "item_name": i_name,
             "req_qty": req_q or 0.0, "aud_qty": aud_q or 0.0, "rec_qty": rec_q or 0.0, "po_date": po_d, "rec_date": rec_d, "prod_id": code}
        r.update(_req_calc(r))
        if stat != r["calc_status"] or (delay_db or 0) != r["delay"]:
            cursor.execute("UPDATE requisition_tracking SET status=%s, po_delay_days=%s WHERE id=%s", (r["calc_status"], r["delay"], r_id))
            synced = True
        has_po = _req_parse_date(po_d) is not None
        tags = ()
        if r["calc_status"] == "Fully Received":
            tags, full = ("done",), full + 1
        elif r["calc_status"] == "Partially Received":
            tags, part = ("partial",), part + 1
        elif not has_po and r["aud_qty"] > 0 and r["delay"] > REQ_PO_ALERT_DAYS:
            tags = ("po_late",)
        if not has_po and r["pending"] > 0 and r["aud_qty"] > 0:
            po_wait += 1
            max_delay = max(max_delay, r["delay"])
        total += 1
        pending_total += r["pending"]
        iid = tree_req.insert("", "end", values=(r_id, f_name, r_no, dept, r_date, i_name, f"{r['req_qty']:g}", f"{r['aud_qty']:g}",
                                                 f"{r['rec_qty']:g}", f"{r['pending']:g}", po_d if po_d else "Pending PO",
                                                 rec_d if rec_d else "Not Received", r["calc_status"], f"{r['delay']} Days"), tags=tags)
        rq_state["rows"][iid] = r
    if synced:
        conn.commit()
    lbl_req_summary.config(text=f"Requisitions: {total}  |  Fully Received: {full}  |  Partially Received: {part}  |  Awaiting HO PO: {po_wait}  |  Total Pending Qty: {pending_total:,.2f}  |  Longest PO Delay: {max_delay} Days")
    show_req_detail()


# ================= TAB 7: REPAIR & RETURNS =================
repair_frame = tk.Frame(tab_repair, bg="white", padx=5, pady=5)
repair_frame.pack(fill="both", expand=True)

repair_editing_id = {"id": None}

repair_form = tk.LabelFrame(repair_frame, text=" 🛠️ Repair / Return Entry Form ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=8, pady=5)
repair_form.pack(fill="x", pady=(0, 4))

rp_gate_var = tk.StringVar()
rp_track_var = tk.StringVar()
rp_return_type_var = tk.StringVar(value="Returnable")
rp_item_var = tk.StringVar()
rp_qty_var = tk.StringVar()
rp_supplier_var = tk.StringVar()
rp_type_var = tk.StringVar(value="Repair")
rp_sent_var = tk.StringVar(value=datetime.now().strftime("%d-%b-%Y"))
rp_return_date_var = tk.StringVar()
rp_status_var = tk.StringVar(value="Pending Return")


def _rp_label(text, r, c):
    tk.Label(repair_form, text=text, bg="white", font=("Arial", 8, "bold")).grid(row=r, column=c, sticky="w", padx=(4, 2), pady=2)


_rp_label("Gate Pass No:", 0, 0)
tk.Entry(repair_form, textvariable=rp_gate_var, width=18, font=("Arial", 9)).grid(row=0, column=1, padx=(0, 10), pady=2)
_rp_label("Return Type:", 0, 2)
ttk.Combobox(repair_form, textvariable=rp_return_type_var, values=["Returnable", "Non-Returnable"], width=16, state="readonly", font=("Arial", 9)).grid(row=0, column=3, padx=(0, 10), pady=2)
_rp_label("Item Description:", 0, 4)
tk.Entry(repair_form, textvariable=rp_item_var, width=32, font=("Arial", 9)).grid(row=0, column=5, padx=(0, 10), pady=2)
_rp_label("Qty:", 0, 6)
tk.Entry(repair_form, textvariable=rp_qty_var, width=10, font=("Arial", 9)).grid(row=0, column=7, padx=(0, 4), pady=2)

_rp_label("Supplier Name:", 1, 0)
tk.Entry(repair_form, textvariable=rp_supplier_var, width=18, font=("Arial", 9)).grid(row=1, column=1, padx=(0, 10), pady=2)
_rp_label("Type:", 1, 2)
ttk.Combobox(repair_form, textvariable=rp_type_var, values=["Repair", "Warranty Claim", "Rejected Return", "Other"], width=16, state="readonly", font=("Arial", 9)).grid(row=1, column=3, padx=(0, 10), pady=2)
_rp_label("Sent Date:", 1, 4)
tk.Entry(repair_form, textvariable=rp_sent_var, width=16, font=("Arial", 9)).grid(row=1, column=5, sticky="w", padx=(0, 10), pady=2)
_rp_label("Status:", 1, 6)
ttk.Combobox(repair_form, textvariable=rp_status_var, values=["Pending Return", "Returned", "Closed"], width=14, state="readonly", font=("Arial", 9)).grid(row=1, column=7, padx=(0, 4), pady=2)

_rp_label("Tracking Code:", 2, 0)
tk.Entry(repair_form, textvariable=rp_track_var, width=18, font=("Arial", 9)).grid(row=2, column=1, padx=(0, 10), pady=2)
_rp_label("Return Date:", 2, 2)
tk.Entry(repair_form, textvariable=rp_return_date_var, width=18, font=("Arial", 9)).grid(row=2, column=3, padx=(0, 10), pady=2)
tk.Label(repair_form, text="Tracking Code: leave blank to auto-generate (REP-0001...).  Dates: DD-Mon-YYYY, e.g. 12-Oct-2026 (Return Date blank = not returned yet)",
         bg="white", fg="#666", font=("Arial", 7, "italic")).grid(row=2, column=4, columnspan=4, sticky="w", pady=2)

repair_btn_bar = tk.Frame(repair_frame, bg="white")
repair_btn_bar.pack(fill="x", pady=(0, 3))


def _repair_write_check():
    if not require_login():
        return False
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot modify repair records!")
        return False
    if "CONSOLIDATED" in selected_factory.get():
        messagebox.showerror("Error Security", "Cannot add/edit repair records in CONSOLIDATED view!\nPlease select a specific active factory.")
        return False
    return True


def _repair_read_form():
    gate = rp_gate_var.get().strip()
    track = rp_track_var.get().strip()
    item = rp_item_var.get().strip()
    supplier = rp_supplier_var.get().strip()
    sent = rp_sent_var.get().strip()
    ret_date = rp_return_date_var.get().strip()
    if not gate or not item or not supplier:
        messagebox.showerror("Error", "Gate Pass No, Item Description and Supplier Name are required!")
        return None
    try:
        qty = float(rp_qty_var.get().strip())
        if qty <= 0:
            raise ValueError
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid Qty greater than 0!")
        return None
    if not sent:
        messagebox.showerror("Error", "Sent Date is required!")
        return None
    for label, val in (("Sent Date", sent), ("Return Date", ret_date)):
        if val:
            try:
                datetime.strptime(val, "%d-%b-%Y")
            except ValueError:
                messagebox.showerror("Error", f"{label} must be in DD-Mon-YYYY format (e.g. 12-Oct-2026)!")
                return None
    status = rp_status_var.get()
    if ret_date and status == "Pending Return":
        status = "Returned"
    return {"gate": gate, "track": track, "item": item, "supplier": supplier, "qty": qty, "sent": sent,
            "ret_date": ret_date, "status": status,
            "source_type": rp_type_var.get(), "return_type": rp_return_type_var.get()}


def clear_repair_form():
    repair_editing_id["id"] = None
    rp_gate_var.set("")
    rp_track_var.set("")
    rp_return_type_var.set("Returnable")
    rp_item_var.set("")
    rp_qty_var.set("")
    rp_supplier_var.set("")
    rp_type_var.set("Repair")
    rp_sent_var.set(datetime.now().strftime("%d-%b-%Y"))
    rp_return_date_var.set("")
    rp_status_var.set("Pending Return")
    btn_rp_update.config(state="disabled")
    for it in tree_repair.selection():
        tree_repair.selection_remove(it)


def add_repair_item():
    if not _repair_write_check():
        return
    d = _repair_read_form()
    if not d:
        return
    fac = selected_factory.get()
    try:
        if d["track"]:
            cursor.execute("SELECT id FROM repair_returns WHERE tracking_code=%s", (d["track"],))
            if cursor.fetchone():
                messagebox.showerror("Duplicate", f"Tracking Code '{d['track']}' already exists! Use a different code or leave it blank to auto-generate.")
                return
        cursor.execute("""INSERT INTO repair_returns (factory_name, tracking_code, gate_pass_no, item_name, qty, source_type, return_type,
                          supplier_name, sent_date, return_date, status, remarks, officer_name)
                          VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
                       (fac, d["track"] if d["track"] else "TMP", d["gate"], d["item"], d["qty"], d["source_type"], d["return_type"], d["supplier"],
                        d["sent"], d["ret_date"] if d["ret_date"] else None, d["status"], "", current_authenticated_user.get()))
        new_id = cursor.fetchone()[0]
        tracking = d["track"] if d["track"] else f"REP-{new_id:04d}"
        if not d["track"]:
            cursor.execute("UPDATE repair_returns SET tracking_code=%s WHERE id=%s", (tracking, new_id))
        _audit("ADD_REPAIR", f"Added repair/return item {tracking} ({d['item']}, Qty {d['qty']:g}) for {fac}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to add item: {e}")
        return
    messagebox.showinfo("Success", f"Item added successfully!\nTracking Code: {tracking}")
    clear_repair_form()
    refresh_data()


def load_selected_repair_into_form(event=None):
    sel = tree_repair.selection()
    if not sel:
        return
    v = tree_repair.item(sel[0], "values")
    repair_editing_id["id"] = v[0]
    rp_track_var.set(v[1])
    rp_gate_var.set(v[3])
    rp_item_var.set(v[4])
    rp_qty_var.set(v[5])
    rp_type_var.set(v[6])
    rp_return_type_var.set(v[7])
    rp_supplier_var.set(v[8])
    rp_sent_var.set(v[9])
    rp_return_date_var.set("" if v[10] in ("", "Not Returned", "None") else v[10])
    rp_status_var.set(v[11])
    btn_rp_update.config(state="normal")


def update_repair_item():
    if not _repair_write_check():
        return
    rid = repair_editing_id["id"]
    if not rid:
        messagebox.showerror("Selection Error", "Please select a record from the table first (click a row to load it into the form), then edit and press Update!")
        return
    d = _repair_read_form()
    if not d:
        return
    try:
        new_track = d["track"]
        if new_track:
            cursor.execute("SELECT id FROM repair_returns WHERE tracking_code=%s AND id<>%s", (new_track, rid))
            if cursor.fetchone():
                messagebox.showerror("Duplicate", f"Tracking Code '{new_track}' already exists on another record!")
                return
            cursor.execute("UPDATE repair_returns SET tracking_code=%s WHERE id=%s", (new_track, rid))
        cursor.execute("""UPDATE repair_returns SET gate_pass_no=%s, item_name=%s, qty=%s, source_type=%s, return_type=%s, supplier_name=%s,
                          sent_date=%s, return_date=%s, status=%s WHERE id=%s""",
                       (d["gate"], d["item"], d["qty"], d["source_type"], d["return_type"], d["supplier"], d["sent"],
                        d["ret_date"] if d["ret_date"] else None, d["status"], rid))
        _audit("EDIT_REPAIR", f"Edited repair/return record ID {rid}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to update record: {e}")
        return
    messagebox.showinfo("Success", f"Record ID {rid} updated successfully!")
    clear_repair_form()
    refresh_data()


def delete_repair_item():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot delete repair records!")
        return
    sel = tree_repair.selection()
    if not sel:
        messagebox.showerror("Selection Error", "Please select a record from the table to delete!")
        return
    v = tree_repair.item(sel[0], "values")
    rid = v[0]
    if not messagebox.askyesno("Confirm Delete", f"Delete record ID {rid} ({v[1]} - {v[4]})?\nThis cannot be undone."):
        return
    try:
        cursor.execute("DELETE FROM repair_returns WHERE id=%s", (rid,))
        _audit("DELETE_REPAIR", f"Deleted repair/return record ID {rid} ({v[1]})")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to delete record: {e}")
        return
    clear_repair_form()
    refresh_data()
    messagebox.showinfo("Success", f"Record ID {rid} deleted successfully!")


btn_rp_add = tk.Button(repair_btn_bar, text="➕ Add Item", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), width=12, command=lambda: add_repair_item())
btn_rp_add.pack(side="left", padx=2)
btn_rp_update = tk.Button(repair_btn_bar, text="✏️ Update Selected", bg="#d97706", fg="white", font=("Arial", 9, "bold"), command=lambda: update_repair_item(), state="disabled")
btn_rp_update.pack(side="left", padx=2)
btn_rp_delete = tk.Button(repair_btn_bar, text="🗑️ Delete Selected", bg="#c53030", fg="white", font=("Arial", 9, "bold"), command=lambda: delete_repair_item())
btn_rp_delete.pack(side="left", padx=2)
btn_rp_clear = tk.Button(repair_btn_bar, text="Clear Form", bg="#718096", fg="white", font=("Arial", 9, "bold"), command=lambda: clear_repair_form())
btn_rp_clear.pack(side="left", padx=2)

repair_search_bar = tk.Frame(repair_frame, bg="white")
repair_search_bar.pack(fill="x", pady=(2, 3))
tk.Label(repair_search_bar, text="Search (Item / Gate Pass / Supplier / Tracking Code):", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(2, 4))
rp_search_var = tk.StringVar()
rp_search_entry = tk.Entry(repair_search_bar, textvariable=rp_search_var, width=30, font=("Arial", 9))
rp_search_entry.pack(side="left", padx=(0, 4))

columns_repair = ("ID", "Tracking Code", "Factory", "Gate Pass No", "Item Description", "Qty", "Type", "Return Type", "Supplier Name", "Sent Date", "Return Date", "Status", "Aging")


def search_repair_records(event=None):
    load_repair_returns()


def reset_repair_search():
    rp_search_var.set("")
    load_repair_returns()


def _repair_table_rows():
    return [tree_repair.item(i, "values") for i in tree_repair.get_children()]


def export_repair_excel():
    rows = _repair_table_rows()
    if not rows:
        messagebox.showwarning("No Data", "There are no records in the table to download!")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile="Repair_Returns_Report", filetypes=[("Excel Files", "*.xlsx")])
    if not file_path:
        return
    try:
        pd.DataFrame(rows, columns=list(columns_repair)).to_excel(file_path, index=False)
        messagebox.showinfo("Success", f"Repair & Returns exported to Excel successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export Excel: {e}")


def export_repair_pdf():
    rows = _repair_table_rows()
    if not rows:
        messagebox.showwarning("No Data", "There are no records in the table to download!")
        return
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    except ImportError:
        messagebox.showerror("Missing Library", "PDF export requires the 'reportlab' library.\nInstall it with:  pip install reportlab")
        return
    file_path = filedialog.asksaveasfilename(defaultextension=".pdf", initialfile="Repair_Returns_Report", filetypes=[("PDF Document", "*.pdf")])
    if not file_path:
        return
    try:
        styles = getSampleStyleSheet()
        cell = ParagraphStyle("cell", parent=styles["Normal"], fontSize=7, leading=8)
        head = ParagraphStyle("head", parent=cell, textColor=colors.white, fontName="Helvetica-Bold")
        doc = SimpleDocTemplate(file_path, pagesize=landscape(A4), leftMargin=20, rightMargin=20, topMargin=24, bottomMargin=24)
        flt = rp_search_var.get().strip()
        elements = [
            Paragraph("Repair & Returns Report", styles["Title"]),
            Paragraph(f"<b>Factory:</b> {html_lib.escape(selected_factory.get())} &nbsp;&nbsp; <b>Filter:</b> {html_lib.escape(flt) if flt else 'None (all records)'} &nbsp;&nbsp; <b>Records:</b> {len(rows)} &nbsp;&nbsp; <b>Generated:</b> {datetime.now().strftime('%d-%b-%Y %I:%M %p')}", styles["Normal"]),
            Spacer(1, 8),
        ]
        data = [[Paragraph(c, head) for c in columns_repair]]
        for r in rows:
            data.append([Paragraph(html_lib.escape(str(x)), cell) for x in r])
        widths = [24, 50, 62, 52, 110, 28, 48, 52, 70, 50, 50, 50, 44]
        table = Table(data, repeatRows=1, colWidths=widths)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1b3b6f")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7fafc")]),
        ]))
        elements.append(table)
        doc.build(elements)
        messagebox.showinfo("Success", f"Repair & Returns exported to PDF successfully!\nPath: {file_path}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to export PDF: {e}")


tk.Button(repair_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: search_repair_records()).pack(side="left", padx=2)
tk.Button(repair_search_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 8, "bold"), command=lambda: reset_repair_search()).pack(side="left", padx=2)
tk.Button(repair_search_bar, text="Download Excel", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: export_repair_excel()).pack(side="right", padx=2)
tk.Button(repair_search_bar, text="Download PDF", bg="#b71c1c", fg="white", font=("Arial", 9, "bold"), command=lambda: export_repair_pdf()).pack(side="right", padx=2)
rp_search_entry.bind("<Return>", search_repair_records)

repair_tree_frame = tk.Frame(repair_frame, bg="white")
repair_tree_frame.pack(fill="both", expand=True)
tree_repair = ttk.Treeview(repair_tree_frame, columns=columns_repair, show="headings", height=10)
for col in columns_repair:
    tree_repair.heading(col, text=col)
    tree_repair.column(col, width=90, anchor="w", stretch=True)
tree_repair.pack(fill="both", expand=True, side="left", pady=(2, 0))
rp_sc = ttk.Scrollbar(repair_tree_frame, orient="vertical", command=tree_repair.yview)
rp_sc.pack(side="right", fill="y", pady=(2, 0))
tree_repair.configure(yscrollcommand=rp_sc.set)
tree_repair.bind("<<TreeviewSelect>>", load_selected_repair_into_form)
tree_repair.bind("<Double-1>", load_selected_repair_into_form)


def load_repair_returns():
    for item in tree_repair.get_children():
        tree_repair.delete(item)
    fac = selected_factory.get()
    query = ("SELECT id, tracking_code, factory_name, gate_pass_no, item_name, qty, source_type, return_type, supplier_name, "
             "sent_date, return_date, status FROM repair_returns WHERE 1=1")
    params = []
    if "CONSOLIDATED" not in fac:
        query += " AND factory_name = %s"
        params.append(fac)
    term = rp_search_var.get().strip().lower()
    if term:
        query += " AND (LOWER(COALESCE(item_name,'')) ILIKE %s OR LOWER(COALESCE(gate_pass_no,'')) ILIKE %s OR LOWER(COALESCE(supplier_name,'')) ILIKE %s OR LOWER(COALESCE(tracking_code,'')) ILIKE %s)"
        params.extend([f"%{term}%"] * 4)
    query += " ORDER BY id DESC"
    cursor.execute(query, params)
    for r in cursor.fetchall():
        rid, trk, f_name, gp, item, qty, s_type, r_type, sup, sent, ret, status = r
        try:
            start = datetime.strptime(str(sent).strip(), "%d-%b-%Y")
            end = datetime.strptime(str(ret).strip(), "%d-%b-%Y") if ret else datetime.now()
            aging = f"{max((end - start).days, 0)} Days"
        except (ValueError, TypeError):
            aging = "N/A"
        tree_repair.insert("", "end", values=(rid, trk, f_name, gp, item, f"{qty:g}" if qty is not None else "0", s_type, r_type, sup,
                                              sent, ret if ret else "Not Returned", status, aging))


# ================= TAB 8: LEDGER (MONTHLY REPORT) =================
monthly_frame = tk.Frame(tab_monthly_report, bg="white", padx=5, pady=5)
monthly_frame.pack(fill="both", expand=True)
columns_monthly_rep = ("Factory", "Officer", "SL", "ERP Code", "Item Name", "Qty", "Type", "Total Price", "Notes", "Date & Time")
tree_monthly_report = ttk.Treeview(monthly_frame, columns=columns_monthly_rep, show="headings", height=15)
for col in columns_monthly_rep:
    tree_monthly_report.heading(col, text=col)
    tree_monthly_report.column(col, width=100, anchor="w", stretch=True)
tree_monthly_report.pack(fill="both", expand=True, side="left", pady=(2, 0))


def load_monthly_report():
    for item in tree_monthly_report.get_children():
        tree_monthly_report.delete(item)
    fac = selected_factory.get()
    query = ("SELECT t.factory_name, t.officer_name, t.sl_no, t.prod_id, t.item_name, t.qty, t.trans_type, t.notes, t.date, t.time, i.unit_price "
             "FROM transactions t LEFT JOIN inventory i ON t.sl_no = i.sl_no AND t.factory_name = i.factory_name WHERE 1=1")
    params = []
    if "CONSOLIDATED" not in fac:
        query += " AND t.factory_name = %s"
        params.append(fac)
    query += " ORDER BY t.id DESC"
    cursor.execute(query, params)
    for row in cursor.fetchall():
        dt_str = f"{row[8]} {row[9]}"
        qty = row[5] or 0
        price = row[10] if row[10] and row[10] > 0 else 0.0
        val = qty * price
        tree_monthly_report.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], qty, _tlabel(row[6]), f"{val:,.2f} BDT", row[7], dt_str))


# ================= TAB 9: FORECAST =================
forecast_frame = tk.Frame(tab_forecast, bg="white", padx=10, pady=10)
forecast_frame.pack(fill="both", expand=True)

fc_state = {"rows": {}}
fc_cur_plan_var = tk.StringVar()
fc_next_plan_var = tk.StringVar()
fc_note_var = tk.StringVar()
fc_search_var = tk.StringVar()
fc_only_cons_var = tk.BooleanVar(value=True)

fc_plan_frame = tk.LabelFrame(forecast_frame, text=" 🏭 Production Plan (input drives the next-month forecast) ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=8, pady=5)
fc_plan_frame.pack(fill="x", pady=(0, 4))

lbl_fc_cur_month = tk.Label(fc_plan_frame, text="Current Month Production Plan:", bg="white", font=("Arial", 8, "bold"))
lbl_fc_cur_month.grid(row=0, column=0, sticky="w", padx=(2, 3), pady=2)
fc_cur_entry = tk.Entry(fc_plan_frame, textvariable=fc_cur_plan_var, width=12, font=("Arial", 9))
fc_cur_entry.grid(row=0, column=1, padx=(0, 4), pady=2)
tk.Label(fc_plan_frame, text="pcs", bg="white", fg="#666", font=("Arial", 8)).grid(row=0, column=2, sticky="w", padx=(0, 14))

lbl_fc_next_month = tk.Label(fc_plan_frame, text="Next Month Production Plan:", bg="white", font=("Arial", 8, "bold"))
lbl_fc_next_month.grid(row=0, column=3, sticky="w", padx=(2, 3), pady=2)
fc_next_entry = tk.Entry(fc_plan_frame, textvariable=fc_next_plan_var, width=12, font=("Arial", 9))
fc_next_entry.grid(row=0, column=4, padx=(0, 4), pady=2)
tk.Label(fc_plan_frame, text="pcs", bg="white", fg="#666", font=("Arial", 8)).grid(row=0, column=5, sticky="w", padx=(0, 14))

tk.Label(fc_plan_frame, text="Plan Remarks (e.g. Denim Pant):", bg="white", font=("Arial", 8, "bold")).grid(row=0, column=6, sticky="w", padx=(2, 3), pady=2)
fc_note_entry = tk.Entry(fc_plan_frame, textvariable=fc_note_var, width=26, font=("Arial", 9))
fc_note_entry.grid(row=0, column=7, padx=(0, 8), pady=2)

lbl_fc_factor = tk.Label(fc_plan_frame, text="", bg="white", fg="#0d47a1", font=("Arial", 8, "bold"), anchor="w", justify="left")
lbl_fc_factor.grid(row=1, column=0, columnspan=9, sticky="w", padx=2, pady=(2, 0))


def _fc_month_info(now=None):
    now = now or datetime.now()
    cy, cm = now.year, now.month
    ny, nm = (cy + 1, 1) if cm == 12 else (cy, cm + 1)
    return {"now": now, "cur_key": f"{cy}-{cm:02d}", "next_key": f"{ny}-{nm:02d}",
            "cur_label": f"{calendar.month_abbr[cm]}-{cy}", "next_label": f"{calendar.month_abbr[nm]}-{ny}",
            "cur_days": calendar.monthrange(cy, cm)[1], "next_days": calendar.monthrange(ny, nm)[1]}


def _fc_num(text):
    t = str(text).replace(",", "").strip()
    if t == "":
        return 0.0
    v = float(t)
    if v < 0:
        raise ValueError("negative")
    return v


def _fc_get_plans():
    cursor.execute("SELECT factory_name, plan_month, plan_qty, plan_note FROM production_plans")
    return {(f, m): (q or 0.0, n or "") for f, m, q, n in cursor.fetchall()}


def _fc_factor_for(plans, factory, mi):
    cur_q = plans.get((factory, mi["cur_key"]), (0.0, ""))[0]
    next_q = plans.get((factory, mi["next_key"]), (0.0, ""))[0]
    if cur_q > 0 and next_q > 0:
        return next_q / cur_q, cur_q, next_q
    return 1.0, cur_q, next_q


def update_factor_label():
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        lbl_fc_factor.config(text="Consolidated view: each factory's own saved production plan is applied. Select a single factory to edit its plan.")
        return
    try:
        cur_q = _fc_num(fc_cur_plan_var.get())
        next_q = _fc_num(fc_next_plan_var.get())
    except ValueError:
        lbl_fc_factor.config(text="Enter valid numbers for the production plan.")
        return
    if cur_q > 0 and next_q > 0:
        f = next_q / cur_q
        pct = (f - 1) * 100
        if abs(pct) < 0.005:
            why = "Production plan is unchanged, so consumption is expected to stay at the current level."
        elif pct > 0:
            why = f"Next month plan ({next_q:,.0f} pcs) is {pct:.1f}% HIGHER than current month ({cur_q:,.0f} pcs) → expected consumption is {pct:.1f}% higher."
        else:
            why = f"Next month plan ({next_q:,.0f} pcs) is {abs(pct):.1f}% LOWER than current month ({cur_q:,.0f} pcs) → expected consumption is {abs(pct):.1f}% lower."
        lbl_fc_factor.config(text=f"Production Factor = {next_q:,.0f} ÷ {cur_q:,.0f} = {f:.2f}x   |   {why}")
    else:
        lbl_fc_factor.config(text="Production Factor = 1.00x   |   Enter BOTH Current and Next Month plan (pcs) to adjust the forecast for production changes. Until then the daily average is used as is.")


def load_plan_fields():
    fac = selected_factory.get()
    mi = _fc_month_info()
    lbl_fc_cur_month.config(text=f"Current Month ({mi['cur_label']}) Production Plan:")
    lbl_fc_next_month.config(text=f"Next Month ({mi['next_label']}) Production Plan:")
    if "CONSOLIDATED" in fac:
        fc_cur_plan_var.set("")
        fc_next_plan_var.set("")
        fc_note_var.set("")
        for e in (fc_cur_entry, fc_next_entry, fc_note_entry):
            e.config(state="disabled")
        btn_fc_save_plan.config(state="disabled")
    else:
        for e in (fc_cur_entry, fc_next_entry, fc_note_entry):
            e.config(state="normal")
        btn_fc_save_plan.config(state="normal")
        plans = _fc_get_plans()
        cq, cn = plans.get((fac, mi["cur_key"]), (0.0, ""))
        nq, nn = plans.get((fac, mi["next_key"]), (0.0, ""))
        fc_cur_plan_var.set(f"{cq:g}" if cq else "")
        fc_next_plan_var.set(f"{nq:g}" if nq else "")
        fc_note_var.set(nn or cn)
    update_factor_label()


def save_production_plan():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot change production plans!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error Security", "Cannot save a production plan in CONSOLIDATED view!\nPlease select a specific factory.")
        return
    try:
        cur_q = _fc_num(fc_cur_plan_var.get())
        next_q = _fc_num(fc_next_plan_var.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter valid positive numbers for the production plans!")
        return
    mi = _fc_month_info()
    note = fc_note_var.get().strip()
    now_s = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user = current_authenticated_user.get()
    try:
        for key, qty in ((mi["cur_key"], cur_q), (mi["next_key"], next_q)):
            cursor.execute("SELECT id FROM production_plans WHERE factory_name=%s AND plan_month=%s", (fac, key))
            row = cursor.fetchone()
            if row:
                cursor.execute("UPDATE production_plans SET plan_qty=%s, plan_note=%s, updated_by=%s, updated_at=%s WHERE id=%s", (qty, note, user, now_s, row[0]))
            else:
                cursor.execute("INSERT INTO production_plans (factory_name, plan_month, plan_qty, plan_note, updated_by, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                               (fac, key, qty, note, user, now_s))
        _audit("SAVE_PROD_PLAN", f"{fac}: {mi['cur_label']}={cur_q:g} pcs, {mi['next_label']}={next_q:g} pcs. {note}")
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Database Error", f"Failed to save production plan: {e}")
        return
    messagebox.showinfo("Success", "Production plan saved. Forecast recalculated.")
    update_factor_label()
    load_forecast()


btn_fc_save_plan = tk.Button(fc_plan_frame, text="💾 Save Plan & Recalculate", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: save_production_plan())
btn_fc_save_plan.grid(row=0, column=8, padx=4, pady=2)
fc_cur_plan_var.trace_add("write", lambda *a: update_factor_label())
fc_next_plan_var.trace_add("write", lambda *a: update_factor_label())

fc_search_bar = tk.Frame(forecast_frame, bg="white")
fc_search_bar.pack(fill="x", pady=(2, 3))
tk.Label(fc_search_bar, text="Item Name / ERP Code:", bg="white", font=("Arial", 8, "bold")).pack(side="left", padx=(2, 4))
fc_search_entry = tk.Entry(fc_search_bar, textvariable=fc_search_var, width=30, font=("Arial", 9))
fc_search_entry.pack(side="left", padx=(0, 4))
tk.Button(fc_search_bar, text="🔍 Search", bg="#1b3b6f", fg="white", font=("Arial", 8, "bold"), command=lambda: load_forecast()).pack(side="left", padx=2)
tk.Button(fc_search_bar, text="Show All", bg="#718096", fg="white", font=("Arial", 8, "bold"),
          command=lambda: (fc_search_var.set(""), load_forecast())).pack(side="left", padx=2)
tk.Checkbutton(fc_search_bar, text="Only items with consumption in last 3 months / this month", variable=fc_only_cons_var, bg="white",
               font=("Arial", 8), command=lambda: load_forecast()).pack(side="left", padx=12)
fc_search_entry.bind("<Return>", lambda e: load_forecast())

fc_detail_frame = tk.LabelFrame(forecast_frame, text=" 📊 Item Forecast Analysis (select an item below or search by name) ", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", padx=8, pady=4)
fc_detail_frame.pack(fill="x", pady=(0, 4))

fc_detail_vars = {}
fc_detail_fields = [
    ("item", "Item"), ("cur_cons", "Current Month Consumption"), ("l3m", "Last 03 Months Consumption"), ("avg", "Average Daily Consumption"),
    ("stock", "Current Stock"), ("proj", "Next Month Projected Consumption"), ("net", "Net Requisition Qty"), ("cost", "Estimated Cost"),
]
for idx, (key, caption) in enumerate(fc_detail_fields):
    r, c = divmod(idx, 4)
    cell = tk.Frame(fc_detail_frame, bg="#f7fafc", highlightbackground="#cbd5e0", highlightthickness=1, padx=8, pady=3)
    cell.grid(row=r, column=c, sticky="nsew", padx=3, pady=3)
    fc_detail_frame.grid_columnconfigure(c, weight=1)
    tk.Label(cell, text=caption, bg="#f7fafc", fg="#4a5568", font=("Arial", 8)).pack(anchor="w")
    fc_detail_vars[key] = tk.StringVar(value="—")
    big_color = "#c53030" if key in ("net", "cost") else "#1b3b6f"
    tk.Label(cell, textvariable=fc_detail_vars[key], bg="#f7fafc", fg=big_color, font=("Arial", 10, "bold"), anchor="w", wraplength=300, justify="left").pack(anchor="w")

tk.Label(fc_detail_frame,
         text="Formula: Avg Daily = Last 3 Months Consumption ÷ days in those months  |  Next Month Projected = Avg Daily × days in next month × Production Factor  |  Net Requisition = Projected − Current Stock (min 0, rounded up)  |  Estimated Cost = Net Requisition × Unit Price",
         bg="white", fg="#718096", font=("Arial", 7, "italic"), anchor="w", justify="left", wraplength=1300).grid(row=2, column=0, columnspan=4, sticky="w", padx=3)

lbl_fc_summary = tk.Label(forecast_frame, text="", font=("Arial", 9, "bold"), bg="white", fg="#1b3b6f", anchor="w")
lbl_fc_summary.pack(side="bottom", fill="x", pady=(3, 0))

fc_tree_frame = tk.Frame(forecast_frame, bg="white")
fc_tree_frame.pack(fill="both", expand=True)
columns_fc = ("Factory", "SL", "ERP Code", "Item Name", "Current Stock", "Current Month Consumption", "Last 3 M. Consumption",
              "Avg Daily Consumption", "Next Month Projected", "Net Requisition", "Unit Price", "Estimated Cost")
tree_forecast = ttk.Treeview(fc_tree_frame, columns=columns_fc, show="headings", height=10)
col_w_fc = [100, 35, 70, 180, 85, 150, 140, 140, 135, 105, 75, 105]
for col, w in zip(columns_fc, col_w_fc):
    tree_forecast.heading(col, text=col)
    tree_forecast.column(col, width=w, anchor="w" if col in ("Factory", "Item Name") else "e", stretch=True)
tree_forecast.tag_configure("need", background="#fff5f5")
tree_forecast.pack(fill="both", expand=True, side="left", pady=5)
fc_sc = ttk.Scrollbar(fc_tree_frame, orient="vertical", command=tree_forecast.yview)
fc_sc.pack(side="right", fill="y", pady=5)
tree_forecast.configure(yscrollcommand=fc_sc.set)


def compute_forecast_rows():
    fac = selected_factory.get()
    mi = _fc_month_info()
    now = mi["now"]
    cy, cm = now.year, now.month
    sy, sm = cy, cm - 3
    if sm <= 0:
        sm += 12
        sy -= 1
    l3_start = datetime(sy, sm, 1)
    l3_end = datetime(cy, cm, 1)
    l3_days = max((l3_end - l3_start).days, 1)

    plans = _fc_get_plans()

    q = "SELECT factory_name, sl_no, qty, date FROM transactions WHERE trans_type ILIKE '%%Issue%%'"
    params = []
    if "CONSOLIDATED" not in fac:
        q += " AND factory_name = %s"
        params.append(fac)
    cursor.execute(q, params)
    cur_cons, l3_cons = {}, {}
    for f_name, sl, qty, d in cursor.fetchall():
        try:
            dt = datetime.strptime(str(d).strip(), "%d-%b-%Y")
        except ValueError:
            continue
        key = (f_name, sl)
        if dt.year == cy and dt.month == cm:
            cur_cons[key] = cur_cons.get(key, 0.0) + (qty or 0.0)
        elif l3_start <= dt < l3_end:
            l3_cons[key] = l3_cons.get(key, 0.0) + (qty or 0.0)

    q = "SELECT factory_name, sl_no, prod_id, item_name, current_stock, unit_price FROM inventory"
    params = []
    if "CONSOLIDATED" not in fac:
        q += " WHERE factory_name = %s"
        params.append(fac)
    cursor.execute(q, params)

    rows = []
    for f_name, sl, p_id, name, stock, price in cursor.fetchall():
        stock = stock or 0.0
        price = price or 0.0
        cm_q = cur_cons.get((f_name, sl), 0.0)
        l3_q = l3_cons.get((f_name, sl), 0.0)
        avg_daily = l3_q / l3_days
        factor, cur_plan, next_plan = _fc_factor_for(plans, f_name, mi)
        projected = avg_daily * mi["next_days"] * factor
        net_raw = projected - stock
        net_req = math.ceil(net_raw - 1e-9) if net_raw > 0 else 0
        rows.append({"factory": f_name, "sl": sl, "prod_id": p_id, "name": name, "stock": stock, "cur_cons": cm_q,
                     "l3m": l3_q, "avg": avg_daily, "proj": projected, "net": net_req, "price": price,
                     "cost": net_req * price, "factor": factor, "cur_plan": cur_plan, "next_plan": next_plan,
                     "l3_days": l3_days, "next_days": mi["next_days"], "next_label": mi["next_label"]})
    return rows


def show_forecast_detail(event=None):
    sel = tree_forecast.selection()
    if not sel or sel[0] not in fc_state["rows"]:
        return
    r = fc_state["rows"][sel[0]]
    fc_detail_vars["item"].set(f"{r['name']}  [{r['prod_id']}]  - {r['factory']}")
    fc_detail_vars["cur_cons"].set(f"{r['cur_cons']:,.2f}")
    fc_detail_vars["l3m"].set(f"{r['l3m']:,.2f}  (over {r['l3_days']} days)")
    fc_detail_vars["avg"].set(f"{r['avg']:,.3f} / day")
    fc_detail_vars["stock"].set(f"{r['stock']:,.2f}")
    if r["cur_plan"] > 0 and r["next_plan"] > 0:
        plan_txt = f"  (plan {r['cur_plan']:,.0f} → {r['next_plan']:,.0f} pcs, x{r['factor']:.2f})"
    else:
        plan_txt = "  (no plan factor, x1.00)"
    fc_detail_vars["proj"].set(f"{r['proj']:,.2f} for {r['next_label']}{plan_txt}")
    fc_detail_vars["net"].set(f"{r['net']:,.0f}")
    fc_detail_vars["cost"].set(f"{r['cost']:,.2f} BDT  (@ {r['price']:,.2f})")


tree_forecast.bind("<<TreeviewSelect>>", show_forecast_detail)


def load_forecast():
    for item in tree_forecast.get_children():
        tree_forecast.delete(item)
    fc_state["rows"].clear()
    for var in fc_detail_vars.values():
        var.set("—")
    rows = compute_forecast_rows()
    term = fc_search_var.get().strip().lower()
    if term:
        rows = [r for r in rows if term in str(r["name"]).lower() or term in str(r["prod_id"]).lower()]
    if fc_only_cons_var.get():
        rows = [r for r in rows if r["cur_cons"] > 0 or r["l3m"] > 0]
    rows.sort(key=lambda r: (-r["cost"], str(r["name"]).lower()))
    total_net, total_cost = 0.0, 0.0
    first_iid = None
    for r in rows:
        iid = tree_forecast.insert("", "end", values=(r["factory"], r["sl"], r["prod_id"], r["name"], f"{r['stock']:,.2f}", f"{r['cur_cons']:,.2f}",
                                                       f"{r['l3m']:,.2f}", f"{r['avg']:,.3f}", f"{r['proj']:,.2f}", f"{r['net']:,.0f}",
                                                       f"{r['price']:,.2f}", f"{r['cost']:,.2f} BDT"),
                                   tags=("need",) if r["net"] > 0 else ())
        fc_state["rows"][iid] = r
        if first_iid is None:
            first_iid = iid
        total_net += r["net"]
        total_cost += r["cost"]
    items_need = sum(1 for r in rows if r["net"] > 0)
    lbl_fc_summary.config(text=f"Items Listed: {len(rows)}  |  Items Needing Requisition: {items_need}  |  Total Net Requisition Qty: {total_net:,.0f}  |  Total Estimated Cost: {total_cost:,.2f} BDT")
    if term and len(rows) == 1:
        tree_forecast.selection_set(first_iid)


# ================= TAB 10: BUDGET =================
cat_budget_frame = tk.Frame(tab_category_budget, bg="white", padx=10, pady=10)
cat_budget_frame.pack(fill="both", expand=True)
columns_cat_rep = ("Factory", "Department", "Item Category", "Allocated Budget", "Actual Cost", "Remaining Budget", "Status")
tree_cat_budget = ttk.Treeview(cat_budget_frame, columns=columns_cat_rep, show="headings", height=15)
for col in columns_cat_rep:
    tree_cat_budget.heading(col, text=col)
    tree_cat_budget.column(col, width=110, anchor="w", stretch=True)
tree_cat_budget.pack(fill="both", expand=True, pady=5)

# ================= TRANSACTION CORE LOGIC =================
ISSUE_COOLDOWN_DAYS = 3


def _recent_issue_info(fac, sl_no, ref_dt):
    """Latest issue of the same item within the cooldown window before ref_dt -> (datetime, qty, officer) or None."""
    cursor.execute("SELECT date, time, qty, officer_name FROM transactions WHERE factory_name=%s AND sl_no=%s AND trans_type ILIKE '%%Issue%%' ORDER BY id DESC", (fac, sl_no))
    for d, t, q, off in cursor.fetchall():
        dt = None
        for txt, fmt in ((f"{d} {t}", "%d-%b-%Y %I:%M %p"), (str(d), "%d-%b-%Y")):
            try:
                dt = datetime.strptime(str(txt).strip(), fmt)
                break
            except ValueError:
                continue
        if dt and 0 <= (ref_dt - dt).total_seconds() < ISSUE_COOLDOWN_DAYS * 86400:
            return dt, q, off
    return None


def clear_transaction_form():
    """Blanks the entry form after a successful save (the selected date is kept for quick entry)."""
    entry_search.delete(0, tk.END)
    entry_item.delete(0, tk.END)
    entry_qty.delete(0, tk.END)
    chk_verify_var.set(False)
    text_notes.delete("1.0", tk.END)
    lbl_prod_info.config(text=EMPTY_PROD_TXT, fg="#0d47a1", bg="#e8f4fd")
    entry_item.focus_set()


def _insert_transaction(fac, officer, sl_no, prod_id, item_name, qty, trans_type, day, notes, date_s, time_s, verification, grn_status="Not Required"):
    cursor.execute("""INSERT INTO transactions (factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, day, notes, date, time,
                      verification_status, erp_grn_status) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                   (fac, officer, sl_no, prod_id, item_name, qty, trans_type, day, notes, date_s, time_s, verification, grn_status))


def save_transaction():
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Permission Denied", "Auditor role has read-only access and cannot record store transactions!")
        return
    fac = selected_factory.get()
    if "CONSOLIDATED" in fac:
        messagebox.showerror("Error Security", "Cannot record transactions in CONSOLIDATED view!\nPlease select a specific active factory.")
        return

    officer = current_authenticated_user.get()
    val = entry_item.get().strip()
    try:
        qty = float(entry_qty.get())
    except ValueError:
        messagebox.showerror("Error", "Please enter a valid numeric quantity!")
        return
    if qty <= 0:
        messagebox.showerror("Error", "Quantity must be greater than zero!")
        return

    trans_type = TRANS_TYPE_CODES.get(combo_type.get(), "Supplier. Rec")

    try:
        tx_dt = datetime.strptime(tx_date_var.get().strip(), "%d-%b-%Y")
    except ValueError:
        messagebox.showerror("Error", "Date must be in DD-Mon-YYYY format (e.g. 12-Oct-2026)!")
        return
    if tx_dt.date() > datetime.now().date():
        messagebox.showerror("Error", "A future date cannot be used for a transaction!")
        return

    notes = text_notes.get("1.0", tk.END).strip()
    current_date = tx_dt.strftime("%d-%b-%Y")
    day = tx_dt.day
    current_time = datetime.now().strftime("%I:%M %p")

    # NEW: exact resolution. SL No wins over ERP code; an ambiguous code asks for the SL No instead of guessing.
    prod, cands = _resolve_item(fac, val)
    if not prod:
        if len(cands) > 1:
            messagebox.showerror("Multiple Items Match",
                                 f"'{val}' matches {len(cands)} items. Enter the exact SL No:\n\n{_ambiguous_text(cands)}")
        else:
            messagebox.showerror("Error", "Invalid SL No or ERP Code for selected factory!")
        return
    sl_no, prod_id, _f, item_name, item_size, current_stock, _erp, _price = prod
    current_stock = current_stock or 0.0

    verification = "Verified"
    if trans_type in ["Issued", "Internal Issue"]:
        ticked = chk_verify_var.get()
        ref_dt = datetime.combine(tx_dt.date(), datetime.now().time())
        recent = _recent_issue_info(fac, sl_no, ref_dt)
        if recent and not ticked:
            messagebox.showwarning(
                "Physical Verification Required",
                f"'{item_name}' was already issued on {recent[0].strftime('%d-%b-%Y %I:%M %p')} (Qty {recent[1]:g}, by {recent[2]}) - within the last {ISSUE_COOLDOWN_DAYS} days.\n\n"
                "Please physically verify the stock in the store, tick the 'Physically Verified' box and save again.")
            return
        verification = "Physically Verified" if ticked else "Not Required"

    # Automatic inter-unit transfer when stock is short (matched by product NAME + SIZE)
    if trans_type in ["Issued", "Internal Issue"] and qty > current_stock:
        shortage = qty - current_stock
        other_fac = _other_factory(fac)
        other_res = _find_same_item_in_other_unit(prod_id, item_name, other_fac, item_size)

        if not other_res:
            messagebox.showerror("Insufficient Stock", f"Shortage of {shortage:g} pcs. No product with the same name and size [{item_size or '-'}] was found in [{other_fac}] for transfer.")
            return

        other_stock = other_res[3] or 0.0

        if other_res[4] in ("code", "fuzzy"):
            why = ("has the SAME ERP code but a DIFFERENT name:" if other_res[4] == "code"
                   else "has a SIMILAR product name (spelling differs):")
            if not messagebox.askyesno("Confirm Same Product?",
                                       f"{other_fac} {why}\n\n"
                                       f"  {fac}: {item_name} [{prod_id}]\n  {other_fac}: {other_res[2]} [{other_res[1]}]\n\n"
                                       "Treat them as the same product and transfer?"):
                messagebox.showinfo("Cancelled", "Transfer cancelled. Stock balances remain unchanged.")
                return

        if other_stock < shortage:
            messagebox.showerror("Insufficient Stock", f"Shortage of {shortage:g} pcs cannot be fulfilled! Other unit [{other_fac}] only has {other_stock:g} pcs available.")
            return

        confirm = messagebox.askyesno(
            "Inter-Unit Stock Shortage & Transfer Alert",
            f"⚠️ Shortage Detected in {fac}!\n\n"
            f"- Requested Qty: {qty:g}\n- Available Stock in {fac}: {current_stock:g}\n- Shortage: {shortage:g}\n\n"
            f"[{other_fac}] has {other_stock:g} pcs available of [{other_res[1]} {other_res[2]}].\n\n"
            f"Do you want to automatically transfer {shortage:g} pcs from {other_fac} to {fac} and complete the issue?"
        )
        if not confirm:
            messagebox.showinfo("Cancelled", "Transfer cancelled. Stock balances remain unchanged.")
            return

        try:
            transfer_ref = f"TRF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
            same_item = (other_res[2] == item_name and other_res[1] == prod_id)
            cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (shortage, other_res[0], other_fac))
            cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (shortage, sl_no, fac))
            cursor.execute("""
                INSERT INTO inter_factory_transfers (transfer_ref, source_factory, dest_factory, prod_id, item_name, qty, transfer_date, transfer_time, initiated_by, status, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'Completed', %s)
            """, (transfer_ref, other_fac, fac, prod_id, item_name, shortage, current_date, current_time, officer,
                  "Auto-transfer for shortage during issue" + ("" if same_item else f" (source item: {other_res[2]} [{other_res[1]}])")))
            cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, fac))
            _insert_transaction(fac, officer, sl_no, prod_id, item_name, qty, trans_type, day,
                                f"{notes} [Auto-transferred {shortage:g} pcs from {other_fac}]".strip(),
                                current_date, current_time, verification)
            _audit("AUTO_TRANSFER", f"Transferred {shortage:g} pcs from {other_fac} to {fac} for product {prod_id} [{item_size}]")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Transfer Error", f"Inter-unit transfer failed and rolled back: {e}")
            return
        clear_transaction_form()
        messagebox.showinfo("Success", f"Inter-unit transfer of {shortage:g} pcs completed and issue processed successfully!")
        refresh_data()
        return

    # Receipts (increase stock) - always on THIS SL row (zero-stock item is updated, never duplicated)
    if trans_type in ["Supplier. Rec", "Internal Rec", "Stock Adjustment (+)"]:
        grn_status = "Pending" if trans_type == "Supplier. Rec" else "Not Required"
        try:
            cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, fac))
            _insert_transaction(fac, officer, sl_no, prod_id, item_name, qty, trans_type, day, notes,
                                current_date, current_time, "Verified", grn_status)
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Failed to save receipt (rolled back): {e}")
            return
        clear_transaction_form()
        messagebox.showinfo("Success", f"Receipt transaction recorded successfully for {fac}!")
        refresh_data()
        return

    # Issues / negative adjustments (decrease stock)
    if qty > current_stock:
        messagebox.showerror("Stock Shortage", f"Available stock ({current_stock:g} pcs) is less than requested qty ({qty:g} pcs)!")
        return
    try:
        cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, fac))
        _insert_transaction(fac, officer, sl_no, prod_id, item_name, qty, trans_type, day, notes,
                            current_date, current_time, verification)
        conn.commit()
    except Exception as e:
        conn.rollback()
        messagebox.showerror("Error", f"Failed to save transaction (rolled back): {e}")
        return
    clear_transaction_form()
    messagebox.showinfo("Success", f"Issue transaction successfully recorded for {fac}!")
    refresh_data()


# ================= TAB 11: DAILY WORK SHEET =================
DS_FACTORIES = ["KC Washing Plant", "Windy Washing LTD"]
DS_UOM_CHOICES = ["Pcs", "Kg"]
DS_SCREEN_BLANK_ROWS = 8
DS_PRINT_MIN_BLANK_ROWS = 10
DS_PRINT_TARGET_ROWS = 26

DS_KG_KEYWORDS = ("super enamel wire", "enamel paint", "anamel paint", "weather coat", "plastic paint", "thinner", "cement",
                  " rope", "welding rod", "wood chips", "perak", "heatproof fiber", "decoloring agent", "gear oil", "lube oil",
                  "compressor fluid", "poly bag", "jeet powder", "copper busbar", "varnish", "blizing rod", "thermocol ball")


def _ds_guess_uom(item_name, stock=None):
    n = " " + str(item_name or "").lower()
    if "filter" not in n:
        if any(k in n for k in DS_KG_KEYWORDS):
            return "Kg"
    try:
        if stock is not None and abs(float(stock) - round(float(stock))) > 1e-9:
            return "Kg"
    except (TypeError, ValueError):
        pass
    return "Pcs"


def _ds_autoset_uom_once():
    """One time only: items still on default 'Pcs' that are Kg-type get 'Kg'. Edit UOM changes them later."""
    try:
        if _req_get_setting("uom_autoset_v1", "") == "done":
            return
        cursor.execute("SELECT ctid, item_name, current_stock, unit_name FROM inventory")
        for rid, name, stk, unit in cursor.fetchall():
            if (unit is None or str(unit).strip() in ("", "Pcs")) and _ds_guess_uom(name, stk) == "Kg":
                cursor.execute("UPDATE inventory SET unit_name='Kg' WHERE ctid=%s", (rid,))
        conn.commit()
        _req_set_setting("uom_autoset_v1", "done")
    except Exception:
        conn.rollback()


_ds_autoset_uom_once()

ds_factory_var = tk.StringVar(value=selected_factory.get() if selected_factory.get() in DS_FACTORIES else DS_FACTORIES[0])
ds_date_var = tk.StringVar(value=datetime.now().strftime("%d-%b-%Y"))
ds_show_all_var = tk.BooleanVar(value=False)
ds_autofill_var = tk.BooleanVar(value=False)
ds_row_map = {}


def _ds_parse_date(text):
    text = (text or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _ds_fmt(v):
    if abs(v) < 1e-9:
        return "-"
    return f"{v:,.2f}".rstrip("0").rstrip(".")


def _ds_stock_fmt(v):
    return "0" if abs(v) < 1e-9 else f"{v:,.2f}".rstrip("0").rstrip(".")


def _ds_sync_factory():
    fac = selected_factory.get()
    if fac in DS_FACTORIES:
        ds_factory_var.set(fac)


def compute_daily_sheet_rows(date_obj, fac, show_all):
    """Rows: (sl_no, item_name, size, unit, current_stock, daily_issue, daily_received, short_qty, excess_qty).
    sl_no is the REAL Master Inventory SL No - the same number used in [1] TRANSACTIONS.
    Short / Excess = physical (current) stock vs ERP stock, same rule as [3] ERP AUDIT."""
    d_str = date_obj.strftime("%d-%b-%Y")
    cursor.execute("""
        SELECT i.sl_no, i.item_name, COALESCE(i.size,''), COALESCE(NULLIF(i.unit_name, ''), 'Pcs'), COALESCE(i.current_stock, 0), COALESCE(i.erp_stock, 0),
               COALESCE((SELECT SUM(t.qty) FROM transactions t WHERE t.factory_name=i.factory_name AND t.sl_no=i.sl_no AND t.date=%s AND t.trans_type IN ('Issued', 'Internal Issue')), 0),
               COALESCE((SELECT SUM(t.qty) FROM transactions t WHERE t.factory_name=i.factory_name AND t.sl_no=i.sl_no AND t.date=%s AND t.trans_type IN ('Supplier. Rec', 'Internal Rec')), 0)
        FROM inventory i WHERE i.factory_name=%s ORDER BY i.sl_no
    """, (d_str, d_str, fac))
    rows = []
    for sl, name, size, unit, cur, erp, issue, recv in cursor.fetchall():
        diff = round(cur - erp, 4)
        short, exc = (abs(diff) if diff < 0 else 0.0), (diff if diff > 0 else 0.0)
        if not show_all and abs(cur) < 1e-9 and short == 0 and exc == 0 and issue <= 0 and recv <= 0:
            continue
        rows.append((sl, name, size, unit, cur, issue, recv, short, exc))
    return rows


def load_daily_sheet(silent=False):
    for item in tree_ds.get_children():
        tree_ds.delete(item)
    ds_row_map.clear()
    d = _ds_parse_date(ds_date_var.get())
    if not d:
        lbl_ds_title.config(text="Daily Issue Status For Month")
        lbl_ds_meta.config(text="Invalid date - please enter it like 12-Oct-2026")
        if not silent:
            messagebox.showerror("Invalid Date", "Please enter the date in DD-Mon-YYYY format (e.g. 12-Oct-2026).")
        return
    fac = ds_factory_var.get()
    rows = compute_daily_sheet_rows(d, fac, ds_show_all_var.get())
    auto = ds_autofill_var.get()
    lbl_ds_title.config(text=f"Daily Issue Status For Month: {d.strftime('%B-%Y')}")
    lbl_ds_meta.config(text=f"Date: {d.strftime('%d-%b-%Y')}     |     Factory Name: {fac}")
    n_short = n_exc = 0
    for (sl, name, size, unit, cur, issue, recv, short, exc) in rows:
        tag = "short" if short > 0 else ("excess" if exc > 0 else "")
        if short > 0:
            n_short += 1
        if exc > 0:
            n_exc += 1
        iid = tree_ds.insert("", "end", values=(sl, name, size, unit, _ds_stock_fmt(cur), _ds_fmt(issue) if auto else "",
                                                _ds_fmt(recv) if auto else "", _ds_fmt(short), _ds_fmt(exc)), tags=(tag,) if tag else ())
        ds_row_map[iid] = (fac, sl)
    for j in range(DS_SCREEN_BLANK_ROWS):
        tree_ds.insert("", "end", values=("", "", "", "", "", "", "", "", ""), tags=("blank",))
    lbl_ds_summary.config(text=f"Items on sheet: {len(rows)}  |  Short Items: {n_short}  |  Excess Items: {n_exc}  |  SL No = Master Inventory SL (same as [1] TRANSACTIONS)  |  Double-click a row to issue it")


def ds_load_to_issue(event=None):
    """Double-click on a sheet row: opens [1] TRANSACTIONS with that exact SL No selected."""
    sel = tree_ds.selection()
    if not sel or sel[0] not in ds_row_map:
        return
    fac, sl = ds_row_map[sel[0]]
    if selected_factory.get() != fac:
        selected_factory.set(fac)
        refresh_data()
    entry_search.delete(0, tk.END)
    entry_item.delete(0, tk.END)
    entry_item.insert(0, str(sl))
    fetch_product_info()
    notebook.select(tab_trans)
    entry_qty.focus_set()


def edit_ds_uom(event=None):
    if not require_login():
        return
    if current_user_role.get() == "Auditor":
        messagebox.showerror("Access Denied", "Auditor role has read-only access and cannot change the UOM!")
        return
    sel = tree_ds.selection()
    if not sel or sel[0] not in ds_row_map:
        messagebox.showinfo("Select Item", "Please select an item row first, then click Edit UOM.")
        return
    fac, sl = ds_row_map[sel[0]]
    cursor.execute("SELECT item_name, COALESCE(NULLIF(unit_name, ''), 'Pcs') FROM inventory WHERE sl_no=%s AND factory_name=%s", (sl, fac))
    r = cursor.fetchone()
    if not r:
        return
    item_name, cur_unit = r
    win = tk.Toplevel(root)
    win.title("Edit UOM")
    win.geometry("420x190")
    win.config(bg="white")
    win.grab_set()
    tk.Label(win, text=item_name, font=("Arial", 10, "bold"), bg="white", fg="#1b3b6f", wraplength=390).pack(pady=(12, 4))
    uom_var = tk.StringVar(value=cur_unit if cur_unit in DS_UOM_CHOICES else "Pcs")
    row_f = tk.Frame(win, bg="white")
    row_f.pack(pady=4)
    tk.Label(row_f, text="UOM:", font=("Arial", 9, "bold"), bg="white").pack(side="left", padx=4)
    ttk.Combobox(row_f, textvariable=uom_var, values=DS_UOM_CHOICES, width=8, state="readonly", font=("Arial", 9, "bold")).pack(side="left")
    same_var = tk.BooleanVar(value=True)
    tk.Checkbutton(win, text="Apply to every item with this same name (both factories)", variable=same_var, bg="white", font=("Arial", 8)).pack()

    def save_uom():
        try:
            if same_var.get():
                cursor.execute("UPDATE inventory SET unit_name=%s WHERE LOWER(TRIM(item_name))=LOWER(TRIM(%s))", (uom_var.get(), item_name))
            else:
                cursor.execute("UPDATE inventory SET unit_name=%s WHERE sl_no=%s AND factory_name=%s", (uom_var.get(), sl, fac))
            _audit("EDIT_UOM", f"{item_name}: UOM -> {uom_var.get()}")
            conn.commit()
        except Exception as e:
            conn.rollback()
            messagebox.showerror("Error", f"Failed to update UOM: {e}", parent=win)
            return
        win.destroy()
        load_daily_sheet(silent=True)

    bf = tk.Frame(win, bg="white")
    bf.pack(pady=10)
    tk.Button(bf, text="Save UOM", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), width=12, command=save_uom).pack(side="left", padx=5)
    tk.Button(bf, text="Cancel", bg="#718096", fg="white", font=("Arial", 9, "bold"), width=10, command=win.destroy).pack(side="left", padx=5)


def print_daily_sheet():
    d = _ds_parse_date(ds_date_var.get())
    if not d:
        messagebox.showerror("Invalid Date", "Please enter the date in DD-Mon-YYYY format (e.g. 12-Oct-2026).")
        return
    fac = ds_factory_var.get()
    rows = compute_daily_sheet_rows(d, fac, ds_show_all_var.get())
    auto = ds_autofill_var.get()
    esc = html_lib.escape
    body = ""
    for (sl, name, size, unit, cur, issue, recv, short, exc) in rows:
        cls = ' class="short"' if short > 0 else (' class="excess"' if exc > 0 else "")
        body += (f"<tr{cls}><td class=\"c\">{sl}</td><td class=\"l\">{esc(str(name))}</td><td class=\"c\">{esc(str(size or '-'))}</td>"
                 f"<td class=\"c\">{esc(str(unit))}</td>"
                 f"<td class=\"r\">{_ds_stock_fmt(cur)}</td><td class=\"r\">{_ds_fmt(issue) if auto else ''}</td><td class=\"r\">{_ds_fmt(recv) if auto else ''}</td>"
                 f"<td class=\"r\">{_ds_fmt(short)}</td><td class=\"r\">{_ds_fmt(exc)}</td></tr>")
    blanks = max(DS_PRINT_MIN_BLANK_ROWS, DS_PRINT_TARGET_ROWS - len(rows))
    for _ in range(blanks):
        body += "<tr class=\"blank\">" + "<td></td>" * 9 + "</tr>"
    heads = ["SL No.", "Item Name", "Size", "Unit Name", "Current Stock", "Daily Issue", "Daily Received", "Short Qty", "Excess Qty"]
    head = "".join(f"<th>{h}</th>" for h in heads)
    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Daily Work Sheet</title>
<style>
@page {{ size: A4 portrait; margin: 0; }}
html, body {{ margin: 0; padding: 0; }}
body {{ font-family: Arial, sans-serif; font-size: 11px; color: #111; padding: 0 12mm; }}
table.page {{ width: 100%; border-collapse: collapse; }}
.sp {{ height: 11mm; }}
.hdr {{ text-align: center; margin-bottom: 4mm; }}
.hdr .t {{ font-size: 17px; font-weight: bold; color: #1b3b6f; }}
.hdr .m {{ margin-top: 3px; font-size: 12px; }}
.hdr .m span {{ margin: 0 14px; }}
table.sheet {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
table.sheet th {{ background: #1b3b6f; color: #fff; border: 1px solid #333; padding: 5px 3px; font-size: 10px; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
table.sheet td {{ border: 1px solid #333; padding: 3px 4px; height: 7.2mm; vertical-align: middle; word-wrap: break-word; }}
.c {{ text-align: center; }} .l {{ text-align: left; }} .r {{ text-align: right; }}
tr.short td {{ background: #fde8e8; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
tr.excess td {{ background: #fff3e0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
tr {{ page-break-inside: avoid; }}
thead.rep {{ display: table-header-group; }}
</style></head><body>
<table class="page"><thead><tr><td><div class="sp"></div></td></tr></thead>
<tbody><tr><td>
<div class="hdr"><div class="t">Daily Issue Status For Month: {d.strftime('%B-%Y')}</div>
<div class="m"><span><b>Date:</b> {d.strftime('%d-%b-%Y')}</span><span><b>Factory Name:</b> {esc(fac)}</span></div></div>
<table class="sheet"><colgroup><col style="width:7%"><col style="width:27%"><col style="width:9%"><col style="width:8%"><col style="width:11%"><col style="width:11%"><col style="width:11%"><col style="width:8%"><col style="width:8%"></colgroup>
<thead class="rep"><tr>{head}</tr></thead><tbody>{body}</tbody></table>
</td></tr></tbody>
<tfoot><tr><td><div class="sp"></div></td></tr></tfoot></table>
<script>window.onload = function() {{ window.print(); }};</script></body></html>"""
    try:
        fp = os.path.join(tempfile.gettempdir(), f"Daily_Work_Sheet_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        with open(fp, "w", encoding="utf-8") as f:
            f.write(doc)
        webbrowser.open(Path(fp).as_uri())
    except Exception as e:
        messagebox.showerror("Print Error", f"Failed to prepare the print sheet: {e}")


ds_frame = tk.Frame(tab_daily_sheet, bg="white", padx=5, pady=5)
ds_frame.pack(fill="both", expand=True)

ds_bar = tk.Frame(ds_frame, bg="white", pady=3)
ds_bar.pack(fill="x")
tk.Label(ds_bar, text="Date:", font=("Arial", 9, "bold"), bg="white").pack(side="left")
ds_date_entry = tk.Entry(ds_bar, textvariable=ds_date_var, width=13, font=("Arial", 9))
ds_date_entry.pack(side="left", padx=(3, 3))
tk.Button(ds_bar, text="Today", bg="#718096", fg="white", font=("Arial", 8, "bold"),
          command=lambda: (ds_date_var.set(datetime.now().strftime("%d-%b-%Y")), load_daily_sheet())).pack(side="left", padx=2)
tk.Label(ds_bar, text="Factory:", font=("Arial", 9, "bold"), bg="white").pack(side="left", padx=(12, 3))
ds_factory_combo = ttk.Combobox(ds_bar, textvariable=ds_factory_var, values=DS_FACTORIES, width=20, state="readonly", font=("Arial", 9))
ds_factory_combo.pack(side="left")
ds_factory_combo.bind("<<ComboboxSelected>>", lambda e: load_daily_sheet())
tk.Checkbutton(ds_bar, text="Include zero-stock items", variable=ds_show_all_var, bg="white", font=("Arial", 8, "bold"),
               command=lambda: load_daily_sheet()).pack(side="left", padx=(12, 3))
tk.Checkbutton(ds_bar, text="Auto-fill Daily Issue/Received", variable=ds_autofill_var, bg="white", font=("Arial", 8, "bold"),
               command=lambda: load_daily_sheet()).pack(side="left", padx=(6, 3))
tk.Button(ds_bar, text="🖨️ Print (A4)", bg="#1b3b6f", fg="white", font=("Arial", 9, "bold"), command=lambda: print_daily_sheet()).pack(side="right", padx=3)
tk.Button(ds_bar, text="🔄 Load Sheet", bg="#2e7d32", fg="white", font=("Arial", 9, "bold"), command=lambda: load_daily_sheet()).pack(side="right", padx=3)
tk.Button(ds_bar, text="✏️ Edit UOM", bg="#ef6c00", fg="white", font=("Arial", 9, "bold"), command=lambda: edit_ds_uom()).pack(side="right", padx=3)
ds_date_entry.bind("<Return>", lambda e: load_daily_sheet())

lbl_ds_title = tk.Label(ds_frame, text="Daily Issue Status For Month", font=("Arial", 13, "bold"), bg="white", fg="#1b3b6f")
lbl_ds_title.pack(pady=(4, 0))
lbl_ds_meta = tk.Label(ds_frame, text="", font=("Arial", 10, "bold"), bg="white", fg="#333")
lbl_ds_meta.pack(pady=(0, 4))

lbl_ds_summary = tk.Label(ds_frame, text="", font=("Arial", 8, "bold"), bg="white", fg="#1b3b6f", anchor="w")
lbl_ds_summary.pack(side="bottom", fill="x", pady=(3, 0))

columns_ds = ("SL No.", "Item Name", "Size", "Unit Name", "Current Stock", "Daily Issue", "Daily Received", "Short Qty", "Excess Qty")
tree_ds = ttk.Treeview(ds_frame, columns=columns_ds, show="headings", height=16)
for col, w in zip(columns_ds, [60, 300, 80, 80, 100, 100, 110, 90, 90]):
    tree_ds.heading(col, text=col)
    tree_ds.column(col, width=w, anchor="w" if col == "Item Name" else ("center" if col in ("SL No.", "Unit Name", "Size") else "e"), stretch=True)
tree_ds.tag_configure("short", background="#fde8e8")
tree_ds.tag_configure("excess", background="#fff3e0")
tree_ds.tag_configure("blank", background="#fafafa")
tree_ds.pack(fill="both", expand=True, side="left", pady=(2, 0))
ds_sc = ttk.Scrollbar(ds_frame, orient="vertical", command=tree_ds.yview)
ds_sc.pack(side="right", fill="y", pady=(2, 0))
tree_ds.configure(yscrollcommand=ds_sc.set)
tree_ds.bind("<Double-1>", ds_load_to_issue)


# ================= REFRESH ALL DATA =================
def refresh_data():
    fac = selected_factory.get()
    lbl_active_display.config(text=f"Active View: {fac}")
    inv_term = inv_search_var.get().strip().lower()
    aud_term = audit_search_var.get().strip().lower()

    trees_to_clear = [
        tree_recent, tree_alert, tree_inv, tree_pending, tree_queue,
        tree_audit_all, tree_audit_short, tree_audit_excess, tree_audit_matched,
        tree_audit_pending, tree_audit_closed, tree_audit_plan,
        tree_il, tree_tf, tree_req, tree_repair, tree_monthly_report, tree_forecast, tree_cat_budget
    ]
    for tree in trees_to_clear:
        for item in tree.get_children():
            tree.delete(item)

    # 1. Transactions
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT id, factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, notes, date, time, verification_status FROM transactions ORDER BY id DESC")
    else:
        cursor.execute("SELECT id, factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, notes, date, time, verification_status FROM transactions WHERE factory_name=%s ORDER BY id DESC", (fac,))
    for row in cursor.fetchall():
        dt_str = f"{row[9]} {row[10]}"
        verif = row[11] if row[11] else "N/A"
        tree_recent.insert("", "end", values=(row[0], row[1], row[2], row[3], row[4], row[5], row[6], _tlabel(row[7]), verif, row[8], dt_str))

    # 2. Low / negative stock alerts
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), current_stock FROM inventory WHERE current_stock <= 5 ORDER BY current_stock ASC")
    else:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), current_stock FROM inventory WHERE factory_name=%s AND current_stock <= 5 ORDER BY current_stock ASC", (fac,))
    for row in cursor.fetchall():
        f_name, sl, p_id, name, size, stk = row
        status = "🔴 NEGATIVE STOCK (URGENT)" if stk < 0 else "⚠️ LOW STOCK (<= 5 pcs)"
        tree_alert.insert("", "end", values=(f_name, sl, p_id, name, size, stk, status))

    # 3. Inventory master & summary
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, erp_status FROM inventory")
    else:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, erp_status FROM inventory WHERE factory_name=%s", (fac,))

    total_inv_items = total_erp_val = total_phys_val = total_var_val = 0.0
    no_size_count = 0
    zero_stock_count = shown_inv_count = 0
    stock_filter = inv_stock_filter_var.get()
    for row in cursor.fetchall():
        f_name, sl, p_id, name, size, dept, cat, erp_stk, phys_stk, price, erp_stat = row
        erp_stk = erp_stk or 0.0
        phys_stk = phys_stk or 0.0
        price = price if price else 0.0
        var_qty = phys_stk - erp_stk
        var_val = var_qty * price
        total_inv_items += 1
        total_erp_val += erp_stk * price
        total_phys_val += phys_stk * price
        total_var_val += var_val
        if not (size or "").strip():
            no_size_count += 1
        if phys_stk <= 0:
            zero_stock_count += 1
        if stock_filter == INV_STOCK_FILTERS[1]:
            stock_ok = phys_stk <= 0
        elif stock_filter == INV_STOCK_FILTERS[2]:
            stock_ok = phys_stk > 0
        elif stock_filter == INV_STOCK_FILTERS[3]:
            stock_ok = not (size or "").strip()
        else:
            stock_ok = True                      # ALL items are listed, zero balance included
        if stock_ok and _inv_match(inv_term, f_name, p_id, name, size, dept, cat):
            shown_inv_count += 1
            tree_inv.insert("", "end", values=(f_name, sl, p_id, name, size, dept, cat, f"{erp_stk:,.1f}", f"{phys_stk:,.1f}", f"{var_qty:,.1f}",
                                               f"{price:,.2f} BDT", f"{erp_stk * price:,.2f} BDT", f"{phys_stk * price:,.2f} BDT", f"{var_val:,.2f} BDT", erp_stat))
        if erp_stat == "ERP Pending" and _inv_match(inv_term, f_name, p_id, name, size, dept, cat):
            tree_pending.insert("", "end", values=(f_name, sl, p_id, name, size, dept, cat, f"{erp_stk:,.1f}", f"{phys_stk:,.1f}", f"{price:,.2f} BDT", erp_stat))

    lbl_inv_summary.config(text=f"Total Items: {int(total_inv_items)} | ERP Value: {total_erp_val:,.2f} BDT | Physical Value: {total_phys_val:,.2f} BDT | Variance Value: {total_var_val:,.2f} BDT"
                                f" | ⚠ Items without Size: {no_size_count} | Zero / No Stock Items: {zero_stock_count} | Showing: {shown_inv_count}")

    # Unmatch / Import Queue (pending + approved history)
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT id, factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, status FROM import_queue ORDER BY id DESC")
    else:
        cursor.execute("SELECT id, factory_name, sl_no, prod_id, item_name, COALESCE(size,''), department, category, erp_stock, current_stock, unit_price, status FROM import_queue WHERE factory_name=%s ORDER BY id DESC", (fac,))
    pending_q = 0
    for q_row in cursor.fetchall():
        is_appr = q_row[11] == "Approved"
        if not is_appr:
            pending_q += 1
        if _inv_match(inv_term, q_row[1], q_row[3], q_row[4], q_row[5], q_row[6], q_row[7]):
            tags = ("approved",) if is_appr else (("nosize",) if not (q_row[5] or "").strip() else ())
            tree_queue.insert("", "end", values=q_row, tags=tags)

    # 4. Budget
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, department_name, category_name, allocated_budget FROM category_budgets")
    else:
        cursor.execute("SELECT factory_name, department_name, category_name, allocated_budget FROM category_budgets WHERE factory_name=%s", (fac,))

    total_allocated_budget = 0.0
    total_actual_consumption = 0.0
    for b_row in cursor.fetchall():
        f_name, dept_name, cat_name, alloc_b = b_row
        total_allocated_budget += alloc_b
        cursor.execute("""
            SELECT SUM(t.qty * i.unit_price)
            FROM transactions t
            JOIN inventory i ON t.sl_no = i.sl_no AND t.factory_name = i.factory_name
            WHERE t.factory_name = %s AND i.category = %s AND t.trans_type ILIKE '%%Issue%%'
        """, (f_name, cat_name))
        res_cost = cursor.fetchone()
        actual_c = res_cost[0] if res_cost and res_cost[0] is not None else 0.0
        total_actual_consumption += actual_c
        rem_b = alloc_b - actual_c
        b_status = "SAFE" if rem_b >= 0 else "OVER BUDGET"
        tree_cat_budget.insert("", "end", values=(f_name, dept_name, cat_name, f"{alloc_b:,.2f} BDT", f"{actual_c:,.2f} BDT", f"{rem_b:,.2f} BDT", b_status))

    util_pct = (total_actual_consumption / total_allocated_budget * 100) if total_allocated_budget > 0 else 0.0
    rem_tot = total_allocated_budget - total_actual_consumption
    b_stat_str = "SAFE" if rem_tot >= 0 else "EXCEEDED"
    lbl_budget_val.config(text=f"Total Budget: {total_allocated_budget:,.2f} BDT  |  Consumption Cost: {total_actual_consumption:,.2f} BDT  |  Remaining: {rem_tot:,.2f} BDT  |  Utilization: {util_pct:.1f}%  |  Status: {b_stat_str}")

    # 5. ERP audit dashboard
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, unit_price, erp_status, COALESCE(size,'') FROM inventory")
    else:
        cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, unit_price, erp_status, COALESCE(size,'') FROM inventory WHERE factory_name=%s", (fac,))

    total_mismatched = short_items_count = excess_items_count = 0
    total_short_val = total_excess_val = 0.0
    for row in cursor.fetchall():
        f_name, sl, p_id, name, erp_stk, curr_stk, price, erp_stat, size = row
        erp_stk = erp_stk or 0.0
        curr_stk = curr_stk or 0.0
        price = price if price else 0.0
        variance = curr_stk - erp_stk
        var_val = variance * price
        short_val = abs(var_val) if variance < 0 else 0.0
        exc_val = var_val if variance > 0 else 0.0
        show = _inv_match(aud_term, f_name, p_id, name, size)
        if variance < 0:
            v_type = "Shortage"
            total_mismatched += 1
            short_items_count += 1
            total_short_val += short_val
            if show:
                tree_audit_short.insert("", "end", values=(f_name, sl, p_id, name, erp_stk, curr_stk, variance, f"{price:,.2f} BDT", f"{short_val:,.2f} BDT", f"{exc_val:,.2f} BDT", erp_stat, v_type))
        elif variance > 0:
            v_type = "Excess"
            total_mismatched += 1
            excess_items_count += 1
            total_excess_val += exc_val
            if show:
                tree_audit_excess.insert("", "end", values=(f_name, sl, p_id, name, erp_stk, curr_stk, variance, f"{price:,.2f} BDT", f"{short_val:,.2f} BDT", f"{exc_val:,.2f} BDT", erp_stat, v_type))
        else:
            v_type = "Matched"
            if show:
                tree_audit_matched.insert("", "end", values=(f_name, sl, p_id, name, erp_stk, curr_stk, variance, f"{price:,.2f} BDT", f"{short_val:,.2f} BDT", f"{exc_val:,.2f} BDT", erp_stat, v_type))

        if show and erp_stat == "ERP Pending":
            tree_audit_pending.insert("", "end", values=(f_name, sl, p_id, name, erp_stk, curr_stk, variance, f"{price:,.2f} BDT", f"{short_val:,.2f} BDT", f"{exc_val:,.2f} BDT", erp_stat, v_type))
        if show:
            tree_audit_all.insert("", "end", values=(f_name, sl, p_id, name, erp_stk, curr_stk, variance, f"{price:,.2f} BDT", f"{short_val:,.2f} BDT", f"{exc_val:,.2f} BDT", erp_stat, v_type))

    # Correction plan (open / closed tasks)
    if "CONSOLIDATED" in fac:
        cursor.execute("SELECT id, factory_name, prod_id, item_name, variance_type, variance_qty, variance_value, assigned_officer, target_date, status, priority, root_cause FROM audit_correction_tasks")
    else:
        cursor.execute("SELECT id, factory_name, prod_id, item_name, variance_type, variance_qty, variance_value, assigned_officer, target_date, status, priority, root_cause FROM audit_correction_tasks WHERE factory_name=%s", (fac,))

    open_tasks_count = 0
    for t_row in cursor.fetchall():
        t_id, f_name, p_id, name, v_type, v_qty, v_val, officer, target, status, prio, rem = t_row
        if status != "Closed":
            open_tasks_count += 1
            tree_audit_plan.insert("", "end", values=(t_id, f_name, p_id, name, v_type, v_qty, f"{(v_val or 0):,.2f} BDT", officer, target, status, prio, rem))
        else:
            tree_audit_closed.insert("", "end", values=(t_id, f_name, p_id, name, v_type, v_qty, f"{(v_val or 0):,.2f} BDT", officer, target, status, prio, rem))

    lbl_audit_main_summary.config(text=f"Total Mismatched: {total_mismatched} | Short Items: {short_items_count} | Excess Items: {excess_items_count} | Short Value: {total_short_val:,.2f} BDT | Excess Value: {total_excess_val:,.2f} BDT | Open Tasks: {open_tasks_count} | Unmatch Pending: {pending_q}")

    # Other tabs
    load_requisitions()
    load_repair_returns()
    load_monthly_report()
    load_issue_ledger()
    load_transfer_history()
    load_erp_aging()
    load_plan_fields()
    load_forecast()
    load_daily_sheet(silent=True)


# ================= START APPLICATION =================
refresh_data()
if DUP_WARNING:
    messagebox.showwarning("Duplicate Items Found", DUP_WARNING)
root.mainloop()
