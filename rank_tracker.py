import streamlit as st
import pandas as pd
from datetime import datetime
from serpapi import GoogleSearch
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
st.set_page_config(page_title="SEO Rank Tracker - Pro", layout="wide")
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]

CONF_PAYS = {
    "France": {"gl": "fr", "hl": "fr", "google_domain": "google.fr", "location": "France"},
    "États-Unis": {"gl": "us", "hl": "en", "google_domain": "google.com", "location": "United States"}
}

# --- FONCTIONS ---

def get_serpapi_rank(query, domain, country_config):
    params = {
        "q": query, "location": country_config["location"], "hl": country_config["hl"],
        "gl": country_config["gl"], "google_domain": country_config["google_domain"],
        "api_key": SERPAPI_KEY, "num": 100 
    }
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        organic = results.get("organic_results", [])
        clean_domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").strip().lower()
        for res in organic:
            if clean_domain in res.get("link", "").lower():
                return res.get("position"), res.get("link")
        return 101, None
    except Exception as e:
        return "Erreur", None

def get_last_position(keyword, nom_pays):
    """Cherche la dernière position dans le Google Sheet"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GCP_SERVICE_ACCOUNT"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("SEO_Rank_Tracker_DB").sheet1
        records = sheet.get_all_records()
        if not records: return None
        df_h = pd.DataFrame(records)
        df_f = df_h[(df_h['Mot-clé'] == keyword) & (df_h['Pays'] == nom_pays)]
        if not df_f.empty:
            return df_f.iloc[-1]['Position']
    except: return None
    return None

def save_to_google_sheets(df_new, nom_pays):
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["GCP_SERVICE_ACCOUNT"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("SEO_Rank_Tracker_DB").sheet1
        df_new["Pays"] = nom_pays
        data = df_new.fillna("").astype(str).values.tolist()
        sheet.append_rows(data)
        return True
    except Exception as e:
        st.error(f"Erreur GSheets : {e}")
        return False

# --- INTERFACE ---
st.title("📈 SEO Rank Tracker & Evolution")

with st.sidebar:
    st.header("⚙️ Configuration")
    target_domain = st.text_input("Domaine :", placeholder="monsite.com")
    keywords_raw = st.text_area("Mots-clés (1 par ligne) :")
    nom_pays = st.selectbox("Pays :", list(CONF_PAYS.keys()))
    run_btn = st.button("🚀 Analyser & Sauvegarder")

if run_btn and target_domain and keywords_raw:
    keywords = [k.strip() for k in keywords_raw.split('\n') if k.strip()]
    tracking_data = []
    bar = st.progress(0)
    
    for i, kw in enumerate(keywords):
        with st.spinner(f"Analyse : {kw}"):
            pos, url = get_serpapi_rank(kw, target_domain, CONF_PAYS[nom_pays])
            last_pos = get_last_position(kw, nom_pays)
            
            # Calcul du delta (ex: ancienne pos 10, nouvelle 8 = +2 places)
            delta = None
            if last_pos and isinstance(pos, int) and str(last_pos).isdigit():
                delta = int(last_pos) - pos 

            tracking_data.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Domaine": target_domain,  
                "Mot-clé": kw,
                "Position": pos,
                "Delta": delta,
                "URL exacte": url if url else "N/A"
            })
        bar.progress((i + 1) / len(keywords))

    df = pd.DataFrame(tracking_data)
    save_to_google_sheets(df, nom_pays)

    # --- AFFICHAGE DES RÉSULTATS ---
    st.subheader("📊 Résultats et Progression")
    for _, row in df.iterrows():
        c1, c2 = st.columns([3, 1])
        c1.write(f"**{row['Mot-clé']}**")
        val_display = "Top 100+" if row['Position'] == 101 else row['Position']
        c2.metric(label="Pos", value=val_display, delta=row['Delta'])
    
    st.dataframe(df, use_container_width=True)
