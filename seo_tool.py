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
# S'assure que la clé est bien dans .streamlit/secrets.toml
SERPER_API_KEY = st.secrets["SERPER_API_KEY"]

# --- FONCTIONS UTILES ---

def get_serp_links(query):
    """Récupère les 3 premiers liens sur Google"""
    url = "https://google.serper.dev/search"
    payload = {"q": query, "gl": "fr", "hl": "fr"}
    headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
    try:
        response = requests.post(url, headers=headers, json=payload)
        return [item['link'] for item in response.json().get('organic', [])[:3]]
    except Exception:
        return []

def get_clean_text(url):
    """Extrait le texte propre d'une URL"""
    downloaded = fetch_url(url)
    return extract(downloaded) if downloaded else ""

def count_words(text):
    """Compte le nombre de mots"""
    return len(text.split())

def create_pdf(score, word_count, avg_comp, missing_words):
    """Génère le rapport PDF avec gestion des accents"""
    pdf = FPDF()
    pdf.add_page()
    
    # Encodage sécurisé pour éviter les erreurs de caractères
    def safe_text(text):
        return text.encode('latin-1', 'ignore').decode('latin-1')

    # Titre
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(200, 10, safe_text("Rapport d'Optimisation Sémantique SEO"), ln=True, align='C')
    pdf.ln(10)
    
    # Score Global
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text(f"Score de Similarité : {score}%"), ln=True)
    pdf.set_font("Helvetica", '', 12)
    pdf.cell(200, 10, safe_text(f"Longueur de ton texte : {word_count} mots"), ln=True)
    pdf.cell(200, 10, safe_text(f"Moyenne concurrents : {avg_comp} mots"), ln=True)
    pdf.ln(10)
    
    # Liste des mots
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(200, 10, safe_text("Mots-clés à intégrer en priorité :"), ln=True)
    pdf.set_font("Helvetica", '', 10)
    
    clean_words = [w.replace('`', '') for w in missing_words]
    words_text = ", ".join(clean_words)
    pdf.multi_cell(0, 10, safe_text(words_text))
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFACE STREAMLIT ---
st.set_page_config(page_title=ST_TITLE, layout="wide")
st.title(f"🛠️ {ST_TITLE}")

col_input, col_res = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("Saisie des données")
    query = st.text_input("Mot-clé cible :", placeholder="ex: meilleur robot cuisine 2024")
    user_content = st.text_area("Colle ton texte ici :", height=400)
    analyze_btn = st.button("🚀 Analyser maintenant")

# --- LOGIQUE D'ANALYSE ---
if analyze_btn and query and user_content:
    with st.spinner('Analyse concurrentielle en cours...'):
        # 1. Scraping
        links = get_serp_links(query)
        if not links:
            st.error("Impossible de récupérer les résultats Google.")
        else:
            competitors_texts = [get_clean_text(link) for link in links]
            competitors_texts = [t for t in competitors_texts if t]
            
            # 2. Analyse de longueur
            comp_word_counts = [count_words(t) for t in competitors_texts]
            avg_comp_words = int(np.mean(comp_word_counts)) if comp_word_counts else 0
            user_word_count = count_words(user_content)
            
            # 3. Score Sémantique
            stop_words_fr = ['le', 'la', 'les', 'des', 'du', 'un', 'une', 'et', 'en', 'pour', 'que', 'dans', 'est']
            vectorizer = TfidfVectorizer(stop_words=stop_words_fr)
            tfidf_matrix = vectorizer.fit_transform(competitors_texts + [user_content])
            
            target_vector = np.asarray(tfidf_matrix[:-1].mean(axis=0))
            user_vector = tfidf_matrix[-1]
            semantic_score = round(cosine_similarity(user_vector, target_vector)[0][0] * 100, 1)

            # 4. Extraction des mots manquants
            feature_names = vectorizer.get_feature_names_out()
            df_tfidf = pd.DataFrame(tfidf_matrix.toarray(), columns=feature_names)
            comp_importance = df_tfidf.iloc[:-1].mean().sort_values(ascending=False).head(15)
            user_presence = df_tfidf.iloc[-1]
            missing_words = [word for word, val in comp_importance.items() if user_presence[word] == 0]

            # --- AFFICHAGE DES RÉSULTATS ---
            with col_res:
                st.subheader("Tableau de Bord SEO")
                
                m1, m2 = st.columns(2)
                m1.metric("Score Sémantique", f"{semantic_score}%")
                m2.metric("Tes mots", user_word_count, delta=user_word_count - avg_comp_words)
                
                st.write("### Comparaison de la longueur")
                chart_data = pd.DataFrame({
                    'Pages': ['Moyenne Top 3', 'Ton Texte'],
                    'Mots': [avg_comp_words, user_word_count]
                })
                st.bar_chart(chart_data.set_index('Pages'))

                st.write("### 💡 Mots-clés manquants")
                if missing_words:
                    st.warning(", ".join(missing_words))
                    
                    # Génération du PDF
                    try:
                        pdf_data = create_pdf(semantic_score, user_word_count, avg_comp_words, missing_words)
                        st.download_button(
                            label="📥 Télécharger le rapport PDF",
                            data=pdf_data,
                            file_name=f"rapport_seo_{query.replace(' ', '_')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as e:
                        st.error(f"Erreur PDF : {e}")
                else:
                    st.success("Sémantique parfaite !")