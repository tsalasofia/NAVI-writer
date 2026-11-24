"""Shared look & feel for Navi (light, pastel pink -> blue gradient, high contrast)."""
import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root{
  --ink:#111827; --muted:#4b5568; --acc:#9d1f63; --line:#ead3e2; --card:#ffffff;
  --grad:linear-gradient(135deg,#f6a9d1 0%,#a5e4ff 62%,#8fb4ff 100%);
  --grad-soft:linear-gradient(135deg,#fff0f7 0%,#eef9ff 100%);
  color-scheme:light;
}
html,body,[class*="css"],.stApp{font-family:'Inter',sans-serif;}
.stApp{background:linear-gradient(135deg,#fff4fa 0%,#f7fbff 55%,#ebfaff 100%) fixed;}
#MainMenu,footer,header[data-testid="stHeader"]{visibility:hidden;height:0;}
/* the built-in Streamlit sidebar is not used: the chat list lives in the page */
[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"],[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"]{display:none!important;}
[data-testid="stSidebarNav"]{display:none;}
.block-container{padding:0 2rem 7rem 2rem;max-width:1400px;}

/* ---------- text: always dark, whatever Streamlit theme is active ---------- */
.stApp,.stApp p,.stApp span,.stApp label,.stApp li,.stApp h1,.stApp h2,.stApp h3,.stApp h4,
.stApp small,.stApp summary,.stApp button,.stApp button *,
[data-testid="stMarkdownContainer"] *,[data-testid="stCaptionContainer"] *,
[data-testid="stWidgetLabel"] *,[data-testid="stFileUploaderDropzone"] *,
[data-testid="stExpander"] *,[data-testid="stAlert"] *{color:var(--ink)!important;}
.stApp ::placeholder{color:#5b6475!important;opacity:1!important;}
.stApp [data-testid="stCaptionContainer"] *,.hero p,.page-head p,.filemeta,.note,.note *,
.side-label,.panel-label,.ws{color:var(--muted)!important;}
.hero .tag,.step{color:var(--acc)!important;}

/* ---------- widgets: always light ---------- */
.stTextInput input,.stTextArea textarea,[data-baseweb="input"],[data-baseweb="base-input"],
[data-baseweb="select"]>div,[data-baseweb="select"] input{
  background:#fff!important;color:var(--ink)!important;border-radius:12px!important;}
.stTextInput>div>div,[data-baseweb="select"]>div{border:1px solid var(--line)!important;}
.stTextInput>div>div:focus-within{border-color:#e48fbd!important;box-shadow:0 0 0 3px rgba(228,143,189,.25)!important;}
[data-baseweb="popover"],[data-baseweb="popover"]>div,[data-baseweb="menu"],[data-testid="stPopoverBody"]{
  background:#fff!important;color:var(--ink)!important;}
[data-baseweb="menu"] li:hover{background:#fff0f7!important;}
.stButton>button,.stDownloadButton>button,[data-testid="stPopover"]>button,
[data-testid="stFileUploaderDropzone"] button{
  background:#fff!important;border:1px solid var(--line)!important;border-radius:12px;box-shadow:none;}
.stButton>button:hover,[data-testid="stPopover"]>button:hover{border-color:#e48fbd!important;background:#fff7fb!important;}
.stButton>button[kind="primary"],.stDownloadButton>button[kind="primary"],
[data-testid="stFormSubmitButton"] button{background:var(--grad)!important;border:0!important;font-weight:600;}
[data-testid="stExpander"] details{background:#fff;border:1px solid var(--line);border-radius:12px;}
[data-testid="stFileUploaderDropzone"]{border:1.5px dashed #eaa8cb!important;border-radius:16px;background:#fff0f7!important;}
[data-testid="stVerticalBlockBorderWrapper"]{border-color:var(--line)!important;border-radius:14px;background:rgba(255,255,255,.7);}

/* ---------- left panel (chats) ---------- */
[data-testid="stColumn"]:has(.st-key-sidepanel),
div[data-testid="column"]:has(.st-key-sidepanel){
  position:sticky!important;top:4.8rem;align-self:flex-start!important;
  max-height:calc(100vh - 6rem);overflow-y:auto;background:linear-gradient(180deg,#fff0f7,#fdf5fa);
  border:1px solid var(--line);border-radius:16px;padding:1rem;}
.st-key-sidepanel .stButton>button{width:100%;justify-content:flex-start;background:transparent!important;
  border:0!important;font-size:.88rem;padding:.5rem .7rem;border-radius:10px;}
.st-key-sidepanel .stButton>button:hover{background:rgba(255,255,255,.9)!important;}
.st-key-sidepanel .stButton>button[kind="primary"]{background:#fff!important;
  box-shadow:0 0 0 1px var(--line),0 2px 8px rgba(200,120,170,.12);font-weight:600;}
.st-key-sidepanel [data-testid="stPopover"]>button{background:transparent!important;border:0!important;padding:.3rem;}
.st-key-sidepanel .st-key-newchat button{background:var(--grad)!important;justify-content:center!important;
  font-weight:600;padding:.65rem!important;border-radius:12px!important;}
.side-label{font-size:.7rem;letter-spacing:.08em;font-weight:600;margin:1.2rem 0 .4rem .4rem;}

/* ---------- top bar ---------- */
[data-testid="stElementContainer"]:has(> .st-key-topbar),
[data-testid="stLayoutWrapper"]:has(> .st-key-topbar),
div.element-container:has(> .st-key-topbar){position:sticky!important;top:0;z-index:999;}
.st-key-topbar{background:linear-gradient(90deg,#fff3f9,#eefbff);border-bottom:1px solid var(--line);
  padding:.65rem 2rem;margin:0 -2rem 1.4rem -2rem;}
.brand{font-weight:700;font-size:1.2rem;letter-spacing:.02em;margin-top:.15rem;}
.st-key-topbar a{border-radius:10px;padding:.4rem .9rem;font-size:.86rem;font-weight:500;
  text-decoration:none;background:rgba(255,255,255,.85);border:1px solid var(--line);}
.st-key-topbar a,.st-key-topbar a *{color:var(--ink)!important;}
.st-key-topbar a[aria-current="page"]{background:var(--grad);border-color:transparent;font-weight:600;}
.ws{font-size:.8rem;text-align:right;padding-top:.5rem;}

/* ---------- right files panel ---------- */
[data-testid="stColumn"]:has(.st-key-filespanel),
div[data-testid="column"]:has(.st-key-filespanel){
  position:sticky!important;top:4.8rem;align-self:flex-start!important;
  max-height:calc(100vh - 6rem);overflow-y:auto;background:#eaf8fc;border:1px solid #cfeaf3;border-radius:16px;padding:1rem;}
.panel-title{font-size:.95rem;font-weight:600;margin-bottom:.6rem;}
.panel-label{font-size:.7rem;letter-spacing:.08em;font-weight:600;margin:1rem 0 .4rem;}
.filerow{display:flex;align-items:center;gap:.7rem;padding:.55rem 0;border-bottom:1px solid #cfeaf3;}
.fileicon{width:34px;height:34px;border-radius:8px;background:#fff;display:flex;align-items:center;justify-content:center;}
.filename{font-size:.84rem;font-weight:500;word-break:break-all;}
.note{background:rgba(255,255,255,.8);border-radius:12px;padding:.8rem;font-size:.76rem;margin-top:1rem;}

/* ---------- hero + starter cards ---------- */
.hero{text-align:center;padding:2.5rem 0 1.5rem;}
.hero .orb{width:46px;height:46px;margin:0 auto 1rem;border-radius:14px;background:var(--grad);
  display:flex;align-items:center;justify-content:center;font-size:1.3rem;}
.hero .tag{font-size:.8rem;margin-bottom:.4rem;font-weight:500;}
.hero h1{font-size:2.3rem;font-weight:600;margin:0 0 .5rem;padding:0;}
.hero p{font-size:.92rem;}
.st-key-cards button{background:var(--grad-soft)!important;border:1px solid var(--line)!important;border-radius:14px;
  min-height:92px;align-items:flex-start;justify-content:flex-start;text-align:left;padding:1rem;width:100%;}
.st-key-cards button:hover{border-color:#e48fbd!important;}
.st-key-cards button p{text-align:left;font-size:.8rem;line-height:1.5;}
.st-key-cards button p:not(:has(strong)){color:var(--muted)!important;}
.st-key-cards button strong{font-size:.9rem;font-weight:600;}

/* ---------- chat ---------- */
/* notebook look: full-width bands that hug the text. white = Navi, pink = you */
[class*="st-key-chatlog"]{gap:0!important;}
.st-key-chatlog_new{margin-top:-1rem;}
[data-testid="stChatMessage"]{background:#ffffff;border-radius:0;margin:0;
  padding:.8rem 1.4rem;border-bottom:1px solid #f6dbe8;align-items:flex-start;}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]){background:#ffe7f1;}
/* avatars: plain squares, no icons. you = black, Navi = pink/blue ombre */
[data-testid^="stChatMessageAvatar"]{border-radius:8px!important;overflow:hidden;}
[data-testid^="stChatMessageAvatar"] *{visibility:hidden!important;}
[data-testid="stChatMessageAvatarUser"]{background:#E076D2!important;}/*EDO ALLAKSAAAAAAAAAAAAAA!!!!!!!!!!!!!!!!!!!!!!!8*/
[data-testid="stChatMessageAvatarAssistant"]{background:var(--grad)!important;}
[data-testid="stBottom"],[data-testid="stBottom"]>div,[data-testid="stBottomBlockContainer"]{background:transparent!important;}
[data-testid="stChatInput"],[data-testid="stChatInput"]>div,[data-testid="stChatInput"] div[data-baseweb]{
  background:#fff!important;}
[data-testid="stChatInput"]{border-radius:18px;border:1.5px solid #e4b8d6;box-shadow:0 4px 18px rgba(200,120,170,.15);}
[data-testid="stChatInput"] textarea{color:var(--ink)!important;}
[data-testid="stChatInput"] button{background:var(--grad)!important;border-radius:10px;}

/* ---------- tabs / headings ---------- */
.stTabs [data-baseweb="tab-list"]{gap:.3rem;border-bottom:1px solid var(--line);}
.stTabs [aria-selected="true"]{background:#fff0f7;border-radius:8px 8px 0 0;font-weight:600;}
.stTabs [data-baseweb="tab-highlight"]{background:var(--acc);}
.page-head h1{font-size:1.8rem;font-weight:600;margin:.2rem 0;padding:0;}
.page-head p{font-size:.92rem;}
.step{display:inline-flex;width:22px;height:22px;border-radius:50%;background:#fff0f7;
  font-size:.72rem;font-weight:600;align-items:center;justify-content:center;margin-right:.5rem;}
</style>
"""


def setup(title="Navi", icon="✦", sidebar=True):
    st.set_page_config(page_title=title, page_icon=icon, layout="wide",
                       initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)


def topbar(current=None):
    """Pass current="diary" on the Diary page. On every other page the diary
    is re-locked, so tapping Diary always asks for the PIN."""
    if current != "diary":
        st.session_state.diary_unlocked = False
    with st.container(key="topbar"):
        a, b, c, d, _, e = st.columns([1.1, 1.7, 1.2, 1.7, 3, 1.5])
        a.markdown('<div class="brand">NAVI</div>', unsafe_allow_html=True)
        b.page_link("app.py", label="Conversations", icon="💬")
        c.page_link("pages/2_Diary.py", label="Diary", icon="📔")
        d.page_link("pages/1_Report_Writer.py", label="Report Writer", icon="📝")
        e.markdown('<div class="ws">Personal workspace</div>', unsafe_allow_html=True)


def file_icon(name):
    return "📕" if name.lower().endswith(".pdf") else "📄"