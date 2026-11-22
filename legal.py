"""
legal.py : pages « Mentions légales », « Données personnelles » et « Politique des cookies » + liens en pied de la page d'accueil.
Les textes se trouvent dans le dossier legal/ (fichiers Markdown modifiables sans toucher au code).
"""
from pathlib import Path

import streamlit as st

import cookies

DOSSIER = Path(__file__).parent / "legal"
PAGES = {  # clé de page -> (libellé, fichier)
    "mentions": ("Mentions légales", "mentions_legales.md"),
    "donnees": ("Données personnelles", "donnees_personnelles.md"),
    "cookies": ("Politique des cookies", "politique_cookies.md"),
}


def ouvrir(page):
    """Ouvre une page légale ; la page précédente est mémorisée pour le bouton « Retour »."""
    if st.session_state.get("page") not in PAGES:
        st.session_state["page_avant"] = st.session_state.get("page", "accueil")
    st.session_state["page"] = page
    st.query_params["acces"] = page
    st.rerun()


def retour():
    avant = st.session_state.pop("page_avant", "accueil")
    st.session_state["page"] = avant
    if avant == "accueil":
        st.query_params.clear()
    else:
        st.query_params["acces"] = {"medecin": "investigateur"}.get(avant, avant)
    st.rerun()


def est_page_legale():
    return st.session_state.get("page") in PAGES


def afficher():
    """Affiche la page légale demandée."""
    import accueil  # import tardif : accueil.py utilise aussi ce module
    page = st.session_state["page"]
    libelle, fichier = PAGES[page]
    accueil.appliquer_style()
    st.markdown("<style>.st-key-nav_legal button{border-radius:10px;font-weight:600;}</style>", unsafe_allow_html=True)
    _, centre, _ = st.columns([1, 3, 1])
    with centre:
        st.markdown(f'{accueil.logo_html(72)}', unsafe_allow_html=True)
        if st.button("← Retour", key="legal_retour_haut"):
            retour()
        st.title(libelle)
        st.markdown((DOSSIER / fichier).read_text(encoding="utf-8"))
        st.divider()
        with st.container(key="nav_legal"):
            autres = [k for k in PAGES if k != page]
            cols = st.columns(len(autres) + 2)
            for col, k in zip(cols, autres):
                if col.button(PAGES[k][0], key=f"legal_nav_{k}"):
                    ouvrir(k)
            if cols[-2].button("Gérer mes cookies", key="legal_gerer_cookies"):
                cookies.reinitialiser()
                retour()
            if cols[-1].button("← Retour", key="legal_retour_bas", type="primary"):
                retour()


def pied_liens():
    """Liens discrets en bas de la page d'accueil."""
    st.markdown("""<style>
.st-key-pied_legal{margin-top:.4rem;}
.st-key-pied_legal button{background:transparent;border:0;box-shadow:none;color:#5b6b82;text-decoration:underline;font-size:.85rem;padding:.2rem .4rem;}
.st-key-pied_legal button:hover{background:transparent;color:#0086c3;border:0;}
.st-key-pied_legal button p{font-size:.85rem;}
</style>""", unsafe_allow_html=True)
    with st.container(key="pied_legal"):
        cols = st.columns(4, gap="small")
        for col, k in zip(cols, PAGES):
            if col.button(PAGES[k][0], key=f"pied_{k}"):
                ouvrir(k)
        if cols[3].button("Gérer mes cookies", key="pied_gerer_cookies"):
            cookies.reinitialiser()
            st.rerun()
