"""
rendu_html.py : produit le MÊME rapport de synthèse que celui du patient, sous forme d'un fichier HTML autonome
(graphiques interactifs inclus, utilisable hors connexion ; Ctrl+P > « Enregistrer au format PDF » pour un PDF).
Principe : on rejoue report.afficher_rapport en remplaçant temporairement Streamlit par un « enregistreur » HTML.
"""
import re
from datetime import datetime
from html import escape

import plotly.offline

import report


def _inline(t):
    t = escape(str(t))
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", t)


def _md(texte):
    sortie = []
    for ligne in str(texte).split("\n"):
        l = ligne.strip()
        if not l:
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", l)
        sortie.append(f"<h{len(m.group(1))}>{_inline(m.group(2))}</h{len(m.group(1))}>" if m else f"<p>{_inline(l)}</p>")
    return "".join(sortie)


class Zone:
    def __init__(self, racine):
        self.racine, self.parts = racine, []

    def __enter__(self):
        self.racine.pile.append(self)
        return self

    def __exit__(self, *a):
        self.racine.pile.pop()

    def html(self):
        return "".join(p() if callable(p) else p for p in self.parts)

    # --- fonctions Streamlit utilisées par report.py
    def markdown(self, texte, unsafe_allow_html=False, **kw):
        self.parts.append(texte if unsafe_allow_html else _md(texte))

    write = markdown

    def subheader(self, t, **kw):
        self.parts.append(f"<h2>{_inline(t)}</h2>")

    def caption(self, t, **kw):
        self.parts.append(f'<p class="caption">{_inline(t)}</p>')

    def info(self, t, **kw):
        self.parts.append(f'<div class="callout info">{_md(t)}</div>')

    def success(self, t, **kw):
        self.parts.append(f'<div class="callout success">{_md(t)}</div>')

    def warning(self, t, **kw):
        self.parts.append(f'<div class="callout warning">{_md(t)}</div>')

    def metric(self, label, value, **kw):
        self.parts.append(f'<div class="metric"><span>{escape(str(label))}</span><b>{escape(str(value))}</b></div>')

    def divider(self, **kw):
        self.parts.append("<hr>")

    def plotly_chart(self, fig, **kw):
        self.racine.graphiques = True
        self.parts.append('<div class="graphique">' + fig.to_html(
            full_html=False, include_plotlyjs=False, config=dict(displayModeBar=False, responsive=True)) + "</div>")

    def columns(self, spec, **kw):
        poids = list(spec) if isinstance(spec, (list, tuple)) else [1] * int(spec)
        zones = [Zone(self.racine) for _ in poids]
        self.parts.append(lambda: '<div class="ligne">' + "".join(
            f'<div style="flex:{p}">{z.html()}</div>' for p, z in zip(poids, zones)) + "</div>")
        return zones

    def tabs(self, libelles, **kw):
        zones = [Zone(self.racine) for _ in libelles]
        self.parts.append(lambda: "".join(
            f'<section><h1>{escape(l)}</h1>{z.html()}</section>' for l, z in zip(libelles, zones)))
        return zones

    def expander(self, libelle, **kw):
        z = Zone(self.racine)
        self.parts.append(lambda: f"<details open><summary>{_inline(libelle)}</summary>{z.html()}</details>")
        return z


class Racine:
    """Enregistreur : tout appel est redirigé vers la zone courante (colonne, onglet...)."""
    def __init__(self):
        self.pile, self.graphiques = [], False
        self.pile.append(Zone(self))

    def __getattr__(self, nom):
        return getattr(self.pile[-1], nom)


CSS = """
body{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#0b1f3a;background:#f6f8fb;margin:0;line-height:1.5}
main{max-width:1050px;margin:0 auto;padding:24px}
h1{font-size:1.5rem;margin:2rem 0 .6rem} h2{font-size:1.3rem;margin:1.6rem 0 .5rem} h3{font-size:1.15rem;margin:1.4rem 0 .4rem} h4{font-size:1rem;margin:1.2rem 0 .3rem}
.ligne{display:flex;gap:18px;flex-wrap:wrap}.ligne>div{min-width:300px}
.caption{color:#5b6b82;font-size:.9rem}
.callout{padding:12px 16px;border-radius:12px;margin:10px 0;border-left:5px solid}
.callout p{margin:.2rem 0}
.callout.info{background:#e8f1ff;border-color:#3b82f6}.callout.success{background:#e6f8ef;border-color:#10b981}.callout.warning{background:#fff4e0;border-color:#f59e0b}
.metric{display:inline-block;padding:10px 16px;border:1px solid #dbe3ee;border-radius:12px;background:#fff}.metric span{display:block;font-size:.8rem;color:#5b6b82}.metric b{font-size:1.4rem}
details{border:1px solid #dbe3ee;border-radius:12px;padding:8px 14px;margin:10px 0;background:#fff}summary{cursor:pointer;font-weight:600}
.graphique{background:#fff;border:1px solid #e1e7f0;border-radius:16px;padding:6px;margin:8px 0}
.entete{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dbe3ee;padding-bottom:10px;margin-bottom:10px;color:#5b6b82;font-size:.9rem}
@media print{body{background:#fff}section{break-before:page}section:first-of-type{break-before:auto}.graphique{break-inside:avoid}}
"""


def generer(modules, reponses, age=None, entete=""):
    """Retourne le rapport complet (octets HTML, UTF-8)."""
    racine = Racine()
    report._local.cible = racine
    try:
        report.afficher_rapport(modules, reponses, age=age)
    finally:
        report._local.cible = None
    corps = racine.pile[0].html()
    js = f"<script>{plotly.offline.get_plotlyjs()}</script>" if racine.graphiques else ""
    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")
    doc = (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Rapport de synthèse</title>'
           f"<style>{CSS}</style>{js}</head><body><main>"
           f'<div class="entete"><span>{escape(entete)}</span><span>Généré le {maintenant}</span></div>{corps}</main></body></html>')
    return doc.encode("utf-8")
