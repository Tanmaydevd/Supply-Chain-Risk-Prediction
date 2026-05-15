"""Shared dark-theme CSS injected into every Streamlit page."""
import streamlit as st

DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ── Base ─────────────────────────────────────────────────────────────── */
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"],.main{
  background:#0d1117!important; font-family:'Inter',sans-serif!important;}
[data-testid="stSidebar"]{background:#0a0f1a!important;border-right:1px solid #1f2937;}
[data-testid="stHeader"]{background:transparent!important;}
.block-container{padding-top:.8rem!important;padding-bottom:2rem!important;}

/* ── Sidebar branding ─────────────────────────────────────────────────── */
[data-testid="stSidebarNav"]::before{
  content:"🛡️  SupplyGuard";display:block;
  font-size:1.05rem;font-weight:800;color:#f9fafb;
  padding:1.4rem 1rem .2rem;letter-spacing:-.01em;}
[data-testid="stSidebarNav"]::after{
  content:"AI Risk Intelligence";display:block;
  font-size:.68rem;color:#4b5563;letter-spacing:.05em;font-weight:500;
  padding:0 1rem 1rem;border-bottom:1px solid #1a2236;margin-bottom:.4rem;}
[data-testid="stSidebarNavLink"]{
  border-radius:8px!important;margin:1px 8px!important;
  font-size:.865rem!important;font-weight:500!important;color:#9ca3af!important;
  transition:all .15s ease!important;}
[data-testid="stSidebarNavLink"]:hover{
  background:#1a2236!important;color:#e5e7eb!important;}
[data-testid="stSidebarNavLink"][aria-selected="true"]{
  background:linear-gradient(90deg,#1e3a5f,#1a2236)!important;
  color:#60a5fa!important;border-left:2px solid #3b82f6!important;}

/* ── Metric cards ─────────────────────────────────────────────────────── */
[data-testid="stMetric"]{
  background:#111827;border:1px solid #1f2937;
  border-radius:12px;padding:14px 16px!important;
  transition:all .2s ease;position:relative;overflow:hidden;}
[data-testid="stMetric"]::before{
  content:'';position:absolute;top:0;left:0;right:0;height:2px;
  background:linear-gradient(90deg,#3b82f6,#6366f1);opacity:0;
  transition:opacity .2s ease;}
[data-testid="stMetric"]:hover::before{opacity:1;}
[data-testid="stMetric"]:hover{border-color:#374151;transform:translateY(-1px);}
[data-testid="stMetricLabel"] p{
  color:#6b7280!important;font-size:.68rem!important;
  text-transform:uppercase;letter-spacing:.07em;font-weight:600!important;}
[data-testid="stMetricValue"]{color:#f9fafb!important;font-weight:700!important;}

/* ── DataFrames ───────────────────────────────────────────────────────── */
[data-testid="stDataFrame"]{border:1px solid #1f2937!important;border-radius:10px!important;}
.dvn-scroller,.glideDataEditor{background:#0d1117!important;}

/* ── Buttons ──────────────────────────────────────────────────────────── */
[data-testid="stButton"]>button{
  border-radius:8px!important;font-weight:600!important;
  transition:all .15s ease!important;font-family:'Inter',sans-serif!important;}
[data-testid="stButton"]>button[kind="primary"]{
  background:linear-gradient(135deg,#3b82f6,#6366f1)!important;border:none!important;color:#fff!important;}
[data-testid="stButton"]>button[kind="primary"]:hover{
  transform:translateY(-1px);box-shadow:0 4px 16px rgba(99,102,241,.45)!important;}
[data-testid="stButton"]>button[kind="secondary"]{
  background:#1f2937!important;border:1px solid #374151!important;color:#d1d5db!important;}
[data-testid="stButton"]>button[kind="secondary"]:hover{
  background:#374151!important;color:#f9fafb!important;}

/* ── Expanders ────────────────────────────────────────────────────────── */
[data-testid="stExpander"]{
  background:#111827!important;border:1px solid #1f2937!important;border-radius:10px!important;}

/* ── Select sliders ───────────────────────────────────────────────────── */
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"],
[data-testid="stSelectSlider"] span{color:#6b7280!important;}
label[data-testid="stWidgetLabel"] p{color:#9ca3af!important;font-size:.8rem!important;}

/* ── Divider ──────────────────────────────────────────────────────────── */
hr{border-color:#1f2937!important;margin:.8rem 0!important;}

/* ── Scrollbar ────────────────────────────────────────────────────────── */
::-webkit-scrollbar{width:4px;height:4px;}
::-webkit-scrollbar-track{background:#0d1117;}
::-webkit-scrollbar-thumb{background:#374151;border-radius:99px;}

/* ── Info / warning / error boxes ────────────────────────────────────── */
[data-testid="stAlert"]{border-radius:10px!important;border-width:1px!important;}

/* ── Toggle ──────────────────────────────────────────────────────────── */
[data-testid="stToggle"] span{font-size:.82rem!important;color:#9ca3af!important;}

/* ── Section header helper ────────────────────────────────────────────── */
.sec-hdr{font-size:.68rem;font-weight:700;color:#6b7280;
         text-transform:uppercase;letter-spacing:.1em;margin-bottom:6px;}
</style>
"""

def inject():
    st.markdown(DARK_CSS, unsafe_allow_html=True)


def section(label: str, height: int = 22):
    import streamlit.components.v1 as components
    components.html(
        f"""<style>@import url('https://fonts.googleapis.com/css2?family=Inter:wght@700&display=swap');
        *{{font-family:'Inter',sans-serif;margin:0;padding:0}}
        .s{{font-size:.68rem;font-weight:700;color:#6b7280;
            text-transform:uppercase;letter-spacing:.1em}}</style>
        <div class="s">{label}</div>""",
        height=height,
    )
