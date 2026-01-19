import streamlit as st
import requests
from trafilatura import fetch_url, extract
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fpdf import FPDF
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
ST_TITLE = "SEO Content Analyzer Pro"
SERPER_API_KEY = st.secrets["SERPER_API_KEY"]

DICT_PAYS = {
    "France": {"gl": "fr", "hl": "fr", "lang": "fr"},
    "États-Unis": {"gl": "us", "hl": "en", "lang": "en"},
    "Royaume-Uni": {"gl": "gb", "hl": "en", "lang": "en"},
    "Espagne": {"gl": "es", "hl": "es", "lang": "es"},
    "Allemagne": {"gl": "de", "hl": "de", "lang": "de"}
}

STOP_WORDS_DICT = {
    "fr": ['le', 'la', 'les', 'des', 'du', 'un', 'une', 'et', 'en', 'pour', 'que', 'dans', 'est', 'avec', 'sur', 'pour', 'par', 'pas', 'plus', 'ce', 'cette', 'ont', 'tout', 'tous', 'fait', 'faire', 'etre', 'plus'],
    "en": ['the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'in', 'on', 'at', 'to', 'for', 'with', 'it', 'its', 'of', 'by', 'this', 'that']
}

# --- FONCTIONS ---

def get_serp_full_data(query, gl, hl):
    url = "https://google.serper.dev/search"
    payload = {"q": query, "gl": gl, "hl": hl}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        links = [item['link'] for item in data.get('organic', [])[:10]]
        api_vol = data.get('searchInformation', {}).get('totalResults', "0")
        return links, api_vol
    except:
        return [], "0"

def get_page_data(url):
    """Extrait le texte ET les balises Hn"""
    try:
        downloaded = fetch_url(url)
        if not downloaded: return "", []
        
        # Texte propre pour TF-IDF
        clean_text = extract(downloaded)
        
        # Balises Hn avec BeautifulSoup
        soup = BeautifulSoup(downloaded, 'html.parser')
        hn_tags = []
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            hn_tags.append(f"{tag.name.upper()}: {tag.get_text().strip()}")
            
        return clean_text, hn_tags[:15] # Limite à 15 titres par site
    except:
        return "", []

def get_difficulty_label(total_results):
    try:
        res_count = int(str(total_results).replace(',', '').replace(' ', ''))
        if res_count > 10000000: return "🔴 Très Élevée", "red"
        if res_count > 1000000: return "🟠 Élevée", "orange"
        if res_count > 100000: return "🟡 Moyenne", "blue"
        return "🟢 Faible", "green"
    except:
        return "⚪ Inconnue", "gray"

# --- INTERFACE ---
st.set_page_config(page_title=ST_TITLE, layout="wide")

with st.sidebar:
    st.header("🌍 Paramètres")
    choix_pays = st.selectbox("Pays cible :", list(DICT_PAYS.keys()))
    config_geo = DICT_PAYS[choix_pays]
    
    st.divider()
    st.header("📊 Volume")
    mode_volume = st.radio("Source :", ["Manuel (Semrush)", "Auto (Serper API)", "Aucun"])
    vol_input = "0"
    if mode_volume == "Manuel (Semrush)":
        vol_input = st.text_input("Saisir volume :", value="0")

st.title(f"🛠️ {ST_TITLE}")

col_input, col_res = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("Saisie")
    query = st.text_input("Mot-clé cible :", placeholder="ex: meilleur matelas 2024")
    user_content = st.text_area("Ton texte :", height=400)
    analyze_btn = st.button("🚀 Analyser Top 10 + Hn")

if analyze_btn and query and user_content:
    with st.spinner('Récupération et analyse des 10 concurrents...'):
        links, api_vol = get_serp_full_data(query, config_geo["gl"], config_geo["hl"])
        
        if not links:
            st.error("Échec de la récupération SERP.")
        else:
            all_texts = []
            all_hn = {}
            
            for i, link in enumerate(links):
                txt, hn = get_page_data(link)
                if txt:
                    all_texts.append(txt)
                    all_hn[f"Concurrent {i+1}"] = {"url": link, "hn": hn}

            # Calculs
            avg_comp_words = int(np.mean([len(t.split()) for t in all_texts])) if all_texts else 0
            user_word_count = len(user_content.split())
            
            # TF-IDF
            current_lang = config_geo["lang"]
            vectorizer = TfidfVectorizer(stop_words=STOP_WORDS_DICT.get(current_lang, STOP_WORDS_DICT["fr"]))
            tfidf_matrix = vectorizer.fit_transform(all_texts + [user_content])
            
            semantic_score = round(cosine_similarity(tfidf_matrix[-1], np.asarray(tfidf_matrix[:-1].mean(axis=0)))[0][0] * 100, 1)
            
            # Mots manquants
            features = vectorizer.get_feature_names_out()
            top_terms = pd.DataFrame(tfidf_matrix.toarray(), columns=features).iloc[:-1].mean().sort_values(ascending=False).head(20)
            user_presence = pd.DataFrame(tfidf_matrix.toarray(), columns=features).iloc[-1]
            missing_words = [w for w, v in top_terms.items() if user_presence[w] == 0]

            with col_res:
                st.subheader("Résultats")
                m1, m2, m3 = st.columns(3)
                m1.metric("Similarité", f"{semantic_score}%")
                m2.metric("Tes Mots", user_word_count)
                
                # Gestion Difficulté / Volume
                if mode_volume == "Auto (Serper API)":
                    label, color = get_difficulty_label(api_vol)
                    st.markdown(f"**Difficulté :** :{color}[{label}] ({api_vol} rés.)")
                else:
                    m3.metric("Volume", vol_input if mode_volume == "Manuel (Semrush)" else "Ignoré")

                st.write("### 💡 Mots-clés manquants")
                st.warning(", ".join(missing_words) if missing_words else "Sémantique parfaite !")

                # NOUVEAU : STRUCTURE HN
                st.write("### 📂 Structure des concurrents (H1-H3)")
                with st.expander("Voir le plan détaillé du Top 10"):
                    for name, data in all_hn.items():
                        st.markdown(f"**[{name}]({data['url']})**")
                        if data['hn']:
                            for h in data['hn']:
                                st.text(h)
                        else:
                            st.caption("Aucun titre détecté.")
                        st.divider()

                st.bar_chart(pd.DataFrame({'Pages': ['Moyenne Top 10', 'Toi'], 'Mots': [avg_comp_words, user_word_count]}).set_index('Pages'))
