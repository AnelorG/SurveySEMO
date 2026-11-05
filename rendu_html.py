"""
rendu_html.py : produit le MÊME rapport de synthèse que celui du patient, sous forme d'un document HTML autonome
mis en page pour une impression / un enregistrement en PDF au format A4 (graphiques ajustés à la largeur de la page).
Principe : on rejoue report.afficher_rapport en remplaçant temporairement Streamlit par un « enregistreur » HTML.
"""
import re
from datetime import datetime
from html import escape

import plotly.offline

import report

LARGEUR_PAGE = 700   # largeur utile d'une page A4 (210 mm - 2 x 12 mm de marges) en pixels CSS
ECART = 18           # espace entre deux colonnes
HAUTEUR_MAX = 300    # hauteur maximale d'un graphique (une page A4 en contient ainsi 2 ou 3)


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
    def __init__(self, racine, largeur=LARGEUR_PAGE):
        self.racine, self.parts, self.largeur = racine, [], largeur

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
        if str(t).startswith("Vous pouvez imprimer"):      # inutile dans le document déjà prêt à imprimer
            return
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
        """Le graphique est dimensionné pour la colonne où il se trouve : jamais plus large ni plus haut que la page A4."""
        self.racine.graphiques = True
        h0 = fig.layout.height or 300
        hauteur = min(h0, HAUTEUR_MAX) if h0 > 200 else int(h0 * 0.8)          # les barres horizontales fines sont aplaties
        fig.update_layout(width=int(self.largeur - 16), height=int(hauteur), autosize=False, margin=dict(l=10, r=10, t=40, b=10))
        fig.update_yaxes(automargin=True)                                          # libellés longs jamais coupés
        fig.update_xaxes(automargin=True)
        self.parts.append('<div class="graphique">' + fig.to_html(
            full_html=False, include_plotlyjs=False, config=dict(displayModeBar=False, staticPlot=True, responsive=False)) + "</div>")

    def columns(self, spec, **kw):
        poids = list(spec) if isinstance(spec, (list, tuple)) else [1] * int(spec)
        utile = self.largeur - ECART * (len(poids) - 1)
        zones = [Zone(self.racine, utile * p / sum(poids)) for p in poids]
        self.parts.append(lambda: '<div class="ligne">' + "".join(
            f'<div style="flex:{p} 1 0">{z.html()}</div>' for p, z in zip(poids, zones)) + "</div>")
        return zones

    def tabs(self, libelles, **kw):
        zones = [Zone(self.racine, self.largeur) for _ in libelles]
        self.parts.append(lambda: "".join(
            f'<section><h1>{escape(l)}</h1>{z.html()}</section>' for l, z in zip(libelles, zones)))
        return zones

    def expander(self, libelle, **kw):
        z = Zone(self.racine, self.largeur)
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
@page{size:A4 portrait;margin:12mm}
*{box-sizing:border-box;-webkit-print-color-adjust:exact;print-color-adjust:exact}
body{font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,Arial,sans-serif;color:#0b1f3a;background:#e9edf3;margin:0;line-height:1.45;font-size:13px}
.barre{position:sticky;top:0;z-index:10;background:#0b1f3a;color:#fff;padding:10px 18px;display:flex;gap:16px;align-items:center;justify-content:space-between;font-size:13px}
.barre button{background:linear-gradient(135deg,#009EE0,#3b4cca);color:#fff;border:0;border-radius:10px;padding:10px 20px;font-weight:700;font-size:14px;cursor:pointer;white-space:nowrap}
.barre span{opacity:.85}
.feuille{width:210mm;max-width:100%;margin:16px auto;background:#fff;padding:12mm;box-shadow:0 10px 30px rgba(11,31,58,.15)}
h1{font-size:1.45rem;margin:0 0 .5rem} h2{font-size:1.25rem;margin:1.1rem 0 .4rem} h3{font-size:1.1rem;margin:1rem 0 .3rem} h4{font-size:1rem;margin:.9rem 0 .3rem}
p{margin:.3rem 0}
.ligne{display:flex;gap:18px}.ligne>div{min-width:0}
.caption{color:#5b6b82;font-size:.85rem}
.callout{padding:8px 12px;border-radius:12px;margin:6px 0;border-left:5px solid}
.callout p{margin:.2rem 0}
.callout.info{background:#e8f1ff;border-color:#3b82f6}.callout.success{background:#e6f8ef;border-color:#10b981}.callout.warning{background:#fff4e0;border-color:#f59e0b}
.metric{display:inline-block;padding:8px 14px;border:1px solid #dbe3ee;border-radius:12px;background:#fff}.metric span{display:block;font-size:.8rem;color:#5b6b82}.metric b{font-size:1.3rem}
details{border:1px solid #dbe3ee;border-radius:12px;padding:6px 12px;margin:8px 0;background:#fff}summary{cursor:pointer;font-weight:600}
.graphique{background:#fff;border:1px solid #e1e7f0;border-radius:14px;padding:4px;margin:6px 0;overflow:hidden}
.entete{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #dbe3ee;padding-bottom:8px;margin-bottom:10px;color:#5b6b82;font-size:.85rem}
.callout,.graphique,.ligne,details,.metric,.entete{break-inside:avoid;page-break-inside:avoid}
h1,h2,h3,h4{break-after:avoid;page-break-after:avoid}
h3+.callout,h2+.callout{break-after:avoid;page-break-after:avoid}
section{margin-bottom:6px}
@media print{
 body{background:#fff;font-size:12px}
 .barre{display:none}
 .feuille{width:auto;max-width:none;margin:0;padding:0;box-shadow:none}
 section{break-before:page;page-break-before:always}
 section:first-of-type{break-before:auto;page-break-before:auto}
 .feuille div[style*="linear-gradient(135deg"]{padding:12px 18px !important;margin-bottom:8px !important}
 h2{margin:.7rem 0 .3rem} h3{margin:.7rem 0 .25rem}
}
"""


def generer(modules, reponses, age=None, entete=""):
    """Retourne le rapport complet (octets HTML, UTF-8) prêt à être imprimé ou enregistré en PDF (A4)."""
    racine = Racine()
    report._local.cible = racine
    try:
        report.afficher_rapport(modules, reponses, age=age)
    finally:
        report._local.cible = None
    corps = racine.pile[0].html()
    js = f"<script>{plotly.offline.get_plotlyjs()}</script>" if racine.graphiques else ""
    maintenant = datetime.now().strftime("%d/%m/%Y %H:%M")
    barre = ('<div class="barre"><span>Aperçu du rapport (format A4). Dans la fenêtre d’impression, choisissez '
             '<b>« Enregistrer au format PDF »</b> comme destination.</span>'
             '<button onclick="window.print()">🖨️ Imprimer / Enregistrer en PDF</button></div>')
    doc = (f'<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>Rapport de synthèse</title>'
           f"<style>{CSS}</style>{js}</head><body>{barre}<main class=\"feuille\">"
           f'<div class="entete"><span>{escape(entete)}</span><span>Généré le {maintenant}</span></div>{corps}</main></body></html>')
    return doc.encode("utf-8")
