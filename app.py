# ============================================================
#  KC & Windy Smart Inventory & Budget Control
#  Warm Orange / Peach SaaS Edition  (v2: top navigation + blue-white entry form)
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
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import psycopg2
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="KC & Windy Smart Inventory", page_icon="📦", layout="wide",
                   initial_sidebar_state="expanded")

# ============================================================
#  THEME (warm orange / peach, Inter, soft cards)
# ============================================================
ORANGE, PEACH, BG, INK = "#FF8C00", "#FFB347", "#F8FAFC", "#1E293B"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html, body, [class*="css"], .stApp, button, input, textarea, select {{ font-family: 'Inter', sans-serif !important; }}
.stApp {{ background: {BG}; color: {INK}; }}
.block-container {{ padding-top: 4.2rem !important; padding-bottom: 2.5rem; max-width: 1480px; }}
header[data-testid="stHeader"] {{ background: rgba(248,250,252,.92) !important; z-index: 90; }}
#MainMenu, footer {{ visibility: hidden; }}

/* ---------- Top header bar ---------- */
.top-bar {{
    background: #ffffff; border: 1px solid #FDE7CF; border-radius: 12px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); padding: 14px 20px; margin-bottom: 14px;
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;
}}
.top-bar .title {{ font-size: 18px; font-weight: 800; color: {INK}; letter-spacing: .2px; }}
.top-bar .sub {{ font-size: 12px; color: #64748B; margin-top: 3px; }}
.chip {{
    display: inline-block; padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 700;
    background: linear-gradient(120deg, {ORANGE}, {PEACH}); color: #fff;
    box-shadow: 0 4px 10px rgba(255,140,0,.30); margin-right: 6px;
}}
.chip-soft {{ background: #FFF4E6; color: #C2410C; box-shadow: none; border: 1px solid #FDE7CF; }}

.section-title {{
    font-size: 12px; font-weight: 800; color: {INK}; text-transform: uppercase; letter-spacing: .8px;
    margin: 6px 0 12px 0; padding-left: 10px; border-left: 4px solid {ORANGE};
}}

/* ---------- Cards / metrics ---------- */
div[data-testid="stMetric"] {{
    background: #ffffff; border: 1px solid #F1F5F9; border-radius: 12px; padding: 16px 18px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); border-top: 4px solid {ORANGE};
}}
div[data-testid="stMetricLabel"] p {{ color: #64748B !important; font-weight: 700; font-size: 11.5px; text-transform: uppercase; letter-spacing: .4px; }}
div[data-testid="stMetricValue"] {{ color: {INK}; font-weight: 800; }}
div[data-testid="stVerticalBlockBorderWrapper"] {{ border-radius: 12px !important; box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); background: #fff; }}

.fin-card {{
    background: #ffffff; border: 1px solid #F1F5F9; border-radius: 12px; padding: 18px 20px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); margin-bottom: 14px;
}}
.fin-card .cat-factory {{ font-size: 10.5px; font-weight: 700; color: {ORANGE}; text-transform: uppercase; letter-spacing: .6px; }}
.fin-card .cat-name {{ font-size: 15px; font-weight: 800; color: {INK}; margin: 4px 0 10px 0; }}
.fin-card .cat-nums {{ display: flex; justify-content: space-between; font-size: 12.5px; color: #334155; font-weight: 600; }}
.fin-card .cat-foot {{ font-size: 12px; color: #64748B; margin-top: 8px; font-weight: 600; }}

.bar-label {{ font-size: 12.5px; color: #334155; font-weight: 700; display: flex; justify-content: space-between; margin-top: 6px; }}
.bar-wrap {{ background: #FFEFD9; border-radius: 999px; height: 14px; overflow: hidden; margin: 6px 0 2px 0; }}
.bar-fill {{ height: 100%; border-radius: 999px; transition: width .6s ease; }}

.status-badge {{ display:inline-block; padding:2px 10px; border-radius:999px; font-size:11px; font-weight:700; }}

/* ---------- Navigation tabs (compact, bordered) ---------- */
.stTabs [data-baseweb="tab-list"], .stTabs [data-baseweb="tab-list"] > div {{ overflow: visible !important; flex-wrap: wrap !important; height: auto !important; }}
.stTabs [data-baseweb="tab-list"] {{ gap: 6px; background: transparent; border-bottom: none; padding: 2px 0 12px 0; }}
.stTabs button[data-testid="stTabScrollButton"] {{ display: none !important; }}
div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] {{ display: none !important; height: 0 !important; }}
.stTabs [data-baseweb="tab"] {{
    background: #ffffff; border: 1.5px solid #E2E8F0; border-radius: 10px; padding: 7px 14px;
    font-weight: 700; font-size: 12.5px; color: #334155; box-shadow: 0 1px 3px rgba(15,23,42,.08);
    white-space: nowrap; height: auto; min-height: 36px; transition: all .15s ease;
}}
.stTabs [data-baseweb="tab"]:hover {{ border-color: {ORANGE}; color: #C2410C; }}
.stTabs [aria-selected="true"] {{
    background: linear-gradient(120deg, #F97316, {ORANGE}) !important; color: #fff !important;
    border-color: #EA580C !important; box-shadow: 0 3px 10px rgba(234,88,12,.30);
}}
.stTabs [aria-selected="true"] p {{ color: #fff !important; }}
/* nested tabs act like compact filter chips */
.stTabs .stTabs [data-baseweb="tab"] {{ border-radius: 8px; padding: 5px 12px; font-size: 12px; min-height: 32px; background: #F8FAFC; }}
.stTabs .stTabs [aria-selected="true"] {{
    background: #1E293B !important; border-color: #1E293B !important; box-shadow: 0 2px 6px rgba(30,41,59,.25);
}}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {{ display: none !important; }}

/* ---------- Inputs ---------- */
div[data-baseweb="input"], div[data-baseweb="base-input"], div[data-baseweb="textarea"] {{
    background: #ffffff !important; border: 1.5px solid #E2E8F0 !important; border-radius: 12px !important;
    transition: border-color .2s ease, box-shadow .2s ease;
}}
div[data-baseweb="input"]:focus-within, div[data-baseweb="textarea"]:focus-within {{
    border-color: {ORANGE} !important; box-shadow: 0 0 0 3px rgba(255,140,0,.20) !important;
}}
div[data-baseweb="input"] input, div[data-baseweb="textarea"] textarea {{
    color: {INK} !important; padding: 9px 12px !important; font-size: 14px !important;
}}
div[data-baseweb="select"] > div {{
    border-radius: 12px !important; border: 1.5px solid #E2E8F0 !important; background: #fff !important; min-height: 42px;
}}
div[data-baseweb="select"] span, div[data-baseweb="select"] div {{ color: {INK}; }}

/* ---------- Buttons ---------- */
.stButton > button, .stDownloadButton > button {{
    border-radius: 12px; font-weight: 700; border: 1.5px solid #E2E8F0; padding: 8px 18px;
    transition: all .18s ease; color: {INK}; background: #fff;
}}
.stButton > button:hover, .stDownloadButton > button:hover {{ border-color: {ORANGE}; color: #C2410C; transform: translateY(-1px); }}
.stButton > button[kind="primary"] {{
    background: linear-gradient(120deg, #F97316, {ORANGE}); border: none; color: #fff;
    box-shadow: 0 4px 12px rgba(234,88,12,.28); padding: 9px 16px; font-size: 14px; letter-spacing: .2px;
}}
.stButton > button[kind="primary"]:hover {{ color: #fff; box-shadow: 0 6px 16px rgba(234,88,12,.40); transform: translateY(-1px); }}
.stButton > button:disabled {{ opacity: .5; }}

/* ---------- Tables / alerts / expanders ---------- */
div[data-testid="stDataFrame"] {{
    border: 1.5px solid #CBD5E1; border-radius: 12px; overflow: hidden;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); background: #fff;
}}
div[data-testid="stAlert"] {{ border-radius: 12px; }}
div[data-testid="stExpander"] {{ border: 1px solid #FDE7CF !important; border-radius: 12px !important; background: #fff; box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); }}
div[data-testid="stForm"] {{ border: 1px solid #F1F5F9; border-radius: 12px; background: #fff; padding: 14px; }}

/* ---------- Sidebar: warm gradient ---------- */
section[data-testid="stSidebar"] {{ background: linear-gradient(180deg, #E8590C 0%, {ORANGE} 55%, {PEACH} 100%); }}
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] h3,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] small {{ color: #FFFFFF !important; }}
section[data-testid="stSidebar"] div[data-testid="stForm"] {{
    background: rgba(255,255,255,.14); border: 1px solid rgba(255,255,255,.35); border-radius: 12px; padding: 16px;
    box-shadow: 0 8px 20px rgba(124,45,18,.18);
}}
section[data-testid="stSidebar"] div[data-testid="stForm"] button,
section[data-testid="stSidebar"] .stButton > button {{
    background: #ffffff; color: #C2410C; border: none; width: 100%; font-weight: 800;
    box-shadow: 0 4px 12px rgba(124,45,18,.25);
}}
section[data-testid="stSidebar"] div[data-testid="stForm"] button:hover,
section[data-testid="stSidebar"] .stButton > button:hover {{ background: #FFF7ED; color: #9A3412; }}
section[data-testid="stSidebar"] div[data-baseweb="input"] {{ background: #ffffff !important; border: 1.5px solid #FFFFFF !important; }}
section[data-testid="stSidebar"] div[data-baseweb="input"] input,
section[data-testid="stSidebar"] div[data-baseweb="select"] div {{ color: {INK} !important; }}
section[data-testid="stSidebar"] div[data-baseweb="input"] input::placeholder {{ color: #9CA3AF !important; }}
section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{ background: #fff !important; border: none !important; }}
.nav-item {{
    background: rgba(255,255,255,.16); border-radius: 10px; padding: 8px 12px; margin: 5px 0;
    font-size: 13px; font-weight: 600; color: #fff !important;
}}

/* ---------- Sidebar login: crystal-clear labels ---------- */
section[data-testid="stSidebar"] label p,
section[data-testid="stSidebar"] div[data-testid="stWidgetLabel"] p {{
    color: #FFFFFF !important; font-weight: 700 !important; font-size: 13px !important; letter-spacing: .2px;
}}
section[data-testid="stSidebar"] div[data-baseweb="input"] input {{
    padding: 10px 12px !important; font-size: 14px !important; color: {INK} !important;
    -webkit-text-fill-color: {INK} !important; background: #fff !important;
}}
section[data-testid="stSidebar"] .stButton > button,
section[data-testid="stSidebar"] div[data-testid="stForm"] button {{
    padding: 10px 14px !important; font-size: 14px !important; min-height: 42px;
}}
section[data-testid="stSidebar"] .stButton > button p,
section[data-testid="stSidebar"] div[data-testid="stForm"] button p {{ color: #C2410C !important; font-weight: 800 !important; }}
.user-card {{
    background: #ffffff; border-radius: 12px; padding: 12px 14px; margin: 6px 0 10px 0;
    box-shadow: 0 6px 16px rgba(124,45,18,.22);
}}
.user-card .u-lbl {{ font-size: 10.5px; font-weight: 800; color: #94A3B8 !important; text-transform: uppercase; letter-spacing: .6px; }}
.user-card .u-name {{ font-size: 15px; font-weight: 800; color: #1E293B !important; margin-bottom: 6px; }}
.user-card .u-role {{
    display: inline-block; font-size: 11.5px; font-weight: 800; color: #C2410C !important;
    background: #FFF4E6; border: 1px solid #FDE7CF; border-radius: 999px; padding: 3px 12px;
}}
.brand-card {{
    background: rgba(255,255,255,.18); border: 1px solid rgba(255,255,255,.35); border-radius: 12px;
    padding: 10px 14px; margin-bottom: 10px;
}}
.brand-card .b-t {{ font-size: 14px; font-weight: 800; color: #fff !important; line-height: 1.3; }}
.brand-card .b-s {{ font-size: 11px; color: #FFF7ED !important; margin-top: 2px; }}

/* ---------- Slim strip shown at the top of each tab ---------- */
.strip {{
    display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;
    background: #fff; border: 1px solid #FDE7CF; border-radius: 12px; padding: 8px 14px; margin-bottom: 12px;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,.05); font-size: 12.5px; color: #475569; font-weight: 600;
}}
.strip b {{ color: {INK}; }}

/* ---------- NEW TRANSACTION: compact blue-white entry card ---------- */
.st-key-tx_form_box {{
    background: linear-gradient(180deg, #FFFFFF 0%, #EFF6FF 100%) !important;
    border: 1.5px solid #BFDBFE !important; border-radius: 14px !important;
    box-shadow: 0 8px 22px rgba(37,99,235,.12) !important; padding: 10px 14px 12px 14px !important;
}}
.st-key-tx_form_box div[data-testid="stVerticalBlock"] {{ gap: .4rem !important; }}
.st-key-tx_form_box .section-title {{ border-left-color: #2563EB; color: #1E3A8A; margin: 0 0 4px 0; }}
.st-key-tx_form_box label p, .st-key-tx_form_box div[data-testid="stWidgetLabel"] p {{
    color: #1E3A8A !important; font-weight: 700 !important; font-size: 12px !important; margin-bottom: 0 !important;
}}
.st-key-tx_form_box div[data-testid="stWidgetLabel"] {{ min-height: 0 !important; margin-bottom: -2px; }}
.st-key-tx_form_box div[data-baseweb="input"], .st-key-tx_form_box div[data-baseweb="base-input"] {{
    background: #ffffff !important; border: 1.5px solid #BFDBFE !important; border-radius: 10px !important;
}}
.st-key-tx_form_box div[data-baseweb="input"]:focus-within {{
    border-color: #2563EB !important; box-shadow: 0 0 0 3px rgba(37,99,235,.18) !important;
}}
.st-key-tx_form_box div[data-baseweb="input"] input {{ padding: 6px 10px !important; font-size: 13.5px !important; }}
.st-key-tx_form_box div[data-baseweb="select"] > div {{ border: 1.5px solid #BFDBFE !important; min-height: 36px !important; border-radius: 10px !important; }}
.st-key-tx_form_box div[data-testid="stNumberInput"] button {{ background: #EFF6FF; }}
.st-key-tx_form_box div[data-testid="stAlert"] {{ padding: 6px 10px !important; font-size: 12.5px; }}
.st-key-tx_form_box .stCheckbox label p {{ font-size: 12px !important; }}
.st-key-tx_form_box .stButton > button[kind="primary"] {{
    background: linear-gradient(120deg, #2563EB, #38BDF8) !important; border: none; color: #fff !important;
    box-shadow: 0 6px 16px rgba(37,99,235,.35) !important; padding: 8px 16px !important; font-size: 14px !important;
}}
.st-key-tx_form_box .stButton > button[kind="primary"] p {{ color: #fff !important; }}
.st-key-tx_form_box .stButton > button[kind="primary"]:hover {{ box-shadow: 0 8px 22px rgba(37,99,235,.5) !important; }}
.officer-pill {{
    display: inline-block; background: #DBEAFE; color: #1E40AF; border: 1px solid #BFDBFE; border-radius: 999px;
    padding: 3px 12px; font-size: 12px; font-weight: 700;
}}

/* ---------- v3 polish ---------- */
div[data-testid="stMetricValue"] > div {{
    font-size: 1.65rem !important; white-space: normal !important; overflow: visible !important;
    text-overflow: clip !important; line-height: 1.2;
}}
div[data-testid="stWidgetLabel"] p {{ font-weight: 700; color: #334155; font-size: 13px; }}
.stButton > button, .stDownloadButton > button {{ min-height: 38px; }}
div[data-testid="stCheckbox"] label p {{ font-weight: 600; }}
section[data-testid="stSidebar"] div[data-testid="stExpander"] {{
    background: rgba(255,255,255,.14) !important; border: 1px solid rgba(255,255,255,.35) !important;
    box-shadow: none !important; margin-top: 8px;
}}
section[data-testid="stSidebar"] div[data-testid="stExpander"] summary p {{ font-weight: 800 !important; color: #fff !important; }}
section[data-testid="stSidebar"] div[data-testid="stExpander"] div[data-testid="stForm"] {{
    border: none !important; padding: 4px !important; background: transparent !important; box-shadow: none !important;
}}
section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] * {{ color: #FFF7ED !important; }}

/* ---------- Module navigation: radio styled exactly like the compact tabs (only the open module is rendered = fast) ---------- */
.st-key-main_nav div[role="radiogroup"], .st-key-aud_view div[role="radiogroup"] {{ gap: 6px; flex-wrap: wrap; padding: 2px 0 12px 0; }}
.st-key-main_nav label[data-baseweb="radio"], .st-key-aud_view label[data-baseweb="radio"] {{
    background: #ffffff; border: 1.5px solid #E2E8F0; border-radius: 10px; padding: 7px 14px; margin: 0;
    box-shadow: 0 1px 3px rgba(15,23,42,.08); cursor: pointer; min-height: 36px; align-items: center; transition: all .15s ease;
}}
.st-key-main_nav label[data-baseweb="radio"] > div:not(:has(p)), .st-key-aud_view label[data-baseweb="radio"] > div:not(:has(p)),
.st-key-main_nav label[data-baseweb="radio"] > span, .st-key-aud_view label[data-baseweb="radio"] > span {{ display: none !important; }}
.st-key-main_nav label[data-baseweb="radio"] p, .st-key-aud_view label[data-baseweb="radio"] p {{
    font-weight: 700; font-size: 12.5px; color: #334155; white-space: nowrap; margin: 0;
}}
.st-key-main_nav label[data-baseweb="radio"]:hover, .st-key-aud_view label[data-baseweb="radio"]:hover {{ border-color: {ORANGE}; }}
.st-key-main_nav label[data-baseweb="radio"]:has(input:checked) {{
    background: linear-gradient(120deg, #F97316, {ORANGE}); border-color: #EA580C; box-shadow: 0 3px 10px rgba(234,88,12,.30);
}}
.st-key-main_nav label[data-baseweb="radio"]:has(input:checked) p {{ color: #fff !important; }}
.st-key-aud_view label[data-baseweb="radio"] {{ border-radius: 8px; padding: 5px 12px; background: #F8FAFC; min-height: 32px; }}
.st-key-aud_view label[data-baseweb="radio"] p {{ font-size: 12px; }}
.st-key-aud_view label[data-baseweb="radio"]:has(input:checked) {{
    background: #1E293B; border-color: #1E293B; box-shadow: 0 2px 6px rgba(30,41,59,.25);
}}
.st-key-aud_view label[data-baseweb="radio"]:has(input:checked) p {{ color: #fff !important; }}

/* ---------- ERP PO Pending summary card (clickable) ---------- */
.st-key-po_card_btn button {{
    height: auto; min-height: 96px; text-align: left; justify-content: flex-start; padding: 12px 18px;
    background: linear-gradient(135deg, #FFF7ED 0%, #FFE8CC 100%); border: 1.5px solid #FDBA74; border-left: 6px solid {ORANGE};
    border-radius: 14px; box-shadow: 0 6px 16px rgba(234,88,12,.18);
}}
.st-key-po_card_btn button:hover {{ border-color: #EA580C; transform: translateY(-2px); box-shadow: 0 10px 22px rgba(234,88,12,.28); }}
.st-key-po_card_btn button p {{ white-space: pre-line; text-align: left; margin: 0; font-size: 28px; font-weight: 800; color: #9A3412; line-height: 1.15; }}
.st-key-po_card_btn button p:first-child::first-line {{
    font-size: 12px; font-weight: 800; color: #C2410C; text-transform: uppercase; letter-spacing: .7px;
}}
</style>""", unsafe_allow_html=True)

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
BUDGET_ALERT_PCT = 85
DEPARTMENTS = ["Maintenance", "Warehouse", "Admin, HR & Compliance", "Lab"]
CATEGORIES = ["Maintenance Spare Parts", "Electrical Accessories", "Utilities Spare Parts", "Stationeries Items",
              "Production Consumable Items", "Safety and Security", "Cleaning Goods", "Furniture Accessories",
              "Medicine & Others", "Plumbing and Sanitary Goods", "Office Maintenance", "Laboratory Accessories",
              "Uncategorized (Edit Later)"]
UOM = ["Pcs", "Kg"]
INV_COLS = ("sl_no, prod_id, factory_name, item_name, COALESCE(size,'') AS size, COALESCE(serial_no,'') AS serial, "
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
# Navigation state keys / ERP Audit view names (used by the clickable "ERP PO Pending" card)
NAV_KEY = "main_nav"
NAV_ERP_AUDIT = "🔍 [3] ERP AUDIT"
AUD_VIEW_KEY = "aud_view"
AUD_ACT, AUD_ALL, AUD_SHORT, AUD_EXC, AUD_MATCH = "⚙️ Actions", "📋 All", "🔴 Short", "🟠 Excess", "🟢 Matched"
AUD_PEND, AUD_PO, AUD_RECV = "🟡 ERP Pending", "📌 ERP PO Pending", "📥 Product Received"
AUD_PLAN, AUD_AGE = "📝 Correction Plan", "⏱ Receipt Aging"
AUD_VIEWS = [AUD_ACT, AUD_ALL, AUD_SHORT, AUD_EXC, AUD_MATCH, AUD_PEND, AUD_PO, AUD_RECV, AUD_PLAN, AUD_AGE]
VERIFY_AFTER_DAYS = 3   # same product issued on 3 consecutive days -> physical verification on the 4th day
MODULE_NAV = [("📝", "Transactions"), ("📦", "Inventory Master"), ("🔍", "ERP Audit"), ("📜", "Issue Ledger"),
              ("🔁", "Transfer History"), ("📑", "Requisition"), ("🛠", "Repair & Returns"), ("📒", "Ledger"),
              ("📈", "Forecast"), ("💵", "Budget"), ("🗓", "Daily Work Sheet")]


# ============================================================
#  DATABASE
# ============================================================
@st.cache_resource(show_spinner=False)
def _connect():
    conn = psycopg2.connect(st.secrets["DB_URL"], connect_timeout=10, keepalives=1, keepalives_idle=30,
                            keepalives_interval=10, keepalives_count=3)
    conn.autocommit = False
    return conn


def get_conn():
    """Returns a live connection; reconnects automatically if the old one was dropped."""
    conn = _connect()
    if conn.closed:
        _connect.clear()
        conn = _connect()
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
        "ALTER TABLE inventory ADD COLUMN IF NOT EXISTS serial_no TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'Active'",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TEXT",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS supplier_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS challan_no TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS erp_product_name TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS erp_code TEXT DEFAULT ''",
        "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS erp_sl_ref TEXT DEFAULT ''",
        """CREATE TABLE IF NOT EXISTS password_resets (
            id SERIAL PRIMARY KEY, username TEXT, requested_at TEXT, status TEXT DEFAULT 'Pending',
            handled_by TEXT, handled_at TEXT)""",
    ]
    try:
        with conn.cursor() as cur:
            for s in ddl:
                cur.execute(s)
            default_users = [
                ("Officer_Sagor", "sagor123", "Store Officer", "Md. Sagor Ali"),
                ("Officer_Rahim", "rahim123", "Store Officer", "Abdul Rahim"),
                ("Store_Manager", "windy123", "Store Manager", "Manager Admin"),
                ("Auditor_User", "audit2026", "Auditor", "External Auditor"),
                ("Executive_Sattar", "sattar123", "Executive", "Mr. Sattar"),
            ]
            for uname, pw, role, full in default_users:   # adds any missing default account
                cur.execute("SELECT 1 FROM users WHERE username=%s", (uname,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO users (username, password, role, full_name) VALUES (%s,%s,%s,%s)",
                                (uname, hash_password(pw), role, full))
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
    try:  # fast serial-number lookup (plain index, no data change)
        with conn.cursor() as cur:
            cur.execute("CREATE INDEX IF NOT EXISTS ix_inventory_serial ON inventory(factory_name, lower(COALESCE(serial_no,'')))")
        conn.commit()
    except Exception:
        conn.rollback()
    try:  # same name + size can not be saved twice in one factory
        with conn.cursor() as cur:
            cur.execute("""CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_name_size
                           ON inventory(factory_name, lower(replace(replace(item_name,' ',''),'.','')), lower(trim(COALESCE(size,''))))""")
        conn.commit()
    except Exception:
        conn.rollback()
    # Speed indexes (plain, additive - no data is touched). Without them every save / table refresh scanned the
    # whole transactions + inventory tables, and the daily sheet ran one full scan per inventory row.
    for ix_sql in (
        "CREATE INDEX IF NOT EXISTS ix_inventory_fac_sl ON inventory(factory_name, sl_no)",
        "CREATE INDEX IF NOT EXISTS ix_inventory_fac_prod ON inventory(factory_name, prod_id)",
        "CREATE INDEX IF NOT EXISTS ix_tx_fac_sl_id ON transactions(factory_name, sl_no, id)",
        "CREATE INDEX IF NOT EXISTS ix_tx_fac_date ON transactions(factory_name, date)",
    ):
        try:
            with conn.cursor() as cur:
                cur.execute(ix_sql)
            conn.commit()
        except Exception:
            conn.rollback()
    return True


def ensure_live_connection():
    """One cheap ping per rerun: a silently dropped cloud connection is replaced at once
    instead of hanging for minutes on a dead socket."""
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
        conn.rollback()
    except Exception:
        try:
            _connect.clear()
        except Exception:
            pass


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
    """Success message survives the rerun, so the screen refreshes cleanly."""
    st.session_state["flash"] = msg
    st.rerun()


def show_flash():
    msg = st.session_state.pop("flash", None)
    if msg:
        try:
            st.toast(msg, icon="✅")
        except Exception:
            st.success(msg)


def mgr_check(key):
    pw = st.text_input("🔐 Store Manager password", type="password", key=key)
    ok = bool(pw) and verify_manager_password(pw)
    if pw and not ok:
        st.caption("❌ Password vul")
    return ok


def confirm_box(key, text="⚠️ Ami confirm korchi - ei record permanently delete hobe."):
    """Explicit tick required before any destructive action."""
    return st.checkbox(text, key=key)


USERNAME_RE = re.compile(r"[A-Za-z0-9_.\-]{3,30}")


@tx
def register_user(username, full_name, pw):
    """New accounts are always 'Store Officer' and stay Pending until the Store Manager approves them."""
    if q("SELECT 1 AS x FROM users WHERE LOWER(username)=LOWER(%s)", (username,)):
        st.error("Ei username already ache. Onno username din.")
        return False
    run("INSERT INTO users (username, password, role, full_name, status, created_at) VALUES (%s,%s,'Store Officer',%s,'Pending',%s)",
        (username, hash_password(pw), full_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    audit("REGISTER_REQUEST", f"Registration request: {username} ({full_name})")
    return True


@tx
def request_password_reset(username):
    """Queues a reset request for the Store Manager. Nothing is revealed about whether the user exists."""
    r = q("SELECT username FROM users WHERE LOWER(username)=LOWER(%s) AND COALESCE(status,'Active')='Active'", (username,))
    if r:
        uname = r[0]["username"]
        if not q("SELECT 1 AS x FROM password_resets WHERE username=%s AND status='Pending'", (uname,)):
            run("INSERT INTO password_resets (username, requested_at, status) VALUES (%s,%s,'Pending')",
                (uname, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            audit("PASSWORD_RESET_REQUEST", f"Reset requested for {uname}")
    return True


@tx
def approve_user(uid, role, uname):
    run("UPDATE users SET status='Active', role=%s WHERE id=%s AND COALESCE(status,'Active')='Pending'", (role, uid))
    audit("APPROVE_USER", f"{uname} approved as {role}")
    return True


@tx
def reject_user(uid, uname):
    run("DELETE FROM users WHERE id=%s AND COALESCE(status,'Active')='Pending'", (uid,))
    audit("REJECT_USER", f"Registration of {uname} rejected")
    return True


@tx
def set_temp_password(rid, uname, new_pw):
    run("UPDATE users SET password=%s WHERE username=%s", (hash_password(new_pw), uname))
    run("UPDATE password_resets SET status='Done', handled_by=%s, handled_at=%s WHERE id=%s",
        (st.session_state.get("user", ""), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), rid))
    audit("PASSWORD_RESET_DONE", f"Temporary password set for {uname}")
    return True


@tx
def change_password(uname, new_pw):
    run("UPDATE users SET password=%s WHERE username=%s", (hash_password(new_pw), uname))
    audit("PASSWORD_CHANGED", f"{uname} changed own password")
    return True


def user_admin_panel():
    """Store Manager only: approve registrations and answer password-reset requests."""
    pend = q("SELECT id, username, full_name FROM users WHERE COALESCE(status,'Active')='Pending' ORDER BY id")
    resets = q("SELECT id, username, requested_at FROM password_resets WHERE status='Pending' ORDER BY id")
    with st.expander(f"👥 User Admin ({len(pend) + len(resets)} pending)"):
        st.markdown("**New registrations**")
        if not pend:
            st.caption("Pending registration nei.")
        else:
            labels = {f"{r['username']} - {r['full_name']}": r for r in pend}
            sel = labels[st.selectbox("Registration request", list(labels), key="ua_reg_sel")]
            role = st.selectbox("Assign role", ["Store Officer", "Auditor"], key="ua_reg_role")
            c1, c2 = st.columns(2)
            if c1.button("✔ Approve", key="ua_reg_ok"):
                if approve_user(sel["id"], role, sel["username"]):
                    done(f"{sel['username']} approved as {role}.")
            if c2.button("✖ Reject", key="ua_reg_no"):
                if reject_user(sel["id"], sel["username"]):
                    done(f"{sel['username']} rejected.")
        st.markdown("**Password reset requests**")
        if not resets:
            st.caption("Pending reset request nei.")
        else:
            labels2 = {f"{r['username']} ({r['requested_at']})": r for r in resets}
            sel2 = labels2[st.selectbox("Reset request", list(labels2), key="ua_rs_sel")]
            np_ = st.text_input("New temporary password (min 8 chars)", type="password", key="ua_rs_pw")
            if st.button("Set temporary password", key="ua_rs_btn"):
                if len(np_) < 8:
                    st.error("Password kom pokkhe 8 character hote hobe.")
                elif set_temp_password(sel2["id"], sel2["username"], np_):
                    done("Temporary password set. User-ke surakkhitovabe janan; login-er por password change korte bolun.")


def sidebar_login():
    with st.sidebar:
        st.markdown(
            '<div class="brand-card"><div class="b-t">📦 KC &amp; Windy Smart Inventory</div>'
            '<div class="b-s">Budget Control · Designed by MD. Sagor Ali</div></div>', unsafe_allow_html=True)
        st.markdown("### 🔐 Secure Login")
        if st.session_state.get("user"):
            st.markdown(
                f'<div class="user-card"><div class="u-lbl">Logged in as</div>'
                f'<div class="u-name">{html_lib.escape(str(st.session_state["user"]))}</div>'
                f'<div class="u-lbl">Role</div>'
                f'<span class="u-role">{html_lib.escape(str(st.session_state.get("role", "-")))}</span></div>',
                unsafe_allow_html=True)
            if st.button("🚪 Logout", use_container_width=True, key="logout_btn"):
                log_event("LOGOUT", f"User {st.session_state['user']} logged out.")
                st.session_state.pop("user", None)
                st.session_state.pop("role", None)
                done("Logged out successfully.")
            with st.expander("🔑 Change password"):
                with st.form("chg_pw_form", clear_on_submit=True):
                    cur_pw = st.text_input("Current password", type="password", key="cp_cur")
                    new_pw1 = st.text_input("New password (min 8 chars)", type="password", key="cp_new1")
                    new_pw2 = st.text_input("Confirm new password", type="password", key="cp_new2")
                    chg = st.form_submit_button("Update password", use_container_width=True)
                if chg:
                    row = q("SELECT password FROM users WHERE username=%s", (st.session_state["user"],))
                    if not row or not verify_password(row[0]["password"], cur_pw):
                        st.error("Current password thik nei.")
                    elif len(new_pw1) < 8:
                        st.error("New password kom pokkhe 8 character hote hobe.")
                    elif new_pw1 != new_pw2:
                        st.error("Dui password mile ni.")
                    elif change_password(st.session_state["user"], new_pw1):
                        st.success("Password updated.")
            if st.session_state.get("role") == "Store Manager":
                user_admin_panel()
        else:
            with st.form("login_form", clear_on_submit=False):
                u = st.text_input("Username", placeholder="Enter your username", key="login_user")
                p = st.text_input("Password", type="password", placeholder="Enter your password", key="login_pass")
                submitted = st.form_submit_button("🔓 Sign in", use_container_width=True)
            if submitted:
                if not u.strip() or not p:
                    st.error("Username ar password dui-i din.")
                else:
                    r = q("SELECT password, role, COALESCE(status,'Active') AS status FROM users WHERE username=%s", (u.strip(),))
                    if r and verify_password(r[0]["password"], p):
                        if r[0]["status"] == "Pending":
                            st.warning("Apnar registration Store Manager-er approval-er opekkhay ache.")
                        elif r[0]["status"] != "Active":
                            st.error("Ei account active nei. Store Manager-er sathe jogajog korun.")
                        else:
                            st.session_state["user"] = u.strip()
                            st.session_state["role"] = r[0]["role"]
                            log_event("LOGIN", f"User {u.strip()} logged in as {r[0]['role']}.")
                            done(f"Welcome, {u.strip()}!")
                    else:
                        st.error("Username ba password vul.")

            with st.expander("📝 Registration"):
                st.caption("Notun account Store Manager approve korle chalu hobe.")
                with st.form("reg_form", clear_on_submit=True):
                    ru = st.text_input("Username*", key="reg_user", placeholder="3-30 letters / digits / _ . -")
                    rn = st.text_input("Full name*", key="reg_name")
                    rp1 = st.text_input("Password* (min 8 chars)", type="password", key="reg_pw1")
                    rp2 = st.text_input("Confirm password*", type="password", key="reg_pw2")
                    reg = st.form_submit_button("Submit registration", use_container_width=True)
                if reg:
                    if not USERNAME_RE.fullmatch(ru.strip()):
                        st.error("Username 3-30 character, shudhu letter / digit / _ . - hote parbe.")
                    elif not rn.strip():
                        st.error("Full name din.")
                    elif len(rp1) < 8:
                        st.error("Password kom pokkhe 8 character hote hobe.")
                    elif rp1 != rp2:
                        st.error("Dui password mile ni.")
                    elif register_user(ru.strip(), rn.strip(), rp1):
                        st.success("Registration request pathano hoyeche. Store Manager approve korle login korte parben.")

            with st.expander("🔑 Forgot Password"):
                st.caption("Username din. Request Store Manager-er kache jabe; manager temporary password dibe, "
                           "login-er por password change korben.")
                with st.form("fp_form", clear_on_submit=True):
                    fu = st.text_input("Username", key="fp_user")
                    fps = st.form_submit_button("Send reset request", use_container_width=True)
                if fps:
                    if not fu.strip():
                        st.error("Username din.")
                    elif request_password_reset(fu.strip()):
                        st.success("Username thakle reset request Store Manager-er kache pathano hoyeche.")


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
    return (f"SL {r['sl_no']} | S/N {r.get('serial') or '-'} | {r['factory_name']} | {r['item_name']} "
            f"[{r['size'] or '-'}] | {r['prod_id']} | Stock {float(r['stock'] or 0):g}")


def next_free_temp(fac):
    used = {str(r["prod_id"]) for r in q("SELECT prod_id FROM inventory WHERE factory_name=%s", (fac,))}
    n = 1
    while f"TEMP-{n:04d}" in used:
        n += 1
    return f"TEMP-{n:04d}"


def insert_tx(fac, officer, sl, pid, name, qty, ttype, day, notes, date_s, time_s, verif, grn="Not Required",
              supplier="", challan=""):
    run("""INSERT INTO transactions (factory_name, officer_name, sl_no, prod_id, item_name, qty, trans_type, day,
           notes, date, time, verification_status, erp_grn_status, supplier_name, challan_no)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (fac, officer, sl, pid, name, qty, ttype, day, notes, date_s, time_s, verif, grn, supplier, challan))


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
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8590C")),
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


def budget_bar_html(pct, label="Budget consumption"):
    """Dynamic bar: green below 70%, amber 70-85%, red above the alert limit."""
    width = min(max(pct, 0), 100)
    color = "#16A34A" if pct < 70 else ("#F59E0B" if pct <= BUDGET_ALERT_PCT else "#DC2626")
    return (f'<div class="bar-label"><span>{html_lib.escape(label)}</span><span>{pct:.1f}%</span></div>'
            f'<div class="bar-wrap"><div class="bar-fill" style="width:{width:.1f}%;background:{color};"></div></div>')


def status_badge(text):
    t = str(text or "")
    if t.startswith("Physically"):
        bg, fg, lab = "#DCFCE7", "#166534", "✔ Physically Verified"
    elif t == "Verified":
        bg, fg, lab = "#DBEAFE", "#1E40AF", "✔ Verified"
    elif t == "Not Required" or t == "N/A" or not t:
        bg, fg, lab = "#F1F5F9", "#475569", "• Normal"
    else:
        bg, fg, lab = "#FFF4E6", "#C2410C", t
    return f'<span class="status-badge" style="background:{bg};color:{fg}">{html_lib.escape(lab)}</span>'


# ============================================================
#  ITEM RESOLVING
# ============================================================
def resolve_item(fac, key, in_stock_only=False):
    """SL No (exact) -> Serial No (exact) -> ERP code -> name (exact) -> partial name/size/serial. Returns (row, candidates).
    in_stock_only=True hides items whose current stock is 0 or negative (used for issue-type transactions)."""
    k = str(key or "").strip()
    if not k:
        return None, []
    stages = []
    if k.isdigit():
        stages.append(("sl_no=%s", [int(k)]))
    stages.append(("LOWER(TRIM(COALESCE(serial_no,'')))=LOWER(%s)", [k]))
    stages.append(("LOWER(TRIM(prod_id))=LOWER(%s)", [k]))
    stages.append(("LOWER(TRIM(item_name))=LOWER(%s)", [k]))
    like = f"%{k.lower()}%"
    stages.append(("(LOWER(item_name) LIKE %s OR LOWER(COALESCE(size,'')) LIKE %s OR LOWER(COALESCE(serial_no,'')) LIKE %s)",
                   [like, like, like]))
    fsql, fp = fw(fac)
    stock_sql = " AND COALESCE(current_stock,0) > 0" if in_stock_only else ""
    for where, params in stages:
        rows = q(f"SELECT {INV_COLS} FROM inventory WHERE {where}{stock_sql}{fsql} ORDER BY factory_name, sl_no", params + fp)
        if len(rows) == 1:
            return rows[0], rows
        if len(rows) > 1:
            return None, rows
    return None, []


def search_items(fac, term, in_stock_only=False):
    like = f"%{term.lower()}%"
    fsql, fp = fw(fac)
    stock_sql = " AND COALESCE(current_stock,0) > 0" if in_stock_only else ""
    return q(f"""SELECT {INV_COLS} FROM inventory
                 WHERE (LOWER(item_name) LIKE %s OR LOWER(COALESCE(size,'')) LIKE %s OR LOWER(prod_id) LIKE %s
                        OR LOWER(COALESCE(serial_no,'')) LIKE %s OR CAST(sl_no AS TEXT)=%s){stock_sql}{fsql}
                 ORDER BY CASE WHEN LOWER(COALESCE(serial_no,''))=LOWER(%s) THEN 0 ELSE 1 END, sl_no LIMIT 100""",
             [like, like, like, like, term] + fp + [term])


def serial_owner(fac, serial, exclude_sl=None):
    """Item of this factory that already carries the serial number (or None)."""
    sn = (serial or "").strip()
    if not sn:
        return None
    rows = q("""SELECT sl_no, item_name, COALESCE(size,'') AS size FROM inventory
                WHERE factory_name=%s AND LOWER(TRIM(COALESCE(serial_no,'')))=LOWER(%s)""", (fac, sn))
    rows = [r for r in rows if exclude_sl is None or r["sl_no"] != exclude_sl]
    return rows[0] if rows else None


def is_duplicate_tx(fac, sl, ttype, qty, date_s, user, notes):
    """True when the newest transaction of this item is an identical one saved within the last 2 minutes
    (same type, qty, date, officer and remarks) - i.e. a repeated click / stale form."""
    last = q("""SELECT qty, trans_type, officer_name, date, time, notes FROM transactions
                WHERE factory_name=%s AND sl_no=%s ORDER BY id DESC LIMIT 1""", (fac, sl))
    if not last:
        return False
    t = last[0]
    if not (t["trans_type"] == ttype and abs(float(t["qty"] or 0) - float(qty)) < 1e-9
            and t["officer_name"] == user and t["date"] == date_s
            and str(t["notes"] or "").strip().startswith(str(notes or "").strip())):
        return False
    try:
        tm = datetime.strptime(str(t["time"]).strip(), "%I:%M %p").time()
    except ValueError:
        return False
    saved = datetime.combine(datetime.now().date(), tm)
    return 0 <= (datetime.now() - saved).total_seconds() < 120


def inv_options(fac):
    fsql, fp = fw(fac)
    rows = q(f"""SELECT sl_no, prod_id, factory_name, item_name, COALESCE(size,'') AS size, department, category,
                 COALESCE(serial_no,'') AS serial_no, COALESCE(erp_stock,0) AS erp_stock, COALESCE(current_stock,0) AS current_stock,
                 COALESCE(unit_price,0) AS unit_price, COALESCE(NULLIF(unit_name,''),'Pcs') AS unit_name
                 FROM inventory WHERE 1=1{fsql} ORDER BY factory_name, sl_no""", fp)
    return {f"SL {r['sl_no']} | {r['factory_name']} | {r['item_name']} [{r['size'] or '-'}] | {r['prod_id']}"
            + (f" | S/N {r['serial_no']}" if r["serial_no"] else ""): r for r in rows}


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


def verification_needed(fac, sl, tx_dt):
    """Physical-verification rule. The SAME product (factory + SL No) issued on the 3 calendar days directly
    before tx_dt (Day 1, Day 2, Day 3) -> tx_dt is Day 4 and physical verification is required.
    The days must be CONSECUTIVE: a missing day breaks the run. A day that was physically verified
    starts a new run. Returns (needed, consecutive_days_found)."""
    days = [(tx_dt - timedelta(days=k)).strftime(DATE_FMT) for k in range(1, VERIFY_AFTER_DAYS + 1)]
    rows = q("""SELECT date, verification_status FROM transactions
                WHERE factory_name=%s AND sl_no=%s AND trans_type IN ('Issued','Internal Issue') AND date IN %s""",
             (fac, sl, tuple(days)))
    by_day = {}
    for r in rows:
        by_day.setdefault(str(r["date"]).strip(), []).append(str(r["verification_status"] or ""))
    streak = 0
    for d in days:                      # D-1, D-2, D-3 : stop at the first gap / verified day
        sts = by_day.get(d)
        if not sts or any(s.startswith("Physically") for s in sts):
            break
        streak += 1
    return streak >= VERIFY_AFTER_DAYS, streak


# ============================================================
#  IMPORT ENGINE (Master Inventory, in-memory index)
# ============================================================
def empty_index():
    return {"all": [], "name": {}, "code": {}, "codes": set(), "max_sl": 0, "temp": 0, "serials": {}}


def idx_add(idx, sl, code, name, size, serial=""):
    e = {"sl": sl, "code": str(code or ""), "name": name or "", "size": size or "",
         "nn": norm_name(name), "ns": norm_size(size), "serial": str(serial or "").strip()}
    idx["all"].append(e)
    if e["serial"]:
        idx["serials"][e["serial"].lower()] = sl
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
    for r in q("SELECT sl_no, prod_id, item_name, COALESCE(size,'') AS size, COALESCE(serial_no,'') AS serial_no "
               "FROM inventory WHERE factory_name=%s", (fac,)):
        idx_add(idx, r["sl_no"], r["prod_id"], r["item_name"], r["size"], r["serial_no"])
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


def idx_insert(fac, idx, code, name, size, dept, cat, erp, stock, price, unit, serial=""):
    final = temp_code(idx) if is_blank_code(code) else unique_code(idx, code, size)
    idx["max_sl"] += 1
    sl = idx["max_sl"]
    run("""INSERT INTO inventory (sl_no, prod_id, factory_name, item_name, size, department, category,
           erp_stock, current_stock, unit_price, erp_status, unit_name, serial_no)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ERP Pending',%s,%s)""",
        (sl, final, fac, name, size or "", dept or "Maintenance", cat or "Uncategorized (Edit Later)",
         erp, stock, price or 0.0, unit or "Pcs", (serial or "").strip()))
    idx_add(idx, sl, final, name, size, serial)
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
    st_ = dict(updated=0, added=0, added_zero=0, mirrored=0, dup=0, no_size=0, size_fill=0, code_fix=0, queue_closed=0,
               serial_set=0, serial_conflict=0)
    touched = set()
    for r in rows:
        code = "" if is_blank_code(r["code"]) else str(r["code"]).strip()
        name = r["name"] or code
        size = r["size"] or ""
        serial = str(r.get("serial") or "").strip()
        e = idx_find(idx, code, name, size)
        if e:
            if e["sl"] in touched:
                st_["dup"] += 1
            touched.add(e["sl"])
            new_size = size if (size and not e["ns"]) else None
            new_code = unique_code(idx, code, size or e["size"]) if (code and e["code"].upper().startswith("TEMP-")) else None
            new_serial = None
            if serial and serial.lower() != str(e.get("serial") or "").lower():
                owner = idx["serials"].get(serial.lower())
                if owner is None or owner == e["sl"]:
                    new_serial = serial
                else:
                    st_["serial_conflict"] += 1
            run("""UPDATE inventory SET current_stock=COALESCE(%s,current_stock), erp_stock=COALESCE(%s,erp_stock),
                   unit_price=COALESCE(%s,unit_price), unit_name=COALESCE(%s,unit_name),
                   size=COALESCE(%s,size), prod_id=COALESCE(%s,prod_id), serial_no=COALESCE(%s,serial_no)
                   WHERE sl_no=%s AND factory_name=%s""",
                (r["phys"], r["erp"], r["price"], r["unit"], new_size, new_code, new_serial, e["sl"], fac))
            if new_serial:
                e["serial"] = new_serial
                idx["serials"][new_serial.lower()] = e["sl"]
                st_["serial_set"] += 1
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
            ins_serial = serial
            if serial and serial.lower() in idx["serials"]:
                ins_serial = ""
                st_["serial_conflict"] += 1
            idx_insert(fac, idx, code, name, size, r["dept"], r["cat"], erp0, phys0, r["price"], r["unit"], ins_serial)
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
        "serial": find_col(df, ["serial no", "serial number", "serial_no", "serial", "s/n"]),
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
            "serial": txt(r[c["serial"]]) if c.get("serial") else "",
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
    if write and "CONSOLIDATED" in FAC:
        st.error("CONSOLIDATED view-te edit kora jabe na. Specific factory select korun.")
        return False
    return True


def inventory_count():
    return int(q(f"SELECT COUNT(*) AS n FROM inventory WHERE 1=1{FSQL}", FP)[0]["n"] or 0)


# ============================================================
#  HEADER (factory, live date/time, user)
# ============================================================
def local_now():
    """Current time in the application's intended timezone (Asia/Dhaka), never hard-coded."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("Asia/Dhaka"))
    except Exception:
        return datetime.now(timezone(timedelta(hours=6)))


def render_header():
    """Slim one-line strip shown at the top of every tab (tabs themselves sit above everything)."""
    user_txt = (f"{st.session_state['user']} · {st.session_state.get('role', '')}"
                if st.session_state.get("user") else "Guest (view only)")
    st.markdown(
        f'<div class="strip"><span>🏭 <b>{html_lib.escape(FAC)}</b></span>'
        f'<span>🕒 <b>{local_now():%d %b %Y | %I:%M %p}</b></span>'
        f'<span>👤 {html_lib.escape(user_txt)}</span></div>', unsafe_allow_html=True)


def sidebar_clock():
    with st.sidebar:
        components.html("""
        <div style="font-family:Inter,sans-serif;background:#fff;border-radius:12px;box-shadow:0 4px 10px rgba(124,45,18,.2);
                    padding:8px 14px;">
          <div id="clk" style="font-size:16px;font-weight:800;color:#1E293B;">--:--:--</div>
          <div id="dt" style="font-size:11.5px;color:#64748B;margin-top:2px;">--</div>
          <div style="font-size:10.5px;color:#C2410C;font-weight:700;margin-top:2px;">Asia/Dhaka</div>
        </div>
        <script>
          function tick(){
            const n = new Date(); const tz = {timeZone:'Asia/Dhaka'};
            document.getElementById('clk').innerText = n.toLocaleTimeString('en-GB', Object.assign({hour12:false}, tz));
            document.getElementById('dt').innerText = n.toLocaleDateString('en-GB', Object.assign({weekday:'short',day:'2-digit',month:'short',year:'numeric'}, tz));
          }
          tick(); setInterval(tick, 1000);
        </script>""", height=82)


# ============================================================
#  HOME - EXECUTIVE OVERVIEW (budget metrics)
# ============================================================
def load_budget_data():
    cons = qdf(f"""SELECT t.factory_name, t.date, t.qty, COALESCE(i.unit_price,0) AS price,
                   COALESCE(i.category,'') AS category
                   FROM transactions t JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                   WHERE t.trans_type IN ('Issued','Internal Issue'){fw(FAC, 't.')[0]}""", FP)
    bud = qdf(f"SELECT factory_name, category_name, allocated_budget FROM category_budgets WHERE 1=1{FSQL}", FP)
    if not cons.empty:
        cons["qty"] = cons["qty"].astype(float)
        cons["price"] = cons["price"].astype(float)
        cons["cost"] = cons["qty"] * cons["price"]
        cons["month"] = cons["date"].apply(lambda s: parse_date(s).strftime("%b-%Y") if parse_date(s) else "")
    else:
        cons = pd.DataFrame(columns=["factory_name", "date", "qty", "price", "category", "cost", "month"])
    return cons, bud


def tab_dashboard():
    cur_label = datetime.now().strftime("%b-%Y")
    cons, bud = load_budget_data()
    months = {m for m in cons["month"] if m}
    options = ["All time"] + sorted(months | {cur_label}, key=lambda s: datetime.strptime(s, "%b-%Y"), reverse=True)

    t_l, t_r = st.columns([3, 1])
    with t_l:
        st.markdown('<div class="section-title">Executive Overview · Budget Control</div>', unsafe_allow_html=True)
    with t_r:
        period = st.selectbox("Period", options, index=options.index(cur_label), key="dash_period",
                              label_visibility="collapsed")

    view = cons if period == "All time" else cons[cons["month"] == period]
    total_budget = float(bud["allocated_budget"].astype(float).sum()) if not bud.empty else 0.0
    consumption = float(view["cost"].sum()) if not view.empty else 0.0
    remaining = total_budget - consumption
    pct = (consumption / total_budget * 100) if total_budget > 0 else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Monthly Budget", f"৳ {total_budget:,.0f}")
    c2.metric("Total Consumption Cost", f"৳ {consumption:,.0f}")
    c3.metric("Expense % of Budget", f"{pct:.1f}%")
    c4.metric("Remaining Balance", f"৳ {remaining:,.0f}")

    st.markdown('<div class="fin-card">' + budget_bar_html(pct) + '</div>', unsafe_allow_html=True)

    if total_budget <= 0:
        st.info("Budget set kora nei. [10] BUDGET tab-e allocation dekhun.")
    elif pct > 100:
        st.error(f"🚨 BUDGET EXCEEDED: Consumption {pct:.1f}% - budget ৳ {abs(remaining):,.0f} beshi kharc hoyeche.")
    elif pct > BUDGET_ALERT_PCT:
        st.warning(f"⚠️ OPERATIONAL ALERT: Budget consumption {pct:.1f}% (limit {BUDGET_ALERT_PCT}%). "
                   f"Baki budget ৳ {max(remaining, 0):,.0f}. Issue-er agey approval nin.")
    else:
        st.success(f"✅ Budget safe: consumption {pct:.1f}% (alert limit {BUDGET_ALERT_PCT}%).")


# ============================================================
#  TAB 1 - TRANSACTIONS (daily entry, top priority)
# ============================================================
@tx
def save_transaction(fac, item, qty, ttype, tx_dt, notes, verified, xfer_ok, supplier="", challan=""):
    user = st.session_state.get("user", "")
    sl, pid, name = item["sl_no"], item["prod_id"], item["item_name"]
    stock = float(item["stock"] or 0)
    date_s, time_s, day = tx_dt.strftime(DATE_FMT), datetime.now().strftime("%I:%M %p"), tx_dt.day
    verif = "Verified"

    if ttype in ISSUE_TYPES:
        needed, _streak = verification_needed(fac, sl, tx_dt)
        if needed and not verified:
            st.error("Physical verification required: ei product porpor 3 din issue hoyeche - 4th din verification tick korun.")
            return False
        verif = "Physically Verified" if (needed and verified) else "Not Required"

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
        insert_tx(fac, user, sl, pid, name, qty, ttype, day, notes, date_s, time_s, "Verified", grn,
                  supplier if ttype == "Supplier. Rec" else "", challan if ttype == "Supplier. Rec" else "")
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


def zebra_styles(row):
    bg = "#FFF7ED" if row.name % 2 else "#FFFFFF"
    return [f"background-color:{bg}"] * len(row)


def tx_manager_panel(df, kp, title="🔐 Manager: Delete / Edit a transaction"):
    """Edit (date / remarks) or delete (stock is reverted) one of the transactions shown in the table above.
    Needs the Store Manager password; deletion also needs an explicit confirmation tick."""
    with st.expander(title):
        if df is None or df.empty:
            st.caption("Kono transaction nei.")
            return
        rows = {int(r["id"]): r for r in df.head(500).to_dict("records")}
        tid = int(st.selectbox("Transaction ID", list(rows), key=f"{kp}_mgr_id",
                               format_func=lambda i: f"ID {i} | {rows[i].get('item_name', '')} | qty {rows[i].get('qty', '')} | {rows[i].get('date', '')}"))
        cur = q("SELECT date, notes FROM transactions WHERE id=%s", (tid,))
        if not cur:
            st.warning("Transaction paoa jay nai (ager-i delete hoye thakte pare).")
            return
        pw_ok = mgr_check(f"{kp}_mgr_pw")
        conf = confirm_box(f"{kp}_del_conf_{tid}", "⚠️ Ami confirm korchi - transaction delete hobe ar stock revert hobe.")
        if st.button("🗑 Delete & revert stock", key=f"{kp}_del"):
            if not pw_ok:
                st.error("Manager password thik nei.")
            elif not conf:
                st.error("Delete confirm tick korun.")
            elif delete_transaction(tid):
                done("Transaction deleted, stock reverted.")
        cur_d = parse_date(cur[0]["date"])
        ed = st.date_input("New date", value=cur_d.date() if cur_d else date.today(), key=f"{kp}_ed_date_{tid}")
        en = st.text_input("Remarks", value=cur[0]["notes"] or "", key=f"{kp}_ed_notes_{tid}")
        if st.button("💾 Save edit", key=f"{kp}_ed_btn"):
            if not pw_ok:
                st.error("Manager password thik nei.")
            elif update_tx_meta(tid, ed.strftime(DATE_FMT), en.strip()):
                done("Transaction updated.")


def tab_transactions():
    fac, fsql, fp = FAC, FSQL, FP
    g = st.session_state.get("tx_gen", 0)   # bumps after every successful save -> all entry widgets start fresh
    if inventory_count() == 0 and not is_cons_view:
        st.info("📦 Ei factory-r inventory khali. [2] INVENTORY → ➕ Add / Import theke opening stock upload korun.")
    po_n = po_pending_counts()
    po_c1, _po_c2 = st.columns([1.3, 2.7])
    with po_c1:
        st.button(f"ERP PO Pending\n\n{po_n['total']}", key="po_card_btn", on_click=go_erp_po_pending,
                  use_container_width=True)
        st.caption(f"Issue {po_n['issue']} · Received {po_n['recv']}  —  click to open ERP Audit → ERP PO Pending")
    left, right = st.columns([1.05, 2], gap="large")
    with left:
        try:
            form_box = st.container(border=True, key="tx_form_box")
        except TypeError:   # very old Streamlit without container(key=...)
            form_box = st.container(border=True)
        with form_box:
            st.markdown('<div class="section-title">New Transaction</div>', unsafe_allow_html=True)
            st.markdown(f'<span class="officer-pill">👤 Officer: {html_lib.escape(str(st.session_state.get("user", "-")))}</span>',
                        unsafe_allow_html=True)
            if is_cons_view:
                st.warning("CONSOLIDATED view-te entry hoy na. Sidebar theke factory select korun.")
            type_label = st.selectbox("Transaction Type", list(TRANS_CODES), key="tx_type")
            ttype = TRANS_CODES[type_label]
            supplier, challan = "", ""
            if ttype == "Supplier. Rec":
                supplier = st.text_input("Supplier", key=f"tx_supplier_{g}", placeholder="Supplier name")
                challan = st.text_input("Challan Number", key=f"tx_challan_{g}", placeholder="Challan / delivery note number")
            # Items with stock 0 (or negative) can not be issued / reduced, so they are not offered for those types.
            # Receipts and (+) adjustments still see every item, otherwise an item at 0 could never be restocked.
            stock_only = ttype in ISSUE_TYPES or ttype == ADJ_OUT
            search = st.text_input("🔍 Search (Serial No / Name / Size / ERP / SL)", key=f"tx_search_{g}",
                                   placeholder="Serial No, naam, SL, ERP code...")
            item, blocked, need_xfer, xfer_ok = None, False, False, False
            if search.strip():
                cands = search_items(fac, search.strip(), stock_only)
                if cands:
                    opts = {item_label(c): c for c in cands}
                    item = opts[st.selectbox("Pick item", list(opts), key=f"tx_pick_{g}")]
                elif stock_only and search_items(fac, search.strip(), False):
                    st.warning("Item paoa geche kintu current stock 0 - tai issue-r list-e dekhano hocche na.")
                else:
                    st.warning("Kichu paoa jay nai.")
            else:
                key = st.text_input("SL No / ERP Code / Serial No", key=f"tx_key_{g}", placeholder="SL, ERP code ba Serial No")
                if key.strip():
                    item, cands = resolve_item(fac, key.strip(), stock_only)
                    if item is None:
                        if cands:
                            st.error(f"{len(cands)} ta item match kore - exact SL No / Serial No likhun")
                        else:
                            alt = resolve_item(fac, key.strip(), False)[0] if stock_only else None
                            if alt is not None:
                                st.warning(f"'{alt['item_name']}' paoa geche kintu stock {float(alt['stock']):g} - issue kora jabe na.")
                            else:
                                st.error("Item paoa jay nai")

            qc, dc = st.columns(2)
            qty = qc.number_input("Quantity", min_value=0.0, step=1.0, key=f"tx_qty_{g}")
            tx_date = dc.date_input("Date", value=date.today(), max_value=date.today(), key="tx_date")
            verified, need_verif = False, False
            if item is not None and ttype in ISSUE_TYPES:
                need_verif, v_streak = verification_needed(fac, item["sl_no"], tx_date)
                if need_verif:
                    st.warning(f"Physical verification required: ei product porpor {v_streak} din issue hoyeche (4th consecutive day).")
                    verified = st.checkbox("Physically Verified (required today)", key=f"tx_ver_{g}")
            notes = st.text_input("Remarks", key=f"tx_notes_{g}", placeholder="Optional note")

            if item is not None:
                st.info(f"**{item['item_name']}** [{item['size'] or '-'}]  ·  Serial **{item['serial'] or '-'}**  ·  SL {item['sl_no']}  ·  "
                        f"ERP {item['prod_id']}  ·  Stock **{float(item['stock']):g}**  ·  "
                        f"Short: {max(float(item['erp']) - float(item['stock']), 0):g}")
                if qty > 0:
                    if ttype in ISSUE_TYPES and need_verif and not verified:
                        blocked = True
                    if qty > float(item["stock"]) and ttype in ISSUE_TYPES:
                        shortage = qty - float(item["stock"])
                        other = find_same_in_other(item["prod_id"], item["item_name"], other_factory(fac), item["size"])
                        if other and float(other["stock"] or 0) >= shortage:
                            need_xfer = True
                            st.warning(f"⚠️ Stock short {shortage:g}. {other['factory_name']} theke auto-transfer hobe "
                                       f"({other['item_name']} [{other['prod_id']}], stock {float(other['stock']):g}, "
                                       f"match: {other['level']}).")
                            xfer_ok = st.checkbox("Transfer confirm kore issue korun", key=f"tx_xfer_{g}")
                        else:
                            st.error(f"Shortage {shortage:g} - other unit-e enough stock/same item nei.")
                            blocked = True
                    elif qty > float(item["stock"]) and ttype not in RECEIPT_TYPES:
                        st.error("Stock kom ache.")
                        blocked = True

            can_write = bool(st.session_state.get("user")) and st.session_state.get("role") != "Auditor" and not is_cons_view
            disabled = item is None or blocked or qty <= 0 or (need_xfer and not xfer_ok) or not can_write
            if not can_write:
                st.caption("Save korte login + specific factory + non-Auditor role lage.")
            if st.button("💾 Save & Update Stock", type="primary", disabled=disabled, use_container_width=True, key="tx_save"):
                if st.session_state.get("tx_saved_gen") == g:
                    st.warning("Ei form already save hoyeche. Notun transaction-er jonno notun kore item select korun.")
                elif guard():
                    fresh = q(f"SELECT {INV_COLS} FROM inventory WHERE sl_no=%s AND factory_name=%s",
                              (item["sl_no"], item["factory_name"]))
                    if not fresh:
                        st.error("Item ar paoa jacche na. Page refresh kore abar select korun.")
                    else:
                        item = fresh[0]   # always work with the live stock, never a stale copy
                        if is_duplicate_tx(item["factory_name"], item["sl_no"], ttype, qty, tx_date.strftime(DATE_FMT),
                                           st.session_state.get("user", ""), notes):
                            st.error("🚫 Duplicate block: ekdom ek-i transaction ei matro save hoyeche. "
                                     "Quantity / remarks bodle ba kichukkhon por abar korun.")
                        elif save_transaction(fac, item, qty, ttype, tx_date, notes, verified, xfer_ok,
                                              supplier.strip(), challan.strip()):
                            st.session_state["tx_saved_gen"] = g
                            st.session_state["tx_gen"] = g + 1
                            done("✅ Transaction saved, stock updated. Form reset hoyeche - porer transaction-er jonno ready.")

    with right:
        st.markdown('<div class="section-title">Recent Transactions</div>', unsafe_allow_html=True)
        rs = st.text_input("🔍 Search transactions (Item / Serial / ERP / SL / Officer)", key="tx_recent_search")
        extra, ep = "", []
        if rs.strip():
            like = f"%{rs.strip().lower()}%"
            extra = """ AND (LOWER(item_name) LIKE %s OR LOWER(prod_id) LIKE %s OR LOWER(COALESCE(officer_name,'')) LIKE %s
                        OR CAST(sl_no AS TEXT)=%s OR EXISTS (SELECT 1 FROM inventory i2 WHERE i2.sl_no=transactions.sl_no
                            AND i2.factory_name=transactions.factory_name AND LOWER(COALESCE(i2.serial_no,'')) LIKE %s))"""
            ep = [like, like, like, rs.strip(), like]
        tdf = qdf(f"""SELECT id, factory_name, officer_name, sl_no,
                      (SELECT COALESCE(i.serial_no,'') FROM inventory i WHERE i.sl_no=transactions.sl_no
                         AND i.factory_name=transactions.factory_name LIMIT 1) AS serial_no,
                      prod_id, item_name, qty, trans_type,
                      COALESCE(supplier_name,'') AS supplier_name, COALESCE(challan_no,'') AS challan_no,
                      verification_status, notes, date, time FROM transactions WHERE 1=1{fsql}{extra}
                      ORDER BY id DESC LIMIT 300""", fp + ep)
        if not tdf.empty:
            tdf["date_time"] = tdf[["date", "time"]].fillna("").agg(" ".join, axis=1)
            tdf["type"] = tdf["trans_type"].map(lambda c: TRANS_LABELS.get(c, c))
            tdf["status"] = tdf["verification_status"].fillna("N/A")
            show = tdf[["id", "factory_name", "officer_name", "sl_no", "serial_no", "prod_id", "item_name", "qty", "type",
                        "supplier_name", "challan_no", "status", "notes", "date_time"]]
            st.dataframe(show.style.apply(zebra_styles, axis=1), hide_index=True,
                         use_container_width=True, height=340)
        else:
            st.dataframe(tdf, hide_index=True, use_container_width=True, height=340)
        export_buttons(tdf, "transactions")
        tx_manager_panel(tdf, "tx")

    st.markdown('<div class="section-title">Low & Negative Stock Alerts (≤ 5 pcs)</div>', unsafe_allow_html=True)
    alerts = qdf(f"""SELECT factory_name, sl_no, COALESCE(serial_no,'') AS serial_no, prod_id, item_name,
                     COALESCE(size,'') AS size, current_stock
                     FROM inventory WHERE current_stock <= 5{fsql} ORDER BY current_stock ASC""", fp)
    if not alerts.empty:
        alerts["status"] = alerts.current_stock.apply(lambda s: "🔴 NEGATIVE (URGENT)" if s < 0 else "⚠️ LOW STOCK")
    st.dataframe(alerts, hide_index=True, use_container_width=True)
    export_buttons(alerts, "low_stock_alerts")


# ============================================================
#  TAB 2 - INVENTORY MASTER
# ============================================================
@tx
def add_item(fac, code, name, size, dept, cat, stock, price, serial=""):
    serial = (serial or "").strip()
    ex = find_same_item(fac, name, size)
    owner = serial_owner(fac, serial)
    if owner and (not ex or owner["sl_no"] != ex["sl_no"]):
        st.error(f"Serial '{serial}' already used: SL {owner['sl_no']} ({owner['item_name']} [{owner['size'] or '-'}]).")
        return False
    if ex:  # same name + size already exists -> stock add, no duplicate
        run("""UPDATE inventory SET current_stock=COALESCE(current_stock,0)+%s,
               unit_price=CASE WHEN %s>0 THEN %s ELSE unit_price END WHERE sl_no=%s AND factory_name=%s""",
            (stock, price, price, ex["sl_no"], fac))
        if serial:
            run("UPDATE inventory SET serial_no=%s WHERE sl_no=%s AND factory_name=%s AND COALESCE(serial_no,'')=''",
                (serial, ex["sl_no"], fac))
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
           erp_stock, current_stock, unit_price, erp_status, serial_no)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'ERP Pending',%s)""",
        (int(mx) + 1, code, fac, name, size, dept, cat, stock, stock, price, serial))
    mirrored = mirror_to_other(fac, code, name, size, dept, cat, price)
    audit("ADD_ITEM", f"{fac}: {name} [{size}] [{code}]" + (f" S/N {serial}" if serial else "")
          + (" + copied to other unit" if mirrored else ""))
    return ("new", int(mx) + 1)


@tx
def update_item(fac, sl, old_code, old_name, code, name, size, dept, cat, erp, phys, price, unit, serial=""):
    serial = (serial or "").strip()
    if any(norm_name(r["item_name"]) == norm_name(name) and norm_size(r["size"]) == norm_size(size)
           for r in q("SELECT item_name, COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s AND sl_no<>%s", (fac, sl))):
        st.error(f"'{name}' [{size}] already exists in {fac}!")
        return False
    if code != old_code and q("SELECT 1 AS x FROM inventory WHERE factory_name=%s AND prod_id=%s AND sl_no<>%s", (fac, code, sl)):
        st.error(f"ERP Code '{code}' already used!")
        return False
    owner = serial_owner(fac, serial, exclude_sl=sl)
    if owner:
        st.error(f"Serial '{serial}' already used: SL {owner['sl_no']} ({owner['item_name']} [{owner['size'] or '-'}]).")
        return False
    run("""UPDATE inventory SET prod_id=%s, item_name=%s, size=%s, department=%s, category=%s, erp_stock=%s,
           current_stock=%s, unit_price=%s, unit_name=%s, serial_no=%s WHERE sl_no=%s AND factory_name=%s""",
        (code, name, size, dept, cat, erp, phys, price, unit, serial, sl, fac))
    if code != old_code or name != old_name:
        run("UPDATE transactions SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (code, name, sl, fac))
        run("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND prod_id=%s", (code, name, fac, old_code))
    audit("EDIT_INVENTORY", f"{fac} SL {sl}: [{old_code}] {old_name} -> [{code}] {name} [{size}] S/N {serial or '-'}")
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
    inv = qdf(f"""SELECT factory_name, sl_no, COALESCE(serial_no,'') AS serial_no, prod_id, item_name,
                  COALESCE(size,'') AS size, department, category,
                  COALESCE(erp_stock,0) AS erp_stock, COALESCE(current_stock,0) AS current_stock,
                  COALESCE(unit_price,0) AS unit_price, erp_status FROM inventory WHERE 1=1{FSQL}
                  ORDER BY factory_name, sl_no""", FP)
    if inv.empty:
        st.info("Kono item nei. ➕ Add / Import tab theke item add ba import korun.")
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
    term = a.text_input("🔍 Search (Serial No / Item / Size / ERP / Dept / Category)", key="inv_search")
    mode = b.selectbox("Show", ["All Items (incl. zero)", "Zero / No Stock Only", "In Stock Only (> 0)", "Items without Size"], key="inv_mode")
    view = inv
    if mode == "Zero / No Stock Only":
        view = inv[inv.current_stock <= 0]
    elif mode == "In Stock Only (> 0)":
        view = inv[inv.current_stock > 0]
    elif mode == "Items without Size":
        view = inv[inv["size"].astype(str).str.strip() == ""]
    if term:
        m = view[["item_name", "size", "prod_id", "serial_no", "department", "category"]].astype(str).apply(
            lambda col: col.str.contains(term, case=False, regex=False)).any(axis=1)
        view = view[m]
    st.caption(f"Showing {len(view)} items")
    st.dataframe(view, hide_index=True, use_container_width=True, height=420)
    export_buttons(view, "inventory")


def inv_add_import_view():
    with st.container(border=True):
        st.markdown('<div class="section-title">Add New Item</div>', unsafe_allow_html=True)
        with st.form("add_item_form", clear_on_submit=False):
            c1, c2, c3 = st.columns(3)
            code = c1.text_input("ERP Code (blank = temporary)")
            name = c2.text_input("Item Name*")
            size = c3.text_input("Size*")
            dept = c1.selectbox("Department", DEPARTMENTS)
            cat = c2.selectbox("Category", CATEGORIES)
            stock = c3.number_input("Initial Stock", min_value=0.0, step=1.0)
            price = c1.number_input("Unit Price (BDT)", min_value=0.0, step=1.0)
            serial = c2.text_input("Serial No (optional, unique per factory)")
            submitted = st.form_submit_button("Save Item")
        if submitted and guard():
            if not name.strip() or not size.strip():
                st.error("Item Name ar Size mandatory.")
            else:
                res = add_item(FAC, code, name.strip(), size.strip(), dept, cat, stock, price, serial.strip())
                if res:
                    done("Stock added to existing item (no duplicate)." if res[0] == "exists" else "New item added.")

    with st.container(border=True):
        st.markdown('<div class="section-title">Import Opening Physical Stock</div>', unsafe_allow_html=True)
        st.download_button("📄 Download import format (CSV)",
                           pd.DataFrame([{"SL No": 1, "Serial No": "KW-001", "ERP Code": "ERP-0001", "Item Name": "Example Item", "Size": "XL",
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
                         f"mirrored to other unit {st_['mirrored']}, size missing {st_['no_size']}, "
                         f"serial set {st_['serial_set']}, serial conflict (skipped) {st_['serial_conflict']}.")


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
        serial = c1.text_input("Serial No (unique per factory)", r["serial_no"] or "", key=f"e_serial_{k}")
        pw = st.text_input("🔐 Store Manager password", type="password", key=f"e_pw_{k}")
        save = st.form_submit_button("💾 Save changes")
    if save:
        if not verify_manager_password(pw):
            st.error("Manager password thik nei.")
        elif not name.strip() or not size.strip():
            st.error("Item Name ar Size mandatory.")
        elif update_item(FAC, r["sl_no"], r["prod_id"], r["item_name"], code.strip() or r["prod_id"], name.strip(),
                         size.strip(), dept, cat.strip(), erp, phys, price, unit, serial.strip()):
            done("Inventory item updated.")
    with st.expander("🗑 Delete this item (Manager)"):
        pw2 = mgr_check(f"del_pw_{k}")
        conf2 = confirm_box(f"del_conf_{k}")
        if st.button("Delete item", key=f"del_btn_{k}"):
            if not pw2:
                st.error("Manager password thik nei.")
            elif not conf2:
                st.error("Delete confirm tick korun.")
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
    export_buttons(qd, "import_queue")
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
    conf = confirm_box(f"qconf_{k}")
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
        elif not conf:
            st.error("Delete confirm tick korun.")
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
    st.markdown('<div class="section-title">Bulk check (Excel / CSV: Item Name, Size, ERP Code)</div>', unsafe_allow_html=True)
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


@tx
def bulk_set_grn_done(pairs):
    """Marks many ERP Pending items as ERP GRN Done in one transaction."""
    for fac, sl in pairs:
        run("UPDATE inventory SET erp_status='ERP GRN Done' WHERE sl_no=%s AND factory_name=%s AND erp_status='ERP Pending'",
            (sl, fac))
    audit("ERP_STATUS_DONE_BULK", f"{len(pairs)} item(s) marked ERP GRN Done: "
          + ", ".join(f"{f}/SL{sl}" for f, sl in pairs[:50]) + (" ..." if len(pairs) > 50 else ""))
    return len(pairs)


@tx
def update_task(tid, officer, prio, status, target, remarks):
    run("""UPDATE audit_correction_tasks SET assigned_officer=%s, priority=%s, status=%s, target_date=%s,
           manager_remarks=%s WHERE id=%s""", (officer, prio, status, target, remarks, tid))
    audit("EDIT_TASK", f"Correction task {tid} edited")
    return True


def audit_search(df, term):
    """Search ERP-audit rows by item, size, ERP code, serial, factory, status or exact SL No."""
    t = (term or "").strip().lower()
    if not t or df is None or df.empty:
        return df
    cols = [c for c in ("item_name", "size", "prod_id", "serial_no", "factory_name", "erp_status", "variance_type")
            if c in df.columns]
    m = df[cols].astype(str).apply(lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)
    m = m | (df["sl_no"].astype(str).str.strip() == t)
    return df[m]


# ---------- ERP PO Pending (Issue + Received) ----------
PO_FROM = "FROM transactions t LEFT JOIN inventory i ON i.sl_no=t.sl_no AND i.factory_name=t.factory_name"
# Issue / Internal Issue: the product's ERP status is still 'ERP Pending' (the status set by "Mark ERP status Done").
# Received (Supplier Receipt): the receipt's own ERP GRN status is still 'Pending' (same field Receipt Aging uses).
PO_WHERE = ("((t.trans_type IN ('Issued','Internal Issue') AND i.erp_status='ERP Pending') "
            "OR (t.trans_type='Supplier. Rec' AND t.erp_grn_status='Pending'))")


def po_pending_counts():
    fsql, fp = fw(FAC, "t.")
    r = q(f"""SELECT COALESCE(SUM(CASE WHEN t.trans_type='Supplier. Rec' THEN 0 ELSE 1 END),0) AS issue_n,
                     COALESCE(SUM(CASE WHEN t.trans_type='Supplier. Rec' THEN 1 ELSE 0 END),0) AS recv_n
              {PO_FROM} WHERE {PO_WHERE}{fsql}""", fp)[0]
    i_n, r_n = int(r["issue_n"] or 0), int(r["recv_n"] or 0)
    return {"issue": i_n, "recv": r_n, "total": i_n + r_n}


def go_erp_po_pending():
    """Button callback: open [3] ERP AUDIT on the ERP PO Pending view."""
    st.session_state[NAV_KEY] = NAV_ERP_AUDIT
    st.session_state[AUD_VIEW_KEY] = AUD_PO


def erp_po_pending_view():
    fsql, fp = fw(FAC, "t.")
    df = qdf(f"""SELECT t.id, t.factory_name, t.sl_no, COALESCE(i.serial_no,'') AS serial_no, t.item_name,
                 COALESCE(NULLIF(t.erp_code,''), t.prod_id) AS erp_code,
                 CASE WHEN t.trans_type='Supplier. Rec' THEN 'Received' ELSE 'Issue' END AS type,
                 t.qty, t.date, t.time, t.officer_name
                 {PO_FROM} WHERE {PO_WHERE}{fsql} ORDER BY t.id DESC""", fp)
    st.markdown('<div class="section-title">ERP PO Pending · Issue & Received transactions</div>', unsafe_allow_html=True)
    if df.empty:
        st.success("ERP PO Pending transaction nei.")
        return
    df["status"] = "ERP PO Pending"
    f1, f2 = st.columns([1, 3])
    tsel = f1.selectbox("Type", ["All", "Issue", "Received"], key="po_type")
    term = f2.text_input("🔍 Search (Item / Serial No / ERP Code / SL No / Officer / Factory)", key="po_search")
    view = df if tsel == "All" else df[df["type"] == tsel]
    t = term.strip().lower()
    if t and not view.empty:
        m = view[["item_name", "serial_no", "erp_code", "officer_name", "factory_name"]].fillna("").astype(str).apply(
            lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)
        view = view[m | (view["sl_no"].astype(str).str.strip() == t)]
    mc = st.columns(3)
    mc[0].metric("ERP PO Pending", len(view))
    mc[1].metric("Issue", int((view["type"] == "Issue").sum()))
    mc[2].metric("Received", int((view["type"] == "Received").sum()))
    out = view[["item_name", "serial_no", "erp_code", "type", "qty", "date", "status", "factory_name", "sl_no", "officer_name", "id"]].copy()
    out.columns = ["Item", "Serial", "ERP Code", "Type", "Qty", "Date", "Status", "Factory", "SL No", "Officer", "ID"]
    st.dataframe(out, hide_index=True, use_container_width=True, height=400)
    export_buttons(out, "erp_po_pending")


# ---------- Product Received ----------
@tx
def update_received_record(tid, name, erp_name, erp_code, erp_status, erp_sl, supplier, challan, date_s, notes, set_master):
    """Edits ONE existing supplier-receipt record (and, when asked, its product record). Never creates a product."""
    rows = q("SELECT * FROM transactions WHERE id=%s AND trans_type='Supplier. Rec'", (tid,))
    if not rows:
        st.error("Received record paoa jay nai.")
        return False
    t = rows[0]
    fac, sl = t["factory_name"], t["sl_no"]
    inv = q("SELECT prod_id, item_name, COALESCE(size,'') AS size FROM inventory WHERE sl_no=%s AND factory_name=%s", (sl, fac))
    if inv:
        cur_name, cur_code, size = inv[0]["item_name"], inv[0]["prod_id"], inv[0]["size"]
        new_code = cur_code
        if name != cur_name and any(
                norm_name(r["item_name"]) == norm_name(name) and norm_size(r["size"]) == norm_size(size)
                for r in q("SELECT item_name, COALESCE(size,'') AS size FROM inventory WHERE factory_name=%s AND sl_no<>%s", (fac, sl))):
            st.error(f"'{name}' [{size}] already exists in {fac} - duplicate product toiri kora jabe na.")
            return False
        if set_master and erp_code and erp_code != cur_code:
            if q("SELECT 1 AS x FROM inventory WHERE factory_name=%s AND prod_id=%s AND sl_no<>%s", (fac, erp_code, sl)):
                st.error(f"ERP Code '{erp_code}' already used by another product in {fac}!")
                return False
            new_code = erp_code
        if name != cur_name or new_code != cur_code:
            run("UPDATE inventory SET item_name=%s, prod_id=%s WHERE sl_no=%s AND factory_name=%s", (name, new_code, sl, fac))
            run("UPDATE transactions SET prod_id=%s, item_name=%s WHERE sl_no=%s AND factory_name=%s", (new_code, name, sl, fac))
            run("UPDATE requisition_tracking SET prod_id=%s, item_name=%s WHERE factory_name=%s AND prod_id=%s",
                (new_code, name, fac, cur_code))
    grn_date = t.get("erp_grn_date")
    if erp_status == "Done":
        grn_date = grn_date or datetime.now().strftime(DATE_FMT)
    elif erp_status == "Pending":
        grn_date = None
    run("""UPDATE transactions SET erp_product_name=%s, erp_code=%s, erp_grn_status=%s, erp_grn_date=%s, erp_sl_ref=%s,
           supplier_name=%s, challan_no=%s, date=%s, notes=%s WHERE id=%s""",
        (erp_name, erp_code, erp_status, grn_date, erp_sl, supplier, challan, date_s, notes, tid))
    audit("EDIT_RECEIVED", f"Received record {tid} ({name}): ERP name '{erp_name}', ERP code '{erp_code}', status {erp_status}, "
                           f"supplier '{supplier}', challan '{challan}'")
    return True


def erp_product_received_view():
    fsql, fp = fw(FAC, "t.")
    rc = qdf(f"""SELECT t.id, t.date, t.time, t.factory_name, t.item_name, COALESCE(t.erp_product_name,'') AS erp_product_name,
                 COALESCE(i.serial_no,'') AS serial_no, t.sl_no, t.prod_id,
                 COALESCE(NULLIF(t.erp_code,''), t.prod_id) AS erp_code, COALESCE(t.erp_sl_ref,'') AS erp_sl_ref,
                 t.qty, COALESCE(t.supplier_name,'') AS supplier_name, COALESCE(t.challan_no,'') AS challan_no,
                 COALESCE(t.erp_grn_status,'') AS erp_status, t.officer_name, COALESCE(t.notes,'') AS notes
                 FROM transactions t LEFT JOIN inventory i ON i.sl_no=t.sl_no AND i.factory_name=t.factory_name
                 WHERE t.trans_type='Supplier. Rec'{fsql} ORDER BY t.id DESC""", fp)
    st.markdown('<div class="section-title">Product Received · ERP & receiving history</div>', unsafe_allow_html=True)
    if rc.empty:
        st.info("Supplier receipt record nei. [1] TRANSACTIONS-e 'Supplier Receipt' diye product receive korun.")
        return
    rc["qty"] = rc["qty"].astype(float)
    rc["_dt"] = pd.to_datetime(rc["date"].apply(parse_date), errors="coerce")
    month_names = list(calendar.month_name)[1:]
    years = sorted({int(y) for y in rc["_dt"].dt.year.dropna()}, reverse=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns([3, 1, 1])
        term = f1.text_input("🔍 Search product (Name / Serial No / ERP Code / SL No / Supplier / Challan)", key="pr_search",
                             placeholder="e.g. Spherical Roller Bearing, KW-001, ERP code, SL number ...")
        mon = f2.selectbox("Month", ["All"] + month_names, key="pr_month")
        yr = f3.selectbox("Year", ["All"] + [str(y) for y in years], key="pr_year")

    view = rc
    t = term.strip().lower()
    if t:
        scols = ["item_name", "erp_product_name", "serial_no", "prod_id", "erp_code", "erp_sl_ref", "supplier_name",
                 "challan_no", "factory_name"]
        m = view[scols].fillna("").astype(str).apply(lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)
        view = view[m | (view["sl_no"].astype(str).str.strip() == t)]
    if mon != "All":
        view = view[view["_dt"].dt.month == month_names.index(mon) + 1]
    if yr != "All":
        view = view[view["_dt"].dt.year == int(yr)]
    chrono = mon != "All" or yr != "All"
    view = view.sort_values(["_dt", "id"], ascending=chrono, na_position="last")

    total_qty = float(view["qty"].sum()) if not view.empty else 0.0
    mc = st.columns(3)
    mc[0].metric("Total Received (Qty)", f"{total_qty:g}")
    mc[1].metric("Times Received (entries)", len(view))
    mc[2].metric("Distinct Products", view[["factory_name", "sl_no"]].drop_duplicates().shape[0] if not view.empty else 0)
    period = " ".join(x for x in (mon if mon != "All" else "", yr if yr != "All" else "") if x)
    if period or t:
        what = f"'{term.strip()}'" if t else "All products"
        st.caption(f"{what}{' · ' + period if period else ''}: received {len(view)} time(s), Total Received {total_qty:g}.")
    if view.empty:
        st.info("Ei filter-e kono received record nei.")
        return

    d1, d2 = st.tabs(["📋 Receiving History (date-wise)", "📦 Product-wise Summary"])
    with d1:
        out = view[["id", "date", "item_name", "serial_no", "sl_no", "erp_code", "qty", "factory_name", "supplier_name",
                    "challan_no", "erp_status", "officer_name", "erp_product_name", "erp_sl_ref", "notes"]].copy()
        out.columns = ["ID", "Date", "Item Name", "Serial No", "SL No", "ERP Code", "Qty", "Factory", "Supplier",
                       "Challan No", "ERP Status", "Officer", "ERP Product Name", "ERP SL / ID", "Remarks"]
        st.dataframe(out, hide_index=True, use_container_width=True, height=380)
        export_buttons(out, "product_received")
    with d2:
        g = (view.groupby(["factory_name", "item_name", "serial_no", "erp_code"], as_index=False)
             .agg(times=("id", "count"), qty=("qty", "sum"), first=("_dt", "min"), last=("_dt", "max"))
             .sort_values("qty", ascending=False))
        g["first"] = g["first"].dt.strftime(DATE_FMT).fillna("")
        g["last"] = g["last"].dt.strftime(DATE_FMT).fillna("")
        g.columns = ["Factory", "Item Name", "Serial No", "ERP Code", "Times Received", "Total Qty Received",
                     "First Received", "Last Received"]
        st.dataframe(g, hide_index=True, use_container_width=True)
        export_buttons(g, "product_received_summary")

    with st.expander("🔐 Manager: Edit / Delete a received product"):
        if not guard(write=False):
            return
        rows = {int(r["id"]): r for r in view.head(500).to_dict("records")}
        tid = int(st.selectbox(
            "Received record", list(rows), key="pr_id",
            format_func=lambda i: (f"ID {i} | {rows[i]['date']} | {rows[i]['item_name']} | qty {float(rows[i]['qty']):g} | "
                                   f"{rows[i]['supplier_name'] or '-'} | {rows[i]['challan_no'] or '-'}")))
        r = rows[tid]
        pw_ok = mgr_check("pr_mgr_pw")
        st.markdown("**✏️ Edit** (same product / same receipt record - no duplicate is created)")
        e1, e2 = st.columns(2)
        e_name = e1.text_input("Product Name", value=str(r["item_name"] or ""), key=f"pr_e_name_{tid}")
        e_erpn = e2.text_input("ERP Product Name", value=str(r["erp_product_name"] or ""), key=f"pr_e_erpn_{tid}")
        e_code = e1.text_input("ERP Code", value=str(r["erp_code"] or ""), key=f"pr_e_code_{tid}")
        statuses = ["Pending", "Done", "Not Required"]
        if r["erp_status"] and r["erp_status"] not in statuses:
            statuses.append(r["erp_status"])
        e_stat = e2.selectbox("ERP Status", statuses, index=statuses.index(r["erp_status"]) if r["erp_status"] in statuses else 0,
                              key=f"pr_e_stat_{tid}")
        e_sl = e1.text_input("ERP SL / Identifier", value=str(r["erp_sl_ref"] or ""), key=f"pr_e_sl_{tid}")
        e_sup = e2.text_input("Supplier", value=str(r["supplier_name"] or ""), key=f"pr_e_sup_{tid}")
        e_ch = e1.text_input("Challan Number", value=str(r["challan_no"] or ""), key=f"pr_e_ch_{tid}")
        cur_d = parse_date(r["date"])
        e_date = e2.date_input("Receiving date", value=cur_d.date() if cur_d else date.today(), key=f"pr_e_date_{tid}")
        e_notes = st.text_input("Remarks", value=str(r["notes"] or ""), key=f"pr_e_notes_{tid}")
        e_master = st.checkbox("Also set this ERP Code as the product's master ERP code (renames it in inventory & history)",
                               key=f"pr_e_master_{tid}")
        if st.button("💾 Save changes", type="primary", key="pr_save"):
            if not pw_ok:
                st.error("Manager password thik nei.")
            elif not e_name.strip():
                st.error("Product Name khali rakha jabe na.")
            elif update_received_record(tid, e_name.strip(), e_erpn.strip(), e_code.strip(), e_stat, e_sl.strip(),
                                        e_sup.strip(), e_ch.strip(), e_date.strftime(DATE_FMT), e_notes.strip(), e_master):
                done("Received record updated.")
        st.markdown("**🗑 Delete**")
        conf = confirm_box(f"pr_del_conf_{tid}",
                           f"⚠️ Ami confirm korchi - ei received record delete hobe ar stock {float(r['qty']):g} kome jabe.")
        if st.button("🗑 Delete received record", key="pr_del"):
            if not pw_ok:
                st.error("Manager password thik nei.")
            elif not conf:
                st.error("Delete confirm tick korun.")
            elif delete_transaction(tid):
                done("Received record deleted, stock reverted.")


def tab_erp_audit():
    aud = qdf(f"""SELECT factory_name, sl_no, COALESCE(serial_no,'') AS serial_no, prod_id, item_name,
                  COALESCE(size,'') AS size,
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

    # ---- search bar (filters every list below: tables, adjust, ERP-done selection)
    if st.session_state.get(AUD_VIEW_KEY) not in AUD_VIEWS:
        st.session_state[AUD_VIEW_KEY] = AUD_VIEWS[0]
    if st.session_state[AUD_VIEW_KEY] in (AUD_PO, AUD_RECV):
        term = ""   # these two views carry their own search bar
    else:
        term = st.text_input("🔍 Search ERP audit records (Item / Serial No / ERP Code / SL No / Factory / Status)",
                             key="aud_search", placeholder="e.g. Spherical Roller Bearing, KW-001, ERP code, SL number ...")
    view = audit_search(aud, term)
    if not aud.empty:
        v_short, v_exc = view[view.variance < 0], view[view.variance > 0]
        v_match, v_pend = view[view.variance == 0], view[view.erp_status == "ERP Pending"]
        vt = view[view.variance != 0]
        if term.strip():
            st.caption(f"Showing {len(view)} of {len(aud)} records")
    else:
        v_short = v_exc = v_match = v_pend = vt = view

    aud_sel = st.radio("ERP Audit view", AUD_VIEWS, key=AUD_VIEW_KEY, horizontal=True, label_visibility="collapsed")
    cols = ["factory_name", "sl_no", "serial_no", "prod_id", "item_name", "size", "erp_stock", "current_stock", "variance",
            "unit_price", "short_value", "excess_value", "erp_status", "variance_type"]
    if aud_sel == AUD_ACT:
        if guard():
            a1, a2, a3, a4 = st.tabs(["📥 Import ERP Balance", "⚖️ Adjust variance to ERP (Manager)",
                                      "📋 Assign Correction Task", "✔️ Mark ERP status Done"])
            with a1:
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

            with a2:
                st.markdown("**⚖️ Adjust variance to ERP** (Manager)")
                st.caption("Physical stock-ke ERP balance-er sathe milano hoy. Upore search bar diye item khunje nin.")
                if vt.empty:
                    st.success("Sob item ERP-er sathe matched." if not term.strip() else "Search-e kono variance item nei.")
                else:
                    labels = {f"SL {r['sl_no']} | {r['item_name']} [{r['size'] or '-'}] | S/N {r['serial_no'] or '-'} | "
                              f"{r['factory_name']} | Var {r['variance']:g}": r for r in vt.to_dict("records")}
                    row = labels[st.selectbox("Item", list(labels), key="adj_sel")]
                    limit = abs(float(row["variance"]))
                    aq = st.number_input("Adjust qty", min_value=0.0, max_value=limit, value=limit, key="adj_qty")
                    pw = mgr_check("adj_pw")
                    if st.button("⚖️ Adjust", key="adj_btn", type="primary"):
                        if not pw:
                            st.error("Manager password thik nei.")
                        elif aq <= 0:
                            st.error("Qty 0 er beshi hote hobe.")
                        elif adjust_variance(row, aq):
                            done("Variance adjusted.")

            with a3:
                st.markdown("**📋 Assign correction task**")
                if vt.empty:
                    st.caption("Variance item nei.")
                else:
                    labels2 = {f"SL {r['sl_no']} | {r['item_name']} [{r['prod_id']}] | {r['factory_name']}": r
                               for r in vt.to_dict("records")}
                    row2 = labels2[st.selectbox("Item for task", list(labels2), key="task_item")]
                    c1, c2, c3 = st.columns(3)
                    officer = c1.selectbox("Officer", ["Officer_Sagor", "Officer_Rahim", "Manager Admin"], key="task_off")
                    days = c2.selectbox("Deadline", [1, 2, 3, 7, 15], index=1, format_func=lambda d: f"{d} day(s)", key="task_days")
                    prio = c3.selectbox("Priority", ["Critical", "High", "Medium", "Low"], index=1, key="task_prio")
                    rem = st.text_input("Root cause / remarks", "Physical recount and verification required", key="task_rem")
                    if st.button("Assign task", key="task_btn"):
                        if assign_task(row2["factory_name"], row2, officer, days, prio, rem):
                            done("Correction task assigned.")

            with a4:
                st.markdown("**✔️ Mark ERP status Done** (ERP Pending items)")
                if v_pend.empty:
                    st.caption("ERP Pending item nei." if not term.strip() else "Search-e kono ERP Pending item nei.")
                else:
                    st.caption("Row-er Select tick din (ek ba ekadhik), tarpor 'Mark Selected as ERP Done' click korun. "
                               "Search bar diye list choto korte paren.")
                    sel_all = st.checkbox(f"Select all {len(v_pend)} shown item(s)", key="erp_sel_all")
                    ed = v_pend[["factory_name", "sl_no", "serial_no", "prod_id", "item_name", "size",
                                 "erp_stock", "current_stock"]].copy()
                    ed.insert(0, "Select", bool(sel_all))
                    tag = hashlib.md5(term.strip().lower().encode()).hexdigest()[:6]
                    edited = st.data_editor(
                        ed, hide_index=True, use_container_width=True, height=360,
                        disabled=[c_ for c_ in ed.columns if c_ != "Select"],
                        column_config={"Select": st.column_config.CheckboxColumn("Select", default=False)},
                        key=f"erp_done_ed_{int(sel_all)}_{len(ed)}_{tag}")
                    chosen = edited[edited["Select"]]
                    st.caption(f"Selected: {len(chosen)} of {len(ed)}")
                    conf = st.checkbox(f"✔ Ami confirm korchi: {len(chosen)} ta selected item ERP GRN Done hobe.",
                                       key=f"erp_done_conf_{len(chosen)}")
                    if st.button(f"✔️ Mark Selected as ERP Done ({len(chosen)})", type="primary",
                                 disabled=chosen.empty, key="erp_done_btn"):
                        if not conf:
                            st.error("Age confirm tick din.")
                        else:
                            pairs = [(r.factory_name, int(r.sl_no)) for r in chosen.itertuples()]
                            if bulk_set_grn_done(pairs):
                                done(f"{len(pairs)} item ERP GRN Done kora hoyeche.")

    if aud_sel == AUD_ALL:
        st.dataframe(view[cols] if not view.empty else view, hide_index=True, use_container_width=True, height=420)
        export_buttons(view[cols] if not view.empty else view, "erp_audit_all")
    if aud_sel == AUD_SHORT:
        st.dataframe(v_short[cols] if not v_short.empty else v_short, hide_index=True, use_container_width=True)
        export_buttons(v_short[cols] if not v_short.empty else v_short, "erp_audit_short")
    if aud_sel == AUD_EXC:
        st.dataframe(v_exc[cols] if not v_exc.empty else v_exc, hide_index=True, use_container_width=True)
        export_buttons(v_exc[cols] if not v_exc.empty else v_exc, "erp_audit_excess")
    if aud_sel == AUD_MATCH:
        st.dataframe(v_match[cols] if not v_match.empty else v_match, hide_index=True, use_container_width=True)
        export_buttons(v_match[cols] if not v_match.empty else v_match, "erp_audit_matched")
    if aud_sel == AUD_PEND:
        st.dataframe(v_pend[cols] if not v_pend.empty else v_pend, hide_index=True, use_container_width=True)
        export_buttons(v_pend[cols] if not v_pend.empty else v_pend, "erp_audit_pending")
    if aud_sel == AUD_PO:
        erp_po_pending_view()
    if aud_sel == AUD_RECV:
        erp_product_received_view()
    if aud_sel == AUD_PLAN:
        if tasks.empty:
            st.info("Correction task nei.")
        else:
            st.dataframe(tasks, hide_index=True, use_container_width=True)
            export_buttons(tasks, "correction_tasks")
            if guard():
                tid = int(st.selectbox("Task ID", tasks["id"].tolist(), key="task_id_sel"))
                trow = tasks[tasks["id"] == tid].iloc[0]
                pw = mgr_check("task_pw")
                conf = confirm_box(f"task_conf_{tid}")
                c1, c2 = st.columns(2)
                if c1.button("✅ Verify & Close", key="task_close"):
                    if not pw:
                        st.error("Manager password din.")
                    elif close_task(tid):
                        done("Task closed.")
                if c2.button("🗑 Delete task", key="task_del"):
                    if not pw:
                        st.error("Manager password din.")
                    elif not conf:
                        st.error("Delete confirm tick korun.")
                    elif delete_task(tid):
                        done("Task deleted.")
                with st.expander("✏️ Edit task"):
                    officers = ["Officer_Sagor", "Officer_Rahim", "Manager Admin"]
                    cur_off = str(trow["assigned_officer"] or "")
                    if cur_off and cur_off not in officers:
                        officers.append(cur_off)
                    prios = ["Critical", "High", "Medium", "Low"]
                    stats = ["Open", "In Progress", "On Hold", "Closed"]
                    with st.form(f"task_edit_{tid}"):
                        e1, e2, e3 = st.columns(3)
                        eo = e1.selectbox("Officer", officers, index=officers.index(cur_off) if cur_off in officers else 0)
                        ep_ = e2.selectbox("Priority", prios, index=prios.index(trow["priority"]) if trow["priority"] in prios else 2)
                        es = e3.selectbox("Status", stats, index=stats.index(trow["status"]) if trow["status"] in stats else 1)
                        et = e1.text_input("Target date (DD-Mon-YYYY)", str(trow["target_date"] or ""))
                        er = e2.text_input("Remarks", str(trow["manager_remarks"] or ""))
                        epw = st.text_input("🔐 Store Manager password", type="password")
                        go = st.form_submit_button("💾 Save task changes")
                    if go:
                        if not verify_manager_password(epw):
                            st.error("Manager password thik nei.")
                        elif not parse_date(et):
                            st.error("Target date DD-Mon-YYYY format-e din.")
                        elif update_task(tid, eo, ep_, es, et, er.strip()):
                            done("Task updated.")
    if aud_sel == AUD_AGE:
        rc = qdf(f"""SELECT id, factory_name, date, item_name, prod_id, qty, officer_name FROM transactions
                     WHERE trans_type='Supplier. Rec' AND erp_grn_status='Pending'{FSQL} ORDER BY id DESC""", FP)
        if rc.empty:
            st.success("ERP-e wait korche emon receipt nei.")
        else:
            rc["days_pending"] = rc.date.apply(lambda d: age_days(d) or 0)
            st.caption(f"Receipts waiting for ERP: {len(rc)} | Over 7 days: {int((rc.days_pending > PO_ALERT_DAYS).sum())}")
            st.dataframe(rc, hide_index=True, use_container_width=True)
            export_buttons(rc, "receipt_aging")
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
    iss = qdf(f"""SELECT t.id, t.date, t.time, t.factory_name, t.item_name, COALESCE(i.size,'') AS size,
                  COALESCE(i.serial_no,'') AS serial_no, t.prod_id, t.sl_no, t.qty,
                  COALESCE(i.unit_price,0) AS unit_price, t.officer_name, t.trans_type, t.notes, t.verification_status
                  FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                  WHERE t.trans_type IN ('Issued','Internal Issue'){fw(FAC, 't.')[0]} ORDER BY t.id DESC""", FP)
    if not iss.empty:
        iss["total_value"] = iss.qty * iss.unit_price
        iss["type"] = iss.trans_type.map(lambda c: TRANS_LABELS.get(c, c))
        iss["erp_status"] = iss.notes.fillna("").apply(lambda n: "ERP PO Pending" if "Pending" in n else "ERP GRN Completed")
        iss["_dt"] = pd.to_datetime(iss["date"].apply(parse_date), errors="coerce")

    st.markdown('<div class="section-title">Search & Filter Issues</div>', unsafe_allow_html=True)
    if iss.empty:
        st.info("Issue record nei.")
        st.dataframe(iss, hide_index=True, use_container_width=True)
        return

    month_names = list(calendar.month_name)[1:]
    years = sorted({int(y) for y in iss["_dt"].dt.year.dropna()}, reverse=True)
    with st.container(border=True):
        f1, f2, f3 = st.columns([3, 1, 1])
        term = f1.text_input("🔍 Search (Item Name / Serial No / ERP Code / SL No / Officer / Factory)", key="il_search",
                             placeholder="e.g. Spherical Roller Bearing, KW-001 ...")
        mon = f2.selectbox("Month", ["All"] + month_names, key="il_month")
        yr = f3.selectbox("Year", ["All"] + [str(y) for y in years], key="il_year")
        use_rng = st.checkbox("Use exact date range (From - To)", key="il_use_rng")
        d_from = d_to = None
        if use_rng:
            r1, r2 = st.columns(2)
            d_from = r1.date_input("From", value=date.today().replace(day=1), key="il_from")
            d_to = r2.date_input("To", value=date.today(), key="il_to")

    view = iss
    t = term.strip().lower()
    if t:
        scols = ["item_name", "serial_no", "prod_id", "size", "officer_name", "factory_name", "notes"]
        m = view[scols].fillna("").astype(str).apply(lambda c: c.str.lower().str.contains(t, regex=False)).any(axis=1)
        view = view[m | (view["sl_no"].astype(str).str.strip() == t)]
    if mon != "All":
        view = view[view["_dt"].dt.month == month_names.index(mon) + 1]
    if yr != "All":
        view = view[view["_dt"].dt.year == int(yr)]
    if use_rng:
        if d_from > d_to:
            st.error("'From' date 'To' date-er age hote hobe.")
        else:
            view = view[(view["_dt"] >= pd.Timestamp(d_from)) & (view["_dt"] < pd.Timestamp(d_to) + pd.Timedelta(days=1))]

    mc = st.columns(4)
    mc[0].metric("Total Issued Qty", f"{view.qty.sum():g}")
    mc[1].metric("Issue Entries", len(view))
    mc[2].metric("Distinct Items", view[["factory_name", "sl_no"]].drop_duplicates().shape[0])
    mc[3].metric("Issued Value (৳)", f"{view.total_value.sum():,.0f}")
    if view.empty:
        st.info("Ei filter-e kono issue record nei.")
        return

    d1, d2, d3 = st.tabs(["📋 Issue Details", "📅 Date-wise Summary", "📦 Item-wise Summary"])
    with d1:
        detail = view.sort_values(["_dt", "id"], ascending=False)[
            ["id", "date", "time", "factory_name", "serial_no", "prod_id", "sl_no", "item_name", "size", "qty", "unit_price",
             "total_value", "officer_name", "type", "verification_status", "erp_status", "notes"]]
        st.dataframe(detail, hide_index=True, use_container_width=True, height=380)
        export_buttons(detail, "issue_ledger")
    with d2:
        dd = view[view["_dt"].notna()]
        if dd.empty:
            st.info("Valid date record nei.")
        else:
            day = dd["_dt"].dt.normalize()
            daily = dd.groupby(day).agg(entries=("id", "count"), qty=("qty", "sum"), value=("total_value", "sum")).reset_index()
            daily["Date"] = daily["_dt"].dt.strftime(DATE_FMT)
            daily = daily[["Date", "entries", "qty", "value"]]
            daily.columns = ["Date", "Issue Entries", "Qty Issued", "Value (৳)"]
            st.markdown("**Date-wise total issued**")
            st.dataframe(daily, hide_index=True, use_container_width=True)
            export_buttons(daily, "issue_datewise_summary")
            st.markdown("**Date × Item × Factory**")
            grp = dd.groupby([day, "item_name", "factory_name"], as_index=False).qty.sum()
            grp["Date"] = grp["_dt"].dt.strftime(DATE_FMT)
            grp = grp[["Date", "item_name", "factory_name", "qty"]]
            grp.columns = ["Date", "Item Name", "Factory", "Qty Issued"]
            st.dataframe(grp, hide_index=True, use_container_width=True)
            export_buttons(grp, "issue_date_item_factory")
    with d3:
        items = (view.groupby(["factory_name", "item_name", "size", "serial_no", "prod_id"], as_index=False)
                 .agg(entries=("id", "count"), qty=("qty", "sum"), value=("total_value", "sum"))
                 .sort_values("qty", ascending=False))
        items.columns = ["Factory", "Item Name", "Size", "Serial No", "ERP Code", "Issue Entries", "Qty Issued", "Value (৳)"]
        st.dataframe(items, hide_index=True, use_container_width=True)
        export_buttons(items, "issue_item_summary")
    tx_manager_panel(view[["id", "item_name", "qty", "date"]], "il", "🔐 Manager: Delete / Edit an issue entry")


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
    st.dataframe(view, hide_index=True, use_container_width=True, height=380)
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
            conf = confirm_box("tf_conf")
            c1, c2 = st.columns(2)
            if c1.button("🗑 Delete transfer", key="tf_del"):
                if not pw:
                    st.error("Manager password din.")
                elif not conf:
                    st.error("Delete confirm tick korun.")
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
        color = ("#DCFCE7" if row["Status"] == "Fully Received" else
                 "#FFF4E6" if row["Status"] == "Partially Received" else
                 "#FEE2E2" if late else "")
        return [f"background-color:{color}" if color else "" for _ in row]

    st.dataframe(df.style.apply(hl, axis=1), hide_index=True, use_container_width=True, height=380)
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
            conf = confirm_box(f"req_conf_{k}")
            if st.button("🗑 Delete requisition", key=f"req_del_{k}"):
                if not pw:
                    st.error("Manager password din.")
                elif not conf:
                    st.error("Delete confirm tick korun.")
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
    st.dataframe(rp, hide_index=True, use_container_width=True, height=380)
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
            rpw = mgr_check(f"rpw_{k}")
            rconf = confirm_box(f"rconf_{k}")
            if st.button("🗑 Delete record", key=f"rdel_{k}"):
                if not rpw:
                    st.error("Manager password thik nei.")
                elif not rconf:
                    st.error("Delete confirm tick korun.")
                elif delete_repair(r["id"]):
                    done("Record deleted.")


# ============================================================
#  TAB 8 - LEDGER
# ============================================================
def tab_ledger():
    led = qdf(f"""SELECT t.id, t.factory_name, t.officer_name, t.sl_no, COALESCE(i.serial_no,'') AS serial_no, t.prod_id,
                  t.item_name, t.qty, t.trans_type, t.notes, COALESCE(t.supplier_name,'') AS supplier_name,
                  COALESCE(t.challan_no,'') AS challan_no,
                  t.date, t.time, COALESCE(i.unit_price,0) AS unit_price
                  FROM transactions t LEFT JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                  WHERE 1=1{fw(FAC, 't.')[0]} ORDER BY t.id DESC""", FP)
    term = st.text_input("🔍 Search ledger (Item / Serial / ERP / SL / Officer)", key="led_search")
    if not led.empty and term.strip():
        tl = term.strip().lower()
        scols = ["item_name", "serial_no", "prod_id", "officer_name", "factory_name"]
        m = led[scols].fillna("").astype(str).apply(lambda c: c.str.lower().str.contains(tl, regex=False)).any(axis=1)
        led = led[m | (led["sl_no"].astype(str).str.strip() == tl)]
    manage = led[["id", "item_name", "qty", "date"]].copy() if not led.empty else led
    if not led.empty:
        led["type"] = led.trans_type.map(lambda c: TRANS_LABELS.get(c, c))
        led["total_price"] = (led.qty * led.unit_price).round(2)
        led["date_time"] = led[["date", "time"]].fillna("").agg(" ".join, axis=1)
        led = led[["id", "factory_name", "officer_name", "sl_no", "serial_no", "prod_id", "item_name", "qty", "type",
                   "supplier_name", "challan_no", "total_price", "notes", "date_time"]]
    st.dataframe(led, hide_index=True, use_container_width=True, height=440)
    export_buttons(led, "ledger")
    tx_manager_panel(manage, "led")


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
    st.markdown(f'<div class="section-title">Production Plan · Current {mi["cur_label"]} · Next {mi["next_label"]}</div>',
                unsafe_allow_html=True)
    plans = {(p["factory_name"], p["plan_month"]): p for p in q("SELECT * FROM production_plans")}
    if FAC and "CONSOLIDATED" not in FAC:
        cp = plans.get((FAC, mi["cur_key"]), {})
        npn = plans.get((FAC, mi["next_key"]), {})
        with st.container(border=True):
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
    st.dataframe(fc, hide_index=True, use_container_width=True, height=420)
    export_buttons(fc, "forecast")
    st.caption("Formula: Avg Daily = Last 3M consumption ÷ days  |  Projected = Avg Daily × days in next month × Factor  |  "
               "Net Requisition = Projected − Stock (rounded up)  |  Est. Cost = Net × Unit Price")


# ============================================================
#  TAB 10 - BUDGET (metric cards + category cards)
# ============================================================
@tx
def update_budget(bid, amount, dept):
    run("UPDATE category_budgets SET allocated_budget=%s, department_name=%s WHERE id=%s", (amount, dept, bid))
    audit("EDIT_BUDGET", f"Budget line {bid}: allocated {amount:,.0f}, dept {dept}")
    return True


@tx
def delete_budget(bid, label):
    run("DELETE FROM category_budgets WHERE id=%s", (bid,))
    audit("DELETE_BUDGET", f"Deleted budget line {bid}: {label}")
    return True


@tx
def add_budget(fac, dept, cat, amount):
    if q("SELECT 1 AS x FROM category_budgets WHERE factory_name=%s AND category_name=%s", (fac, cat)):
        st.error(f"{fac} / {cat} budget line already ache - edit korun.")
        return False
    run("INSERT INTO category_budgets (factory_name, department_name, category_name, allocated_budget) VALUES (%s,%s,%s,%s)",
        (fac, dept, cat, amount))
    audit("ADD_BUDGET", f"{fac} / {dept} / {cat}: {amount:,.0f}")
    return True


def budget_manage_panel():
    brows = q(f"""SELECT id, factory_name, department_name, category_name, allocated_budget FROM category_budgets
                  WHERE 1=1{FSQL} ORDER BY factory_name, department_name, category_name""", FP)
    with st.expander("🔐 Manager: Edit / Add / Delete budget lines"):
        if not guard():
            return
        pw_ok = mgr_check("bud_pw")
        if brows:
            labels = {f"{r['factory_name']} | {r['department_name']} | {r['category_name']} "
                      f"(৳ {float(r['allocated_budget'] or 0):,.0f})": r for r in brows}
            r = labels[st.selectbox("Budget line", list(labels), key="bud_sel")]
            k = str(r["id"])
            amt = st.number_input("Allocated budget (৳)", min_value=0.0, step=100.0,
                                  value=float(r["allocated_budget"] or 0), key=f"bud_amt_{k}")
            dept = st.selectbox("Department", DEPARTMENTS,
                                index=DEPARTMENTS.index(r["department_name"]) if r["department_name"] in DEPARTMENTS else 0,
                                key=f"bud_dept_{k}")
            conf = confirm_box(f"bud_conf_{k}")
            c1, c2 = st.columns(2)
            if c1.button("💾 Save budget line", key=f"bud_save_{k}"):
                if not pw_ok:
                    st.error("Manager password thik nei.")
                elif update_budget(r["id"], amt, dept):
                    done("Budget line updated.")
            if c2.button("🗑 Delete budget line", key=f"bud_del_{k}"):
                if not pw_ok:
                    st.error("Manager password thik nei.")
                elif not conf:
                    st.error("Delete confirm tick korun.")
                elif delete_budget(r["id"], f"{r['factory_name']} / {r['category_name']}"):
                    done("Budget line deleted.")
        st.markdown("**➕ Add budget line** (current factory)")
        a1, a2, a3 = st.columns(3)
        n_dept = a1.selectbox("Department", DEPARTMENTS, key="bud_n_dept")
        n_cat = a2.selectbox("Category", CATEGORIES, key="bud_n_cat")
        n_amt = a3.number_input("Allocated (৳)", min_value=0.0, step=100.0, key="bud_n_amt")
        if st.button("➕ Add budget line", key="bud_add"):
            if not pw_ok:
                st.error("Manager password thik nei.")
            elif add_budget(FAC, n_dept, n_cat, n_amt):
                done("Budget line added.")


def tab_budget():
    bud = qdf(f"SELECT factory_name, department_name, category_name, allocated_budget FROM category_budgets WHERE 1=1{FSQL}", FP)
    cost_rows = q(f"""SELECT t.factory_name, i.category, SUM(t.qty*i.unit_price) AS cost
                      FROM transactions t JOIN inventory i ON t.sl_no=i.sl_no AND t.factory_name=i.factory_name
                      WHERE t.trans_type IN ('Issued','Internal Issue'){fw(FAC, 't.')[0]}
                      GROUP BY t.factory_name, i.category""", FP)
    cost = {(r["factory_name"], r["category"]): float(r["cost"] or 0) for r in cost_rows}
    # Executive Overview & Budget Control lives here (not on the daily-entry home screen)
    try:
        tab_dashboard()
    except Exception as e:
        st.warning(f"Overview load kora jacche na: {e}")
    if bud.empty:
        st.info("Budget nei.")
        return
    bud["actual_cost"] = [cost.get((f, c), 0.0) for f, c in zip(bud.factory_name, bud.category_name)]
    bud["remaining"] = bud.allocated_budget - bud.actual_cost
    bud["status"] = bud.remaining.apply(lambda v: "SAFE" if v >= 0 else "OVER BUDGET")

    st.markdown('<div class="section-title">Category Budget Cards</div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="medium")
    for i, r in enumerate(bud.to_dict("records")):
        b, c_ = float(r["allocated_budget"] or 0), float(r["actual_cost"] or 0)
        pct = (c_ / b * 100) if b > 0 else (100.0 if c_ > 0 else 0.0)
        rem = b - c_
        status_color = "#16A34A" if rem >= 0 else "#DC2626"
        card = (f'<div class="fin-card">'
                f'<div class="cat-factory">{html_lib.escape(str(r["factory_name"]))} · {html_lib.escape(str(r["department_name"]))}</div>'
                f'<div class="cat-name">{html_lib.escape(str(r["category_name"]))}</div>'
                f'<div class="cat-nums"><span>Budget ৳ {b:,.0f}</span><span>Used ৳ {c_:,.0f}</span></div>'
                f'{budget_bar_html(pct, "Consumption")}'
                f'<div class="cat-foot">Remaining ৳ {rem:,.0f} · <span style="color:{status_color};font-weight:800">'
                f'{"SAFE" if rem >= 0 else "OVER BUDGET"}</span></div></div>')
        with cols[i % 3]:
            st.markdown(card, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Budget Detail Table</div>', unsafe_allow_html=True)
    st.dataframe(bud, hide_index=True, use_container_width=True, column_config={
        "allocated_budget": st.column_config.NumberColumn("Allocated (৳)", format="%.0f"),
        "actual_cost": st.column_config.NumberColumn("Actual Cost (৳)", format="%.0f"),
        "remaining": st.column_config.NumberColumn("Remaining (৳)", format="%.0f"),
    })
    export_buttons(bud, "budget")
    budget_manage_panel()


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
    if st.session_state.get("_uom_checked"):
        return
    if q("SELECT 1 AS x FROM req_settings WHERE setting_key='uom_autoset_v1' AND setting_value='done'"):
        st.session_state["_uom_checked"] = True
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
    if _do():
        st.session_state["_uom_checked"] = True


def daily_rows(d, fac, show_all):
    ds = d.strftime(DATE_FMT)
    rows = q("""SELECT i.sl_no, COALESCE(i.serial_no,'') AS serial, i.item_name, COALESCE(i.size,'') AS size,
                COALESCE(NULLIF(i.unit_name,''),'Pcs') AS unit,
                COALESCE(i.current_stock,0) AS cur, COALESCE(i.erp_stock,0) AS erp,
                COALESCE(d.issue,0) AS issue, COALESCE(d.recv,0) AS recv
                FROM inventory i
                LEFT JOIN (SELECT sl_no,
                                  SUM(CASE WHEN trans_type IN ('Issued','Internal Issue') THEN qty ELSE 0 END) AS issue,
                                  SUM(CASE WHEN trans_type IN ('Supplier. Rec','Internal Rec') THEN qty ELSE 0 END) AS recv
                           FROM transactions WHERE factory_name=%s AND date=%s GROUP BY sl_no) d ON d.sl_no=i.sl_no
                WHERE i.factory_name=%s ORDER BY i.sl_no""", (fac, ds, fac))
    out = []
    for r in rows:
        cur, erp = float(r["cur"]), float(r["erp"])
        diff = round(cur - erp, 4)
        short, exc = (abs(diff) if diff < 0 else 0.0), (diff if diff > 0 else 0.0)
        if not show_all and abs(cur) < 1e-9 and short == 0 and exc == 0 and float(r["issue"]) <= 0 and float(r["recv"]) <= 0:
            continue
        out.append({"SL No.": r["sl_no"], "Serial No": r["serial"], "Item Name": r["item_name"], "Size": r["size"], "Unit": r["unit"],
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
                 f"<td>{esc(str(r['Serial No'] or '-'))}</td>"
                 f"<td style='text-align:left'>{esc(str(r['Item Name']))}</td>"
                 f"<td>{esc(str(r['Size'] or '-'))}</td><td>{esc(str(r['Unit']))}</td>"
                 f"<td>{r['Current Stock']:g}</td><td>{issue_txt}</td><td>{recv_txt}</td>"
                 f"<td>{r['Short Qty']:g}</td><td>{r['Excess Qty']:g}</td></tr>")
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Daily Work Sheet</title>
<style>@page {{ size: A4 portrait; margin: 10mm; }} body {{ font-family: Arial; font-size: 11px; }}
h2 {{ text-align:center; color:#C2410C; margin:0; }} p {{ text-align:center; margin:4px 0 10px; }}
table {{ width:100%; border-collapse:collapse; }}
th {{ background:#E8590C; color:#fff; padding:4px; border:1px solid #333; }}
td {{ border:1px solid #333; padding:3px 4px; text-align:center; }}
tr.short td {{ background:#fde8e8; }} tr.excess td {{ background:#fff3e0; }}</style></head><body>
<h2>Daily Issue Status For Month: {d.strftime('%B-%Y')}</h2>
<p><b>Date:</b> {d.strftime(DATE_FMT)} &nbsp; <b>Factory Name:</b> {esc(fac)}</p>
<table><thead><tr><th>SL No.</th><th>Serial No</th><th>Item Name</th><th>Size</th><th>Unit</th><th>Current Stock</th>
<th>Daily Issue</th><th>Daily Received</th><th>Short Qty</th><th>Excess Qty</th></tr></thead>
<tbody>{body}</tbody></table>
</body></html>"""


def tab_daily_sheet():
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
        d = c1.date_input("Date", value=date.today(), key="ds_date")
        fac = c2.selectbox("Factory", FACTORIES, index=FACTORIES.index(FAC) if FAC in FACTORIES else 0, key="ds_fac")
        show_all = c3.checkbox("Include zero-stock", key="ds_all")
        auto = c4.checkbox("Auto-fill issue/received", key="ds_auto")
    ds_term = st.text_input("🔍 Search (Serial No / Item / Size / SL No)", key="ds_search",
                            placeholder="Serial No likhe khujun, e.g. KW-001")
    df = daily_rows(d, fac, show_all or bool(ds_term.strip()))
    shown = df
    if ds_term.strip() and not df.empty:
        tl = ds_term.strip().lower()
        m = df[["Serial No", "Item Name", "Size"]].astype(str).apply(
            lambda c: c.str.lower().str.contains(tl, regex=False)).any(axis=1)
        shown = df[m | (df["SL No."].astype(str) == tl)]
    st.markdown(f'<div class="section-title">Daily Issue Status For Month: {d.strftime("%B-%Y")}</div>',
                unsafe_allow_html=True)
    n_short = int((df["Short Qty"] > 0).sum()) if not df.empty else 0
    n_exc = int((df["Excess Qty"] > 0).sum()) if not df.empty else 0
    st.caption(f"Date: {d.strftime(DATE_FMT)} | Factory: {fac} | SL No = Master Inventory SL (same as Transactions). "
               f"Items: {len(df)} | Short: {n_short} | Excess: {n_exc}")
    view = shown.copy()
    if not auto and not view.empty:
        view["Daily Issue"] = None
        view["Daily Received"] = None
    st.dataframe(view, hide_index=True, use_container_width=True, height=420)
    export_buttons(view, f"daily_work_sheet_{d:%Y%m%d}")
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
ensure_live_connection()
try:
    init_db()
except Exception as e:
    st.error(f"Cloud database-e connect kora jacche na: {e}")
    st.stop()

show_flash()
sidebar_login()

with st.sidebar:
    st.markdown("### 🏭 Active Factory")
    FAC = st.selectbox("Active factory", FACTORIES + [ALL_VIEW], key="factory", label_visibility="collapsed")
    st.caption("📌 CONSOLIDATED view shudhu dekhar jonno. Entry-r jonno specific factory bachun.")
    st.markdown("---")
    st.markdown("### 🧭 Modules")
    for icon, name in MODULE_NAV:
        st.markdown(f'<div class="nav-item">{icon}&nbsp;&nbsp;{name}</div>', unsafe_allow_html=True)
    st.markdown("---")
    sidebar_clock()

FSQL, FP = fw(FAC)
is_cons_view = "CONSOLIDATED" in FAC
autoset_uom_once()

# Top-level navigation: the very first element of the main page. [1] TRANSACTIONS is the default tab.
TAB_NAMES = ["📝 [1] TRANSACTIONS", "📦 [2] INVENTORY", NAV_ERP_AUDIT, "📜 [4] ISSUE LEDGER",
             "🔁 [5] TRANSFER HISTORY", "📑 [6] REQUISITION", "🛠 [7] REPAIR", "📒 [8] LEDGER",
             "📈 [9] FORECAST", "💵 [10] BUDGET", "🗓 [11] DAILY WORK SHEET"]
RENDERERS = [tab_transactions, tab_inventory, tab_erp_audit, tab_issue_ledger, tab_transfer_history,
             tab_requisition, tab_repair, tab_ledger, tab_forecast, tab_budget, tab_daily_sheet]
# Only the opened module is rendered. Streamlit's st.tabs() runs EVERY tab on EVERY click, which made each
# "Save & Update Stock" re-run all 11 modules (twice, because of the refresh after save).
if st.session_state.get(NAV_KEY) not in TAB_NAMES:
    st.session_state[NAV_KEY] = TAB_NAMES[0]
active_tab = st.radio("Module", TAB_NAMES, key=NAV_KEY, horizontal=True, label_visibility="collapsed")
render_header()
RENDERERS[TAB_NAMES.index(active_tab)]()
