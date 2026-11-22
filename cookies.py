"""
cookies.py : bandeau de consentement aux cookies (« Accepter tous » / « Essentiels uniquement »).

- Le choix est mémorisé 6 mois dans UN cookie essentiel, `semo_cookie_consent` (valeurs : all | essential), comme l'indique la politique des cookies.
- Tant qu'aucun choix n'est fait, le bandeau est affiché en bas de toutes les pages ; les deux boutons ont la même présentation
  (refuser aussi facilement qu'accepter).
- L'application elle-même ne dépose aucun cookie de mesure d'audience : si un outil (ex. Matomo) est ajouté par l'hébergeur,
  il ne doit être chargé que si `mesure_audience_autorisee()` est vrai (choix « all »).
- Lecture du cookie : st.context.cookies (Streamlit >= 1.37). Écriture : petit script JS via st.html(unsafe_allow_javascript=True) (Streamlit ne sait pas écrire de cookie).
"""
import streamlit as st

COOKIE = "semo_cookie_consent"
DUREE_S = 180 * 24 * 3600  # 6 mois
TEXTE = ("<b>🍪 Cookies</b> — Ce site utilise des cookies <b>essentiels</b> à son fonctionnement (dont la mémorisation de votre choix pendant 6 mois). "
         "D’éventuels cookies optionnels ne seraient déposés <b>qu’avec votre accord</b>. Vous pouvez accepter tous les cookies ou n’autoriser que les essentiels. "
         "Vous pourrez modifier ce choix à tout moment depuis le pied de page de l’accueil.")

STYLE = """<style>
.st-key-cookie_banner{position:fixed;left:0;right:0;bottom:0;z-index:99999;background:#fff;border-top:4px solid #0086c3;
 box-shadow:0 -14px 40px -12px rgba(11,31,58,.40);padding:1rem 1.5rem 1.1rem;max-height:70vh;overflow:auto;}
.st-key-cookie_banner p{margin:0 0 .6rem;font-size:.93rem;line-height:1.5;color:#0b1f3a;}
.st-key-cookie_banner button{width:100%;border:1.5px solid #0086c3;border-radius:10px;background:#fff;color:#0b1f3a;font-weight:700;padding:.55rem .8rem;}
.st-key-cookie_banner button:hover{background:#eaf6fd;border-color:#0086c3;color:#0b1f3a;}
.block-container{padding-bottom:11rem !important;}
</style>"""


def choix():
    """'all', 'essential' ou None (pas encore de choix). Lu une fois dans le cookie, puis tenu en session."""
    if "cookies_choix" not in st.session_state:
        try:
            v = st.context.cookies.get(COOKIE)
        except Exception:
            v = None
        st.session_state["cookies_choix"] = v if v in ("all", "essential") else None
    return st.session_state["cookies_choix"]


def mesure_audience_autorisee():
    return choix() == "all"


def _enregistrer(valeur):
    """valeur : 'all' | 'essential' | None (efface le choix). Le cookie est écrit au prochain affichage (voir banniere)."""
    st.session_state["cookies_choix"] = valeur
    st.session_state["_cookie_a_ecrire"] = valeur or ""


def reinitialiser():
    """« Gérer mes cookies » : efface le choix, le bandeau réapparaît."""
    _enregistrer(None)


def _ecrire_cookie(valeur):
    """Écrit (ou efface, si valeur == '') le cookie de choix. Streamlit n'a pas d'API d'écriture de cookie : petit script JS."""
    age = DUREE_S if valeur else 0
    ecriture = (f"document.cookie='{COOKIE}={valeur}; max-age={age}; path=/; SameSite=Lax'"
                "+(location.protocol==='https:'?'; Secure':'');")
    try:   # Streamlit récent : script exécuté dans la page elle-même
        st.html(f"<script>try{{{ecriture}}}catch(e){{}}</script>", unsafe_allow_javascript=True)
    except TypeError:   # anciennes versions : iframe (st.components.v1.html, en cours de retrait par Streamlit)
        import streamlit.components.v1 as components
        components.html(f"<script>try{{var document=window.parent.document,location=window.parent.location;{ecriture}}}catch(e){{}}</script>", height=0)


def banniere(ouvrir_politique=None):
    """À appeler en tête de chaque exécution (après la config de page). `ouvrir_politique` : fonction ouvrant la page « Politique des cookies »."""
    if "_cookie_a_ecrire" in st.session_state:
        _ecrire_cookie(st.session_state.pop("_cookie_a_ecrire"))
    if choix() is not None:
        return
    st.markdown(STYLE, unsafe_allow_html=True)
    with st.container(key="cookie_banner"):
        st.markdown(f"<p>{TEXTE}</p>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3, gap="small")
        c1.button("Essentiels uniquement", key="ck_essentiels", on_click=_enregistrer, args=("essential",))
        c2.button("Accepter tous les cookies", key="ck_tous", on_click=_enregistrer, args=("all",))
        if ouvrir_politique is not None and c3.button("Politique des cookies", key="ck_politique"):
            ouvrir_politique("cookies")
