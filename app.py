from datetime import datetime
import calendar
import difflib
import hashlib
import math
import os
import re
import pandas as pd
import streamlit as st
import psycopg2

# Page Config
st.set_page_config(page_title="KC & Windy Smart Stock Tracker", layout="wide")

# Database Connection using Streamlit Secrets or Fallback
DB_URL = st.secrets.get("WINDY_DB_URL") or os.environ.get("WINDY_DB_URL") or "postgresql://postgres:FQauoo9dk4Rsc2Vi@db.lersqtzjxfuzslnhtpjg.supabase.co:5432/postgres"

@st.cache_resource
def init_connection():
    try:
        conn = psycopg2.connect(DB_URL, connect_timeout=10)
        conn.autocommit = True
        return conn
    except Exception as e:
        st.error(f"Cloud Database connection error: {e}")
        st.info("Please check if your Supabase DB URL in Streamlit Secrets is correct.")
        return None

conn = init_connection()

if conn:
    cursor = conn.cursor()
    
    # Table creation checks
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
            erp_status TEXT DEFAULT 'ERP Pending',
            unit_name TEXT DEFAULT 'Pcs',
            size TEXT DEFAULT ''
        )
    """)
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
            verification_status TEXT DEFAULT 'N/A',
            erp_grn_status TEXT DEFAULT 'Not Required',
            erp_grn_date TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            full_name TEXT
        )
    """)
    
    # Default Users Setup
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        def hash_password(password):
            salt = os.urandom(32)
            pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
            return salt.hex() + ":" + pwd_hash.hex()
        
        default_users = [
            ("Officer_Sagor", hash_password("sagor123"), "Store Officer", "Md. Sagor Ali"),
            ("Store_Manager", hash_password("windy123"), "Store Manager", "Manager Admin"),
            ("Auditor_User", hash_password("audit2026"), "Auditor", "External Auditor")
        ]
        cursor.executemany("INSERT INTO users (username, password, role, full_name) VALUES (%s, %s, %s, %s) ON CONFLICT (username) DO NOTHING", default_users)

st.title("KC & Windy Smart Stock Tracker & Budget Control")
st.markdown("Designed & Created By: **MD. Sagor Ali**")

# Session State for Authentication
if "authenticated_user" not in st.session_state:
    st.session_state["authenticated_user"] = "Officer_Sagor"
    st.session_state["user_role"] = "Store Officer"

# Sidebar Authentication & Navigation
st.sidebar.title("🔐 Access & Navigation")
selected_factory = st.sidebar.selectbox("Select Active Factory", ["KC Washing Plant", "Windy Washing LTD", "🌟 CONSOLIDATED (Both Factories)"])

menu = st.sidebar.radio("Select Module", ["Transactions", "Inventory Master", "ERP Audit", "Issue Ledger", "Requisition Tracking"])

# Basic Password Verification Helper
def verify_password(stored_password, provided_password):
    try:
        if ":" not in stored_password:
            return stored_password == provided_password
        salt_hex, pwd_hash_hex = stored_password.split(":")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, 100000)
        return pwd_hash.hex() == pwd_hash_hex
    except Exception:
        return False

# Login Sidebar Section
with st.sidebar.expander("🔑 Login / Account"):
    u_input = st.text_input("Username")
    p_input = st.text_input("Password", type="password")
    if st.button("Login"):
        if conn:
            cursor.execute("SELECT password, role FROM users WHERE username=%s", (u_input,))
            res = cursor.fetchone()
            if res and verify_password(res[0], p_input):
                st.session_state["authenticated_user"] = u_input
                st.session_state["user_role"] = res[1]
                st.success(f"Welcome {u_input} ({res[1]})!")
            else:
                st.error("Invalid Username or Password!")

st.sidebar.info(f"Logged In: **{st.session_state['authenticated_user']}** [{st.session_state['user_role']}]")

if not conn:
    st.warning("Please configure your correct Supabase DB_URL in Streamlit Secrets to load the application modules.")
else:
    # ----------------- MODULE 1: TRANSACTIONS -----------------
    if menu == "Transactions":
        st.header("📥 Transactions & Stock Entry")
        
        if selected_factory == "🌟 CONSOLIDATED (Both Factories)":
            st.warning("Please select a specific factory to record transactions.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                cursor.execute("SELECT sl_no, prod_id, item_name, current_stock FROM inventory WHERE factory_name=%s ORDER BY sl_no", (selected_factory,))
                inv_rows = cursor.fetchall()
                item_dict = {f"SL {r[0]} | {r[1]} | {r[2]} (Stock: {r[3]})": r[0] for r in inv_rows}
                
                selected_item_label = st.selectbox("Select Product", options=list(item_dict.keys()) if item_dict else ["No items found"])
                qty = st.number_input("Quantity (QTY)", min_value=0.1, value=1.0)
                trans_type = st.selectbox("Transaction Type", ["Supplier. Rec", "Issued", "Stock Adjustment (+)", "Stock Adjustment (-)"])
                notes = st.text_area("Activity Notes / Remarks")
                
                if st.button("Save & Update Stock"):
                    if item_dict and selected_item_label in item_dict:
                        sl_no = item_dict[selected_item_label]
                        cursor.execute("SELECT prod_id, item_name, current_stock FROM inventory WHERE sl_no=%s AND factory_name=%s", (sl_no, selected_factory))
                        p_id, p_name, p_stock = cursor.fetchone()
                        
                        now_date = datetime.now().strftime("%d-%b-%Y")
                        now_time = datetime.now().strftime("%I:%M %p")
                        
                        if trans_type in ["Supplier. Rec", "Stock Adjustment (+)"]:
                            cursor.execute("UPDATE inventory SET current_stock = current_stock + %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, selected_factory))
                        else:
                            if qty > p_stock:
                                st.error(f"Stock Shortage! Available stock is only {p_stock}.")
                                st.stop()
                            cursor.execute("UPDATE inventory SET current_stock = current_stock - %s WHERE sl_no=%s AND factory_name=%s", (qty, sl_no, selected_factory))
                        
                        cursor.execute("""
                            INSERT INTO transactions (factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, day, notes, date, time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (selected_factory, st.session_state["authenticated_user"], sl_no, p_id, p_name, qty, trans_type, datetime.now().day, notes, now_date, now_time))
                        
                        conn.commit()
                        st.success("Transaction recorded successfully and stock updated!")
                        st.rerun()

            with col2:
                st.subheader("Recent Transactions")
                cursor.execute("SELECT id, factory_name, officer_name, item_name, qty, trans_type, date FROM transactions ORDER BY id DESC LIMIT 10")
                trans_data = cursor.fetchall()
                if trans_data:
                    df_trans = pd.DataFrame(trans_data, columns=["ID", "Factory", "Officer", "Item Name", "Qty", "Type", "Date"])
                    st.dataframe(df_trans, use_container_width=True)
                else:
                    st.info("No transactions found.")

    # ----------------- MODULE 2: INVENTORY MASTER -----------------
    elif menu == "Inventory Master":
        st.header("📋 Master Inventory")
        
        if selected_factory == "🌟 CONSOLIDATED (Both Factories)":
            cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, department, category, erp_stock, current_stock, unit_price FROM inventory")
        else:
            cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, department, category, erp_stock, current_stock, unit_price FROM inventory WHERE factory_name=%s", (selected_factory,))
            
        inv_data = cursor.fetchall()
        if inv_data:
            df_inv = pd.DataFrame(inv_data, columns=["Factory", "SL No", "ERP Code", "Item Name", "Department", "Category", "ERP Stock", "Physical Stock", "Unit Price"])
            st.dataframe(df_inv, use_container_width=True)
        else:
            st.info("No inventory items found.")

    # ----------------- MODULE 3: ERP AUDIT -----------------
    elif menu == "ERP Audit":
        st.header("🔍 ERP vs Physical Audit")
        
        if selected_factory == "🌟 CONSOLIDATED (Both Factories)":
            cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, (current_stock - erp_stock) as variance FROM inventory")
        else:
            cursor.execute("SELECT factory_name, sl_no, prod_id, item_name, erp_stock, current_stock, (current_stock - erp_stock) as variance FROM inventory WHERE factory_name=%s", (selected_factory,))
            
        audit_data = cursor.fetchall()
        if audit_data:
            df_audit = pd.DataFrame(audit_data, columns=["Factory", "SL No", "ERP Code", "Item Name", "ERP Stock", "Physical Stock", "Variance Qty"])
            st.dataframe(df_audit, use_container_width=True)
        else:
            st.info("No audit records found.")

    # ----------------- MODULE 4: ISSUE LEDGER -----------------
    elif menu == "Issue Ledger":
        st.header("📤 Issue Ledger Report")
        cursor.execute("SELECT id, factory_name, officer_name, item_name, qty, date, notes FROM transactions WHERE trans_type ILIKE '%%Issue%%' ORDER BY id DESC")
        issue_data = cursor.fetchall()
        if issue_data:
            df_issue = pd.DataFrame(issue_data, columns=["ID", "Factory", "Officer", "Item Name", "Qty", "Date", "Notes"])
            st.dataframe(df_issue, use_container_width=True)
        else:
            st.info("No issue records found.")

    # ----------------- MODULE 5: REQUISITION TRACKING -----------------
    elif menu == "Requisition Tracking":
        st.header("📦 Requisition Tracking")
        cursor.execute("CREATE TABLE IF NOT EXISTS requisition_tracking (id SERIAL PRIMARY KEY, factory_name TEXT, req_no TEXT, department TEXT, req_date TEXT, item_name TEXT, req_qty REAL, status TEXT)")
        cursor.execute("SELECT factory_name, req_no, department, req_date, item_name, req_qty, status FROM requisition_tracking")
        req_data = cursor.fetchall()
        if req_data:
            df_req = pd.DataFrame(req_data, columns=["Factory", "Req No", "Department", "Req Date", "Item Name", "Req Qty", "Status"])
            st.dataframe(df_req, use_container_width=True)
        else:
            st.info("No requisitions found.")
