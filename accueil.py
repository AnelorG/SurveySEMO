"""
accueil.py : page d'accueil de la plateforme + habillage graphique commun.
Pour changer les textes, modifiez le bloc « À MODIFIER » ci-dessous.
Pour afficher le logo : déposez un fichier dont le nom commence par "logo" dans le dossier assets/.
"""
import base64
import glob
import math
import os
from functools import lru_cache

import streamlit as st

DOSSIER = os.path.dirname(os.path.abspath(__file__))

# ============================ À MODIFIER ============================
ETABLISSEMENT = "CHU Grenoble Alpes"
TITRE = ("PROFIL", "SANTE")   # le 2e mot s'affiche en couleur
SURTITRE = "Questionnaires"
SOUS_TITRE = "Vous êtes invité(e) à répondre à des questionnaires sur votre mode de vie. Ces informations seront transmises à votre médecin neurologue."
PIED_DE_PAGE = "Centre Hospitalier Universitaire Grenoble Alpes · Vos données sont confidentielles et protégées."
AFFICHER_ETAPES = True            # bandeau « comment ça marche » (3 étapes)
# ====================================================================

TITRE_PAGE = f"{TITRE[0]} {TITRE[1]}".capitalize() + f" · {ETABLISSEMENT}"

# Icônes (tracés « Lucide », licence ISC) : (libellé sur 2 lignes, dessin, couleur)
DETERMINANTS = [
    (("Sommeil",), '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>', "#4f46e5"),
    (("Alimentation",), '<path d="M12 20.94c1.5 0 2.75 1.06 4 1.06 3 0 6-8 6-12.22A4.91 4.91 0 0 0 17 5c-2.22 0-4 1.44-5 2-1-.56-2.78-2-5-2a4.9 4.9 0 0 0-5 4.78C2 14 5 22 8 22c1.25 0 2.5-1.06 4-1.06Z"/><path d="M10 2c1 .5 2 2 2 5"/>', "#0d9488"),
    (("Activité", "physique"), '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>', "#0284c7"),
    (("Stimulation", "cognitive"), '<path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>', "#7c3aed"),
    (("Bien-être", "psychosocial"), '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>', "#059669"),
    (("Environnement",), '<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>', "#2563eb"),
    (("Tabac", "& alcool"), '<circle cx="12" cy="12" r="10"/><path d="m4.9 4.9 14.2 14.2"/>', "#0891b2"),
    (("Santé", "métabolique"), '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>', "#6d28d9"),
]
COEUR = '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>'


def _mini(css):
    return " ".join(css.split())


@lru_cache(maxsize=1)
def _logo_uri():
    mimes = {"png": "image/png", "svg": "image/svg+xml", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
    for ext in mimes:
        for f in sorted(glob.glob(os.path.join(DOSSIER, "assets", f"logo*.{ext}"))):
            with open(f, "rb") as fh:
                return f"data:{mimes[ext]};base64," + base64.b64encode(fh.read()).decode()
    return None


def logo_html(hauteur=54):
    uri = _logo_uri()
    if uri:
        return f'<img class="logo" src="{uri}" alt="{ETABLISSEMENT}" style="height:{hauteur}px">'
    return '<div class="wordmark"><i></i><span>' + ETABLISSEMENT + "</span></div>"


STYLE_COMMUN = _mini("""
:root{--f:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;--ink:#0b1f3a;--muted:#5b6b82;--accent:#009EE0;--accent2:#3b4cca;--line:#e1e7f0;}
.stApp{background:radial-gradient(900px 520px at 88% -8%,rgba(0,158,224,.14),transparent 60%),
 radial-gradient(800px 520px at -8% 108%,rgba(59,76,202,.10),transparent 60%),#f6f8fb;}
header[data-testid="stHeader"]{background:transparent;}
#MainMenu,footer{visibility:hidden;}
div[data-testid="stForm"]{background:rgba(255,255,255,.85);border:1px solid var(--line);border-radius:20px;
 padding:1.4rem 1.4rem 1rem;box-shadow:0 24px 48px -32px rgba(11,31,58,.35);}
.stButton button,.stFormSubmitButton button{border-radius:12px;font-weight:600;font-family:var(--f);}.stFormSubmitButton,.stFormSubmitButton>div{width:100% !important;}.stFormSubmitButton button{width:100%;background:linear-gradient(135deg,#009EE0,#3b4cca);color:#fff !important;border:0;padding:.7rem 1rem;}.stFormSubmitButton button p{color:#fff !important;}.st-key-retour_login button,.st-key-retour_admin button{border:0;background:transparent;color:var(--muted);padding-left:0;}
.logo{width:auto;display:block;}
.wordmark{display:flex;align-items:center;gap:10px;font-weight:800;letter-spacing:-.02em;color:var(--ink);font-size:1.15rem;
 font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;}
.wordmark i{width:34px;height:34px;border-radius:10px;display:inline-block;background:linear-gradient(135deg,var(--accent),var(--accent2));}
.micro{font-family:var(--f);font-size:.84rem;color:var(--muted);margin:.45rem 0 0;line-height:1.35;text-align:center;}
.centre-titre{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);
 font-weight:800;font-size:1.9rem;letter-spacing:-.03em;margin:1.2rem 0 .3rem;}
.centre-texte{font-family:var(--f);color:var(--muted);margin:0 0 1.1rem;line-height:1.5;}
""")

STYLE_ACCUEIL = _mini("""
.block-container{max-width:1180px;padding-top:1.6rem;padding-bottom:2rem;}
.hero,.etapes,.pied,.topbar,.infocard{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;}
.topbar{margin-bottom:1.6rem;}
.eyebrow{display:inline-block;padding:6px 14px;border-radius:999px;background:rgba(0,158,224,.12);color:#0077b6;
 font-weight:700;font-size:.78rem;letter-spacing:.09em;text-transform:uppercase;}
.titre{font-size:clamp(2.6rem,5.4vw,4.4rem);line-height:1.02;letter-spacing:-.04em;color:var(--ink);font-weight:800;margin:1rem 0 1.1rem;}
.titre span{background:linear-gradient(100deg,var(--accent),var(--accent2));-webkit-background-clip:text;background-clip:text;color:transparent;}
.lead{font-size:1.15rem;color:var(--muted);line-height:1.6;max-width:32rem;margin:0 0 1.8rem;}
.st-key-btn_patient,.st-key-btn_medecin,.st-key-btn_patient>div,.st-key-btn_medecin>div{width:100% !important;}.st-key-btn_patient button,.st-key-btn_medecin button{font-family:var(--f);}.st-key-btn_patient button{background:linear-gradient(135deg,#009EE0,#3b4cca);color:#fff !important;border:0;border-radius:14px;
 padding:.95rem 1.2rem;font-weight:700;width:100%;box-shadow:0 14px 28px -14px rgba(59,76,202,.7);transition:transform .15s,box-shadow .15s;}
.st-key-btn_patient button:hover{transform:translateY(-2px);box-shadow:0 18px 32px -14px rgba(59,76,202,.8);color:#fff !important;border:0;}
.st-key-btn_patient button p,.st-key-btn_medecin button p{font-size:1.02rem;font-weight:700;}
.st-key-btn_patient button p{color:#fff !important;}
.st-key-btn_medecin button{background:rgba(255,255,255,.7);color:var(--ink) !important;border:1.5px solid #c5d0e0;border-radius:14px;
 padding:.95rem 1.2rem;width:100%;transition:transform .15s,border-color .15s,background .15s;}
.st-key-btn_medecin button:hover{transform:translateY(-2px);border-color:var(--accent);background:#fff;color:var(--ink) !important;}
.infocard{background:rgba(255,255,255,.72);border:1px solid var(--line);border-radius:32px;padding:6px;
 box-shadow:0 40px 70px -40px rgba(11,31,58,.30);backdrop-filter:blur(6px);}
.info{width:100%;height:auto;display:block;}
.info .lab{font:600 23px ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;fill:#0b1f3a;}
.info .orbite{transform-box:fill-box;transform-origin:center;animation:tourne 120s linear infinite;}
.info .halo{transform-box:fill-box;transform-origin:center;animation:respire 4.5s ease-in-out infinite;}
.info .noeud{opacity:0;transform-box:fill-box;transform-origin:center;animation:apparait .8s cubic-bezier(.2,.8,.2,1) forwards;}
@keyframes tourne{to{transform:rotate(360deg);}}
@keyframes respire{0%,100%{transform:scale(1);opacity:.35;}50%{transform:scale(1.08);opacity:.12;}}
@keyframes apparait{from{opacity:0;transform:scale(.82);}to{opacity:1;transform:none;}}
@media (prefers-reduced-motion:reduce){.info *{animation:none !important;}.info .noeud{opacity:1;}}
.etapes{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:2.4rem;}
.etape{display:flex;gap:14px;align-items:flex-start;padding:18px 20px;border:1px solid var(--line);border-radius:20px;background:rgba(255,255,255,.6);}
.etape b{flex:0 0 34px;height:34px;border-radius:50%;display:grid;place-items:center;color:#fff;font-size:.95rem;
 background:linear-gradient(135deg,var(--accent),var(--accent2));}
.etape strong{display:block;color:var(--ink);margin-bottom:2px;}
.etape span{color:var(--muted);font-size:.92rem;line-height:1.45;}
@media (max-width:760px){.etapes{grid-template-columns:1fr;}}
.pied{text-align:center;color:#8593a8;font-size:.82rem;margin-top:2.2rem;}
""")


def appliquer_style(accueil=False):
    css = STYLE_COMMUN + (STYLE_ACCUEIL if accueil else "")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def infographie_svg():
    """Roue des déterminants de la santé (SVG autonome, sans ressource externe)."""
    W, H, cx, cy, R, r = 880, 720, 440, 360, 215, 38
    n = len(DETERMINANTS)
    s = [f'<svg class="info" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
         f'aria-label="Les déterminants de la santé">',
         '<defs><linearGradient id="gc" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#009EE0"/>'
         '<stop offset="1" stop-color="#3b4cca"/></linearGradient>'
         '<filter id="sh" x="-40%" y="-40%" width="180%" height="190%"><feDropShadow dx="0" dy="8" stdDeviation="9" '
         'flood-color="#0b1f3a" flood-opacity=".15"/></filter></defs>',
         f'<circle class="orbite" cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="#a9b7cb" stroke-width="1.6" '
         f'stroke-dasharray="1 10" stroke-linecap="round"/>']
    noeuds = []
    for i, (lignes, icone, col) in enumerate(DETERMINANTS):
        a = math.radians(-90 + i * 360 / n)
        c, sn = math.cos(a), math.sin(a)
        nx, ny = cx + R * c, cy + R * sn
        s.append(f'<line x1="{cx + 108 * c:.1f}" y1="{cy + 108 * sn:.1f}" x2="{cx + (R - r - 6) * c:.1f}" '
                 f'y2="{cy + (R - r - 6) * sn:.1f}" stroke="{col}" stroke-opacity=".35" stroke-width="2" stroke-linecap="round"/>')
        g = [f'<g class="noeud" style="animation-delay:{0.25 + 0.12 * i:.2f}s">',
             f'<circle cx="{nx:.1f}" cy="{ny:.1f}" r="{r}" fill="#fff" stroke="{col}" stroke-opacity=".35" stroke-width="2" filter="url(#sh)"/>',
             f'<g transform="translate({nx - 17:.1f},{ny - 17:.1f}) scale(1.4167)" fill="none" stroke="{col}" '
             f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{icone}</g>']
        k = len(lignes)
        if abs(c) < 0.3:                                  # haut / bas : texte centré
            anchor, lx = "middle", nx
            y0 = ny - r - 16 - (k - 1) * 26 if sn < 0 else ny + r + 30
        else:                                             # côtés : texte à gauche ou à droite
            anchor = "start" if c > 0 else "end"
            lx = nx + (r + 14) * (1 if c > 0 else -1)
            y0 = ny - (k - 1) * 13 + 8
        tsp = "".join(f'<tspan x="{lx:.1f}" y="{y0 + j * 26:.1f}">{ligne.replace("&", "&amp;")}</tspan>'
                      for j, ligne in enumerate(lignes))
        g.append(f'<text class="lab" text-anchor="{anchor}">{tsp}</text></g>')
        noeuds.append("".join(g))
    s.append(f'<circle class="halo" cx="{cx}" cy="{cy}" r="124" fill="url(#gc)" opacity=".25"/>')
    s.append(f'<circle cx="{cx}" cy="{cy}" r="100" fill="url(#gc)" filter="url(#sh)"/>')
    s.append(f'<g transform="translate({cx - 24},{cy - 66}) scale(2)" fill="none" stroke="#fff" stroke-width="1.8" '
             f'stroke-linecap="round" stroke-linejoin="round">{COEUR}</g>')
    s.append(f'<text x="{cx}" y="{cy + 26}" text-anchor="middle" fill="#fff" style="font:700 30px ui-sans-serif,system-ui,'
             f'-apple-system,Segoe UI,Roboto,Arial,sans-serif">Votre</text>')
    s.append(f'<text x="{cx}" y="{cy + 60}" text-anchor="middle" fill="#fff" style="font:700 30px ui-sans-serif,system-ui,'
             f'-apple-system,Segoe UI,Roboto,Arial,sans-serif">santé</text>')
    s += noeuds
    s.append("</svg>")
    return "".join(s)


def entete_connexion(titre, texte):
    return (f'{logo_html(72)}<div class="centre-titre">{titre}</div><p class="centre-texte">{texte}</p>')


def afficher(aller):
    """Page d'accueil. `aller("patient")` / `aller("medecin")` changent de page."""
    appliquer_style(accueil=True)
    st.markdown(f'<div class="topbar">{logo_html(88)}</div>', unsafe_allow_html=True)
    gauche, droite = st.columns([1.05, 1], gap="large", vertical_alignment="center")
    with gauche:
        st.markdown(
            f'<div class="hero"><span class="eyebrow">{SURTITRE}</span>'
            f'<div class="titre" role="heading" aria-level="1">{TITRE[0]}<br><span>{TITRE[1]}</span></div>'
            f'<p class="lead">{SOUS_TITRE}</p></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2, gap="small")
        with c1:
            if st.button("Accès Participant  →", key="btn_patient"):
                aller("patient")
            st.markdown('<p class="micro">Je réponds aux questionnaires<br></p>', unsafe_allow_html=True)
        with c2:
            if st.button("Accès Médecin", key="btn_medecin"):
                aller("medecin")
            st.markdown('<p class="micro">Accès réservé<br></p>', unsafe_allow_html=True)
    with droite:
        st.markdown(f'<div class="infocard">{infographie_svg()}</div>', unsafe_allow_html=True)
    if AFFICHER_ETAPES:
        st.markdown(
            '<div class="etapes">'
            '<div class="etape"><b>1</b><div><strong>Connectez vous</strong><span>Munissez-vous de votre numéro de participant (PXXX) et entrez dans votre espace sécurisé.</span></div></div>'
            '<div class="etape"><b>2</b><div><strong>Répondez aux questions</strong><span>Prenez tout le temps dont vous avez besoin pour répondre. Vous pouvez compléter les questionnaires en plusieurs fois.</span></div></div>'
            '<div class="etape"><b>3</b><div><strong>Repassez les questionnaires</strong><span>Si vous le souhaitez, reconnectez-vous et terminez/repassez les questionnaires.</span></div></div>'
            '</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="pied">{PIED_DE_PAGE}</div>', unsafe_allow_html=True)
