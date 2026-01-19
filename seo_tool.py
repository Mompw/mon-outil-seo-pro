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

DICT_PAYS = {
    "France": {"gl": "fr", "hl": "fr", "lang": "fr"},
    "États-Unis": {"gl": "us", "hl": "en", "lang": "en"},
    "Royaume-Uni": {"gl": "gb", "hl": "en", "lang": "en"},
    "Espagne": {"gl": "es", "hl": "es", "lang": "es"},
    "Allemagne": {"gl": "de", "hl": "de", "lang": "de"}
}

STOP_WORDS_DICT = {
    "fr": ['le', 'la', 'les', 'des', 'du', 'un', 'une', 'et', 'en', 'pour', 'que', 'dans', 'est', 'avec', 'sur', 'pour', 'par', 'pas', 'plus', 'ce', 'cette', 'ont', 'tout', 'tous', 'fait'],
    "en": ['the', 'a', 'an', 'and', 'or', 'but', 'if', 'then', 'else', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'in', 'on', 'at', 'to', 'for', 'with', 'it', 'its', 'of', 'by', 'this', 'that']
}

# --- FONCTIONS ---

def get_serp_data(query, gl, hl):
    """Récupère le Top 10 (1 crédit)"""
    url = "https://google.serper.dev/search"
    payload = {"q": query, "gl": gl, "hl": hl}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload)
        data = response.json()
        links = [item['link'] for item in data.get('organic', [])[:10]]
        return links
    except:
        return []

def get_clean_text(url):
    downloaded = fetch_url(url)
    return extract(downloaded) if downloaded else ""

def count_words(text):
    return len(text.split())

def create_pdf(score, word_count, avg_comp, missing_words, volume):
    pdf = FPDF()
    pdf.add_page()
    def safe_text(text): return text.encode('latin-1', 'ignore').decode('latin-1')
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, safe_text("Rapport d'Optimisation Sémantique SEO"), ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text(f"Mot-cle cible : {query}"), ln=True)
    pdf.cell(200, 10, safe_text(f"Volume de recherche : {volume}"), ln=True)
    pdf.cell(200, 10, safe_text(f"Score de Similarite : {score}%"), ln=True)
    pdf.cell(200, 10, safe_text(f"Longueur : {word_count} mots (Moyenne Top 10 : {avg_comp})"), ln=True)
    pdf.ln(10)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text("Mots-cles manquants (Top 20) :"), ln=True)
    pdf.set_font("Helvetica", '', 10)
    pdf.multi_cell(0, 10, safe_text(", ".join(missing_words)))
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE ---
st.set_page_config(page_title=ST_TITLE, layout="wide")

with st.sidebar:
    st.header("🌍 Configuration")
    choix_pays = st.selectbox("Pays cible :", list(DICT_PAYS.keys()))
    config_geo = DICT_PAYS[choix_pays]
    
    st.divider()
    st.header("📈 Volume de recherche")
    mode_volume = st.radio("Source du volume :", ["Manuel (Semrush)", "Aucun"])
    
    vol_display = "N/A"
    if mode_volume == "Manuel (Semrush)":
        vol_display = st.text_input("Saisir le volume (ex: 1200) :", value="0")
    
    st.divider()
    st.info("💡 Analyse Top 10 activée (1 crédit Serper)")

st.title(f"🛠️ {ST_TITLE}")

col_input, col_res = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("Saisie des données")
    query = st.text_input("Mot-clé cible :", placeholder="ex: assurance auto")
    user_content = st.text_area("Contenu à analyser :", height=400)
    analyze_btn = st.button("🚀 Lancer l'analyse Top 10")

# --- ANALYSE ---
if analyze_btn and query and user_content:
    with st.spinner('Scraping et analyse sémantique du Top 10...'):
        # 1. Récupération des liens (1 crédit)
        links = get_serp_data(query, config_geo["gl"], config_geo["hl"])
        
        if not links:
            st.error("Impossible de récupérer les résultats Google.")
        else:
            # 2. Scraping des 10 pages
            texts = [get_clean_text(link) for link in links]
            texts = [t for t in texts if t]
            
            avg_comp_words = int(np.mean([count_words(t) for t in texts])) if texts else 0
            user_word_count = count_words(user_content)
            
            # 3. Calcul Sémantique
            current_lang = config_geo["lang"]
            stop_words_list = STOP_WORDS_DICT.get(current_lang, STOP_WORDS_DICT["fr"])
            vectorizer = TfidfVectorizer(stop_words=stop_words_list)
            tfidf_matrix = vectorizer.fit_transform(texts + [user_content])
            
            target_vec = np.asarray(tfidf_matrix[:-1].mean(axis=0))
            user_vec = tfidf_matrix[-1]
            semantic_score = round(cosine_similarity(user_vec, target_vec)[0][0] * 100, 1)

            # 4. Mots manquants
            features = vectorizer.get_feature_names_out()
            df_tfidf = pd.DataFrame(tfidf_matrix.toarray(), columns=features)
            top_terms = df_tfidf.iloc[:-1].mean().sort_values(ascending=False).head(20)
            user_presence = df_tfidf.iloc[-1]
            missing_words = [w for w, v in top_terms.items() if user_presence[w] == 0]

            with col_res:
                st.subheader("Tableau de bord")
                m1, m2, m3 = st.columns(3)
                m1.metric("Score Sémantique", f"{semantic_score}%")
                m2.metric("Tes Mots", user_word_count)
                m3.metric("Volume (Semrush)", vol_display)

                st.write("### Comparaison de longueur")
                chart_data = pd.DataFrame({
                    'Pages': ['Moyenne Top 10', 'Ton Texte'],
                    'Mots': [avg_comp_words, user_word_count]
                })
                st.bar_chart(chart_data.set_index('Pages'))

                st.write("### 💡 Mots-clés manquants (priorité Top 10)")
                if missing_words:
                    st.warning(", ".join(missing_words))
                    
                    # Génération du PDF avec passage du volume
                    pdf_data = create_pdf(semantic_score, user_word_count, avg_comp_words, missing_words, vol_display)
                    st.download_button(
                        label="📥 Télécharger le rapport PDF",
                        data=pdf_data,
                        file_name=f"rapport_seo_{query.replace(' ', '_')}.pdf",
                        mime="application/pdf"
                    )
                else:
                    st.success("Sémantique parfaite !")
