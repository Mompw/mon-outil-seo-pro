import streamlit as st
import pandas as pd
from datetime import datetime
from serpapi import GoogleSearch

# --- CONFIGURATION ---
st.set_page_config(page_title="SEO Rank Tracker - SerpApi", layout="wide")
SERPAPI_KEY = st.secrets["SERPAPI_KEY"]

# Dictionnaire de configuration par pays
CONF_PAYS = {
    "France": {
        "gl": "fr", 
        "hl": "fr", 
        "google_domain": "google.fr", 
        "location": "France"
    },
    "États-Unis": {
        "gl": "us", 
        "hl": "en", 
        "google_domain": "google.com", 
        "location": "United States"
    }
}

# --- FONCTIONS ---

def get_serpapi_rank(query, domain, country_config):
    """Cherche la position via SerpApi avec config dynamique"""
    params = {
        "q": query,
        "location": country_config["location"],
        "hl": country_config["hl"],
        "gl": country_config["gl"],
        "google_domain": country_config["google_domain"],
        "api_key": SERPAPI_KEY,
        "num": 100 
    }
    
    try:
        search = GoogleSearch(params)
        results = search.get_dict()
        organic_results = results.get("organic_results", [])
        
        # Nettoyage du domaine pour la comparaison
        clean_domain = domain.replace("https://", "").replace("http://", "").replace("www.", "").strip().lower()
        
        for result in organic_results:
            link = result.get("link", "").lower()
            if clean_domain in link:
                return result.get("position"), result.get("link")
        
        return ">100", None
    except Exception as e:
        st.error(f"Erreur API pour '{query}': {e}")
        return "Erreur", None

# --- INTERFACE ---
st.title("📈 Freelance Rank Tracker (SerpApi)")
st.info("Suivi des positions sur Google France et USA.")

with st.sidebar:
    st.header("⚙️ Paramètres de suivi")
    target_domain = st.text_input("Domaine à surveiller :", placeholder="ex: monsite.com")
    keywords_raw = st.text_area("Mots-clés (1 par ligne) :", height=200)
    
    st.divider()
    # Sélection du pays (USA ou France)
    nom_pays = st.selectbox("Pays cible :", list(CONF_PAYS.keys()))
    config_actuelle = CONF_PAYS[nom_pays]
    
    run_btn = st.button("🚀 Lancer le tracking")

if run_btn and target_domain and keywords_raw:
    keywords = [k.strip() for k in keywords_raw.split('\n') if k.strip()]
    tracking_data = []
    
    progress_bar = st.progress(0)
    
    for i, kw in enumerate(keywords):
        with st.spinner(f"Analyse de : {kw} ({nom_pays})..."):
            # CORRECTION : On passe l'objet config_actuelle
            pos, url_found = get_serpapi_rank(kw, target_domain, config_actuelle)
            
            tracking_data.append({
                "Date": datetime.now().strftime("%Y-%m-%d"),
                "Mot-clé": kw,
                "Position": pos,
                "URL exacte": url_found if url_found else "Non trouvé"
            })
        progress_bar.progress((i + 1) / len(keywords))

    # --- AFFICHAGE ---
    df = pd.DataFrame(tracking_data)
    
    # Indicateurs (KPIs)
    c1, c2, c3 = st.columns(3)
    # Filtrage propre pour les calculs de metrics
    numeric_pos = df[df['Position'].apply(lambda x: isinstance(x, int))]
    top_3 = len(numeric_pos[numeric_pos['Position'] <= 3])
    top_10 = len(numeric_pos[numeric_pos['Position'] <= 10])
    
    c1.metric("Mots-clés suivis", len(df))
    c2.metric("Dans le Top 3", top_3)
    c3.metric("Dans le Top 10", top_10)

    # Style du tableau
    def highlight_rank(val):
        if val == 1: return 'background-color: #28a745; color: white;'
        if isinstance(val, int) and val <= 10: return 'background-color: #fff3cd;'
        if val == ">100": return 'color: #dc3545;'
        return ''

    st.write(f"### 📊 Résultats - {nom_pays}")
    st.dataframe(df.style.applymap(highlight_rank, subset=['Position']), use_container_width=True)

    # Export
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Télécharger l'export CSV", csv, f"rank_tracking_{nom_pays}.csv", "text/csv")
