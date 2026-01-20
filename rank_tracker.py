import streamlit as st
import requests
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
st.set_page_config(page_title="SEO Rank Tracker Freelance", layout="wide")
SERPER_API_KEY = st.secrets["SERPER_API_KEY"]

# --- FONCTIONS ---

def check_ranking(query, domain, gl="fr", hl="fr"):
    """Cherche la position d'un domaine dans le top 100 de Google via Serper"""
    url = "https://google.serper.dev/search"
    # On demande 100 résultats pour être sûr de trouver le site même s'il est loin
    payload = {"q": query, "gl": gl, "hl": hl, "num": 100}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        results = response.json().get('organic', [])
        
        for i, result in enumerate(results):
            if domain.replace("https://", "").replace("http://", "").replace("www.", "") in result['link']:
                return i + 1, result['link']
        return ">100", None
    except Exception as e:
        return "Erreur", None

# --- INTERFACE ---
st.title("📈 SEO Rank Tracker")
st.subheader("Suivi des positions stratégiques")

with st.sidebar:
    st.header("Paramètres")
    target_domain = st.text_input("Ton domaine (ex: monsite.fr)", placeholder="monsite.fr")
    keywords_input = st.text_area("Mots-clés (un par ligne)", height=200)
    check_btn = st.button("🚀 Lancer le tracking")

if check_btn and target_domain and keywords_input:
    keywords = [k.strip() for k in keywords_input.split('\n') if k.strip()]
    results_list = []
    
    progress_bar = st.progress(0)
    for index, kw in enumerate(keywords):
        with st.spinner(f"Vérification : {kw}..."):
            pos, link = check_ranking(kw, target_domain)
            results_list.append({
                "Date": datetime.now().strftime("%d/%m/%Y"),
                "Mot-clé": kw,
                "Position": pos,
                "URL trouvée": link if link else "N/A"
            })
        progress_bar.progress((index + 1) / len(keywords))

    # Affichage du tableau de bord
    df = pd.DataFrame(results_list)
    
    # Statistiques rapides
    col1, col2, col3 = st.columns(3)
    top_3 = len(df[df['Position'].apply(lambda x: isinstance(x, int) and x <= 3)])
    top_10 = len(df[df['Position'].apply(lambda x: isinstance(x, int) and x <= 10)])
    
    col1.metric("Mots-clés suivis", len(df))
    col2.metric("Dans le Top 3", top_3)
    col3.metric("Dans le Top 10", top_10)

    st.divider()
    
    # Style conditionnel pour les positions
    def color_position(val):
        if val == 1: return 'background-color: #D4EDDA; color: #155724; font-weight: bold'
        if isinstance(val, int) and val <= 10: return 'background-color: #FFF3CD; color: #856404'
        return ''

    st.write("### 📋 Rapport des positions")
    st.dataframe(df.style.applymap(color_position, subset=['Position']), use_container_width=True)
    
    # Bouton de téléchargement CSV
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Exporter en CSV", csv, "rankings.csv", "text/csv")