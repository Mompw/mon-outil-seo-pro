import streamlit as st
import requests
from trafilatura import fetch_url, extract
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from fpdf import FPDF
import pandas as pd
import numpy as np

# --- CONFIGURATION ---
ST_TITLE = "SEO Content Analyzer Pro"
SERPER_API_KEY = st.secrets["SERPER_API_KEY"]

# --- DICTIONNAIRES DE CONFIGURATION ---
DICT_PAYS = {
    "France": {"gl": "fr", "hl": "fr", "lang": "fr"},
    "États-Unis": {"gl": "us", "hl": "en", "lang": "en"},
    "Royaume-Uni": {"gl": "gb", "hl": "en", "lang": "en"},
    "Espagne": {"gl": "es", "hl": "es", "lang": "es"},
    "Allemagne": {"gl": "de", "hl": "de", "lang": "de"}
}

STOP_WORDS_DICT = {
    "fr": ['le', 'la', 'les', 'des', 'du', 'un', 'une', 'et', 'en', 'pour', 'que', 'dans', 'est', 'avec', 'sur', 'pour', 'par', 'pas'],
    "en": ['the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'in', 'on', 'at', 'to', 'for', 'with', 'it', 'its']
}

# --- FONCTIONS UTILES ---

def get_serp_links(query, gl, hl):
    url = "https://google.serper.dev/search"
    payload = {"q": query, "gl": gl, "hl": hl}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload)
        return [item['link'] for item in response.json().get('organic', [])[:3]]
    except Exception:
        return []

def get_clean_text(url):
    downloaded = fetch_url(url)
    return extract(downloaded) if downloaded else ""

def count_words(text):
    return len(text.split())

def create_pdf(score, word_count, avg_comp, missing_words):
    pdf = FPDF()
    pdf.add_page()
    def safe_text(text):
        return text.encode('latin-1', 'ignore').decode('latin-1')

    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, safe_text("Rapport d'Optimisation Sémantique SEO"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text(f"Score de Similarité : {score}%"), ln=True)
    pdf.set_font("Helvetica", '', 12)
    pdf.cell(200, 10, safe_text(f"Longueur : {word_count} mots (Cible moy. : {avg_comp})"), ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text("Mots-clés manquants suggérés :"), ln=True)
    pdf.set_font("Helvetica", '', 10)
    words_text = ", ".join(missing_words)
    pdf.multi_cell(0, 10, safe_text(words_text))
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE ---
st.set_page_config(page_title=ST_TITLE, layout="wide")

# Sidebar pour les réglages internationaux
st.sidebar.header("🌍 Configuration Géo")
choix_pays = st.sidebar.selectbox("Pays et Langue cible :", list(DICT_PAYS.keys()))
config_geo = DICT_PAYS[choix_pays]

st.title(f"🛠️ {ST_TITLE}")

col_input, col_res = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("Saisie des données")
    query = st.text_input("Mot-clé cible :", placeholder="ex: best running shoes 2024")
    user_content = st.text_area("Ton contenu :", height=400)
    analyze_btn = st.button("🚀 Analyser")

# --- ANALYSE ---
if analyze_btn and query and user_content:
    with st.spinner(f'Analyse en cours ({choix_pays})...'):
        links = get_serp_links(query, config_geo["gl"], config_geo["hl"])
        
        if not links:
            st.error("Erreur lors de la récupération des données Google.")
        else:
            texts = [get_clean_text(link) for link in links]
            texts = [t for t in texts if t]
            
            # Statistiques mots
            avg_comp_words = int(np.mean([count_words(t) for t in texts])) if texts else 0
            user_word_count = count_words(user_content)
            
            # Analyse sémantique
            current_lang = config_geo["lang"]
            stop_words_list = STOP_WORDS_DICT.get(current_lang, STOP_WORDS_DICT["fr"])
            
            vectorizer = TfidfVectorizer(stop_words=stop_words_list)
            tfidf_matrix = vectorizer.fit_transform(texts + [user_content])
            
            target_vec = np.asarray(tfidf_matrix[:-1].mean(axis=0))
            user_vec = tfidf_matrix[-1]
            semantic_score = round(cosine_similarity(user_vec, target_vec)[0][0] * 100, 1)

            # Mots manquants
            features = vectorizer.get_feature_names_out()
            df_tfidf = pd.DataFrame(tfidf_matrix.toarray(), columns=features)
            top_terms = df_tfidf.iloc[:-1].mean().sort_values(ascending=False).head(15)
            user_presence = df_tfidf.iloc[-1]
            missing_words = [w for w, v in top_terms.items() if user_presence[w] == 0]

            with col_res:
                st.subheader("Résultats de l'analyse")
                m1, m2 = st.columns(2)
                m1.metric("Score Sémantique", f"{semantic_score}%")
                m2.metric("Mots", user_word_count, f"{user_word_count - avg_comp_words} vs concurrents")
                
                chart_data = pd.DataFrame({
                    'Pages': ['Concurrents', 'Ton Texte'],
                    'Mots': [avg_comp_words, user_word_count]
                })
                st.bar_chart(chart_data.set_index('Pages'))

                st.write("### 💡 Mots-clés manquants")
                if missing_words:
                    st.warning(", ".join(missing_words))
                    
                    pdf_data = create_pdf(semantic_score, user_word_count, avg_comp_words, missing_words)
                    st.download_button(
                        label="📥 Télécharger le rapport PDF",
                        data=pdf_data,
                        file_name=f"rapport_seo_{query.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.success("Sémantique au top !")
