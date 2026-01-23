import streamlit as st
import pandas as pd
from datetime import datetime
from serpapi import GoogleSearch
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIGURATION ---
st.set_page_config(page_title="SEO Rank Tracker Pro", layout="wide")

try:
    SERPAPI_KEY = st.secrets["SERPAPI_KEY"]
    GCP_CREDS = st.secrets["GCP_SERVICE_ACCOUNT"]
except:
    st.error("Erreur : Secrets manquants.")
    st.stop()

CONF_PAYS = {
    "France": {"gl": "fr", "hl": "fr", "google_domain": "google.fr", "location": "France"},
    "États-Unis": {"gl": "us", "hl": "en", "google_domain": "google.com", "location": "United States"}
}

# --- FONCTIONS DE CACHE ET VÉRIFICATION ---

def check_today_exists(domain, keyword):
    """Vérifie dans GSheets si le scan a déjà été fait aujourd'hui"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_CREDS, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("SEO_Rank_Tracker_DB").worksheet("Suivi")
        all_rows = sheet.get_all_values()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        t_dom = str(domain).strip().lower()
        t_kw = str(keyword).strip().lower()

        for row in reversed(all_rows):
            if len(row) >= 6:
                if row[0] == today_str and row[1].strip().lower() == t_dom and row[2].strip().lower() == t_kw:
                    return int(float(row[3])), row[5] # Position et URL
        return None, None
    except: return None, None

def get_last_position(domain, keyword):
    """Cherche la position précédente (avant aujourd'hui)"""
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_CREDS, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("SEO_Rank_Tracker_DB").worksheet("Suivi")
        all_rows = sheet.get_all_values()
        
        today_str = datetime.now().strftime("%Y-%m-%d")
        t_dom = str(domain).strip().lower()
        t_kw = str(keyword).strip().lower()

        for row in reversed(all_rows):
            if len(row) >= 4 and row[0] != today_str: # On ignore les lignes d'aujourd'hui
                if row[1].strip().lower() == t_dom and row[2].strip().lower() == t_kw:
                    val = str(row[3]).replace("'", "").strip()
                    if val.isdigit(): return int(val)
        return None
    except: return None

@st.cache_data(ttl=3600)
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
                return int(res.get("position")), res.get("link")
        return 101, None
    except: return "Erreur", None

def save_to_google_sheets(df_to_save, nom_pays):
    if df_to_save.empty: return True
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(GCP_CREDS, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("SEO_Rank_Tracker_DB").worksheet("Suivi")
        df_to_save["Pays"] = nom_pays
        cols = ["Date", "Domaine", "Mot-clé", "Position", "Delta", "URL exacte", "Pays"]
        data = df_to_save[cols].fillna("").astype(str).values.tolist()
        sheet.append_rows(data)
        return True
    except Exception as e:
        st.error(f"Erreur GSheets : {e}")
        return False

# --- INTERFACE ---
st.title("📈 SEO Tracker Intelligent")

with st.sidebar:
    target_domain = st.text_input("Domaine du client :", placeholder="exemple.com")
    keywords_raw = st.text_area("Mots-clés :")
    nom_pays = st.selectbox("Pays :", list(CONF_PAYS.keys()))
    run_btn = st.button("🚀 Lancer / Actualiser")
    if st.button("🧹 Vider le cache"):
        st.cache_data.clear()

if run_btn and target_domain and keywords_raw:
    keywords = [k.strip() for k in keywords_raw.split('\n') if k.strip()]
    results_for_display = []
    data_to_save = []
    
    bar = st.progress(0)
    for i, kw in enumerate(keywords):
        # 1. Vérification si déjà fait aujourd'hui
        pos, url = check_today_exists(target_domain, kw)
        new_scan = False
        
        if pos is None: # Pas encore de donnée pour aujourd'hui
            pos, url = get_serpapi_rank(kw, target_domain, CONF_PAYS[nom_pays])
            new_scan = True
        
        # 2. Récupération de l'historique pour le Delta
        last_pos = get_last_position(target_domain, kw)
        delta = (last_pos - pos) if (isinstance(last_pos, int) and isinstance(pos, int)) else None

        row_data = {
            "Date": datetime.now().strftime("%Y-%m-%d"),
            "Domaine": target_domain, "Mot-clé": kw, "Position": pos,
            "Delta": delta, "URL exacte": url if url else "N/A"
        }
        results_for_display.append(row_data)
        if new_scan: data_to_save.append(row_data)
        bar.progress((i + 1) / len(keywords))

    # Affichage
    df_display = pd.DataFrame(results_for_display)
    for _, row in df_display.iterrows():
        c1, c2 = st.columns([3, 1])
        c1.write(f"**{row['Mot-clé']}**")
        c2.metric("Pos", "100+" if row['Position']==101 else row['Position'], delta=row['Delta'])
    
    # Sauvegarde uniquement des nouvelles analyses
    if data_to_save:
        save_to_google_sheets(pd.DataFrame(data_to_save), nom_pays)
        st.success("✅ Nouvelles données enregistrées.")
    else:
        st.info("ℹ️ Données du jour déjà présentes. Aucun crédit consommé.")
