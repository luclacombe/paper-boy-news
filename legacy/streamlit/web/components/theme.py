"""Newspaper-themed CSS injection and color constants for Paper Boy."""

import streamlit as st

# === COLOR PALETTE (from design spec) ===
INK_BLACK = "#1B1B1B"
NEWSPRINT = "#FAF8F5"
WARM_GRAY = "#E8E4DF"
RULE_GRAY = "#C4BFB8"
CAPTION_GRAY = "#7A7570"
EDITION_RED = "#C23B22"
DELIVERED_GREEN = "#2D6A4F"
BUILDING_AMBER = "#D4A843"
FAILED_CHARCOAL = "#4A4A4A"
WHITE = "#FFFFFF"


def inject_theme():
    """Inject the full newspaper-themed CSS into the current page.

    Call this at the top of every page before rendering any content.
    """
    st.markdown(
        """
    <style>
    /* === FONTS === */
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;700;900&family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=Source+Sans+3:wght@300;400;600;700&family=JetBrains+Mono:wght@400&display=swap');

    /* === LUCIDE ICONS === */
    @import url('https://unpkg.com/lucide-static@latest/font/lucide.css');

    /* === GLOBAL === */
    html, body, [class*="css"] {
        font-family: 'Source Sans 3', -apple-system, sans-serif !important;
        color: #1B1B1B;
    }

    /* === HIDE STREAMLIT CHROME === */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header[data-testid="stHeader"] {display: none;}
    .stDeployButton {display: none;}
    div[data-testid="stToolbar"] {display: none;}
    div[data-testid="stDecoration"] {display: none;}

    /* === PAGE BACKGROUND === */
    .stApp {
        background-color: #FAF8F5;
    }

    /* Subtle paper grain texture */
    .stApp::before {
        content: '';
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
        pointer-events: none;
        z-index: 0;
    }

    /* === CONTAINER === */
    .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
        max-width: 960px !important;
    }

    /* === BUTTONS === */
    .stButton > button {
        border-radius: 2px !important;
        font-family: 'Source Sans 3', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em;
        transition: all 0.2s ease;
        border: 1px solid #C4BFB8 !important;
    }
    .stButton > button:hover {
        border-color: #1B1B1B !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background-color: #C23B22 !important;
        color: white !important;
        border: none !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover {
        background-color: #A83220 !important;
    }

    /* === DOWNLOAD BUTTON === */
    .stDownloadButton > button {
        border-radius: 2px !important;
        font-family: 'Source Sans 3', sans-serif !important;
        font-weight: 600 !important;
    }

    /* === TEXT INPUTS === */
    .stTextInput > div > div > input {
        border-radius: 2px !important;
        border: 1px solid #C4BFB8 !important;
        font-family: 'Source Sans 3', sans-serif !important;
    }
    .stTextInput > div > div > input:focus {
        border-color: #C23B22 !important;
        box-shadow: 0 0 0 1px #C23B22 !important;
    }

    /* === SELECT BOXES === */
    .stSelectbox > div > div {
        border-radius: 2px !important;
    }

    /* === CHECKBOXES === */
    .stCheckbox label {
        font-family: 'Source Sans 3', sans-serif !important;
    }

    /* === RADIO BUTTONS === */
    .stRadio label {
        font-family: 'Source Sans 3', sans-serif !important;
    }

    /* === TABS === */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid #C4BFB8;
    }
    .stTabs [data-baseweb="tab"] {
        font-family: 'Source Sans 3', sans-serif !important;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        font-size: 0.85rem;
        padding: 0.75rem 1.5rem;
        border-bottom: 3px solid transparent;
        color: #7A7570;
    }
    .stTabs [aria-selected="true"] {
        border-bottom: 3px solid #C23B22 !important;
        color: #1B1B1B !important;
    }

    /* === EXPANDER === */
    .streamlit-expanderHeader {
        font-family: 'Source Sans 3', sans-serif !important;
        font-weight: 600;
    }

    /* === CUSTOM TYPOGRAPHY CLASSES === */
    .masthead-title {
        font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
        font-weight: 900;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #1B1B1B;
        text-align: center;
        margin: 0;
        padding: 0;
    }
    .masthead-subtitle {
        font-family: 'Source Sans 3', sans-serif;
        font-weight: 300;
        color: #7A7570;
        text-align: center;
        font-size: 1.1rem;
        margin: 0.25rem 0 0 0;
    }
    .masthead-date {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #7A7570;
        text-align: center;
    }

    /* === COMPACT HEADER === */
    .compact-header-title {
        font-family: 'Playfair Display', Georgia, 'Times New Roman', serif;
        font-weight: 900;
        font-size: 1.3rem;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: #1B1B1B;
        text-align: center;
        margin: 0;
        padding: 0.5rem 0 0.25rem 0;
    }

    .headline-text {
        font-family: 'Libre Baskerville', Georgia, serif;
        font-weight: 700;
        color: #1B1B1B;
        line-height: 1.3;
    }

    .section-label {
        font-family: 'Source Sans 3', sans-serif;
        font-weight: 700;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: #7A7570;
    }

    .body-text {
        font-family: 'Source Sans 3', sans-serif;
        font-weight: 400;
        color: #1B1B1B;
        line-height: 1.6;
    }

    .caption-text {
        font-family: 'Source Sans 3', sans-serif;
        font-weight: 400;
        font-size: 0.85rem;
        color: #7A7570;
    }

    .mono-text {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        color: #7A7570;
    }

    .pull-quote {
        font-family: 'Libre Baskerville', Georgia, serif;
        font-style: italic;
        font-size: 1.15rem;
        line-height: 1.6;
        color: #1B1B1B;
        text-align: center;
        max-width: 600px;
        margin: 0 auto;
    }
    .pull-quote-mark {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 3rem;
        color: #C4BFB8;
        line-height: 0.5;
    }

    /* === HORIZONTAL RULES === */
    .thick-rule {
        border: none;
        border-top: 3px solid #1B1B1B;
        margin: 0;
    }
    .thin-rule {
        border: none;
        border-top: 1px solid #C4BFB8;
        margin: 0;
    }
    .double-rule {
        border: none;
        border-top: 3px double #1B1B1B;
        margin: 0;
    }
    .dotted-rule {
        border: none;
        border-top: 1px dotted #C4BFB8;
        margin: 0;
    }

    /* === CARDS === */
    .pb-card {
        background: #FFFFFF;
        border: 1px solid #E8E4DF;
        border-radius: 2px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        padding: 1.25rem;
        margin-bottom: 0.75rem;
    }
    .pb-card:hover {
        box-shadow: 0 2px 6px rgba(0,0,0,0.08);
    }
    .pb-card-clickable {
        cursor: pointer;
        transition: box-shadow 0.2s ease, border-color 0.2s ease;
    }
    .pb-card-clickable:hover {
        border-color: #C23B22;
    }
    .pb-card.pb-card-selected {
        border-color: #C23B22 !important;
        border-width: 2px;
        box-shadow: 0 0 0 1px #C23B22;
    }

    /* Device selection cards */
    .device-card {
        text-align: center;
        padding: 1.5rem 0.75rem;
        min-height: 170px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    /* Device card clickable overlay — invisible button covers the card */
    [data-testid="stColumn"]:has(.device-select-card) [data-testid="stButton"] {
        margin-top: -190px;
        position: relative;
        z-index: 10;
    }
    [data-testid="stColumn"]:has(.device-select-card) [data-testid="stButton"] button {
        height: 190px;
        background: transparent !important;
        border: none !important;
        color: transparent !important;
        cursor: pointer;
        box-shadow: none !important;
        border-radius: 2px !important;
    }
    [data-testid="stColumn"]:has(.device-select-card) [data-testid="stButton"] button:hover {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* Bundle card clickable overlay — invisible button covers the card */
    [data-testid="stColumn"]:has(.bundle-select-card) [data-testid="stButton"] {
        margin-top: -90px;
        position: relative;
        z-index: 10;
    }
    [data-testid="stColumn"]:has(.bundle-select-card) [data-testid="stButton"] button {
        height: 90px;
        background: transparent !important;
        border: none !important;
        color: transparent !important;
        cursor: pointer;
        box-shadow: none !important;
        border-radius: 2px !important;
    }
    [data-testid="stColumn"]:has(.bundle-select-card) [data-testid="stButton"] button:hover {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* === STATUS BADGES === */
    .badge {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 2px;
        font-family: 'Source Sans 3', sans-serif;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.03em;
    }
    .badge-delivered {
        background-color: #E8F5E9;
        color: #2D6A4F;
    }
    .badge-building {
        background-color: #FFF8E1;
        color: #D4A843;
    }
    .badge-failed {
        background-color: #F5F5F5;
        color: #4A4A4A;
    }
    .badge-active {
        background-color: #E8F5E9;
        color: #2D6A4F;
    }

    /* === STATUS BANNER === */
    .status-banner {
        background: #FFFFFF;
        border: 1px solid #E8E4DF;
        border-radius: 2px;
        padding: 1.25rem 1.5rem;
        text-align: center;
    }
    .status-banner-delivered {
        border-left: 4px solid #2D6A4F;
    }
    .status-banner-building {
        border-left: 4px solid #D4A843;
    }
    .status-banner-failed {
        border-left: 4px solid #4A4A4A;
    }

    /* === EDITION RED ACCENT BAR === */
    .accent-bar {
        width: 100%;
        height: 4px;
        background-color: #C23B22;
        margin: 0;
    }

    /* === SOURCE STATUS TABLE === */
    .source-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0.5rem 0;
        border-bottom: 1px dotted #C4BFB8;
        font-family: 'Source Sans 3', sans-serif;
        font-size: 0.9rem;
    }
    .source-row:last-child {
        border-bottom: none;
    }

    /* === STEP INDICATOR === */
    .step-indicator {
        display: flex;
        justify-content: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
    }
    .step-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background-color: #C4BFB8;
    }
    .step-dot-active {
        background-color: #C23B22;
    }
    .step-dot-completed {
        background-color: #1B1B1B;
    }

    /* === FOOTER === */
    .pb-footer {
        text-align: center;
        font-family: 'Source Sans 3', sans-serif;
        font-size: 0.85rem;
        color: #7A7570;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        padding: 2rem 0 1rem 0;
    }

    /* === LANDING PAGE SPECIFIC === */
    .landing-hero {
        text-align: center;
        padding: 3rem 0 2rem 0;
    }
    .landing-hero .masthead-title {
        font-size: 2.5rem;
    }
    .how-it-works-card {
        background: #FFFFFF;
        border: 1px solid #E8E4DF;
        border-radius: 2px;
        padding: 1.5rem;
        text-align: center;
        height: 100%;
    }
    .how-it-works-number {
        font-family: 'Playfair Display', Georgia, serif;
        font-size: 2rem;
        font-weight: 700;
        color: #C4BFB8;
        margin-bottom: 0.5rem;
    }
    .how-it-works-title {
        font-family: 'Libre Baskerville', Georgia, serif;
        font-weight: 700;
        font-size: 1.1rem;
        color: #1B1B1B;
        margin-bottom: 0.5rem;
    }
    .how-it-works-desc {
        font-family: 'Source Sans 3', sans-serif;
        font-size: 0.95rem;
        color: #7A7570;
        line-height: 1.5;
    }

    /* === RESPONSIVE === */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        .landing-hero .masthead-title {
            font-size: 1.8rem;
        }
        .masthead-title {
            font-size: 1.5rem !important;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )
