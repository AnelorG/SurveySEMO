"""
report.py : le rapport de synthèse du participant (graphiques colorés + explications).
- Chaque module peut avoir son rapport personnalisé : voir REGISTRE en bas du fichier.
- Un module sans rapport personnalisé reçoit un rapport simple (score éventuel + récapitulatif des réponses).
- Les repères utilisés (OMS, Santé publique France, etc.) sont indicatifs et à faire valider par l'équipe.
"""
import threading
from html import escape

import plotly.graph_objects as go
import streamlit as _st

import cotations
import scoring

# `st` est un intermédiaire : il envoie les appels à Streamlit, sauf si une génération HTML est en cours
# dans CE fil d'exécution (voir rendu_html.py) : c'est ce qui permet de télécharger exactement le même rapport.
_local = threading.local()


class _Intermediaire:
    def __getattr__(self, nom):
        cible = getattr(_local, "cible", None)
        return getattr(_st if cible is None else cible, nom)


st = _Intermediaire()

C = dict(teal="#14b8a6", indigo="#6366f1", amber="#f59e0b", rose="#f43f5e",
         green="#10b981", sky="#0ea5e9", violet="#8b5cf6", slate="#64748b", orange="#f97316")


# ---------------------------------------------------------------- outils
def vide(v):
    return v is None or v == "" or v == []


def num(r, k):
    v = r.get(k)
    return None if vide(v) or isinstance(v, bool) else float(v)


def rang(r, Q, k):
    """Position (0, 1, 2...) de la réponse choisie dans la liste d'options du fichier YAML."""
    opts = Q.get(k, {}).get("options", [])
    v = r.get(k)
    return opts.index(v) if v in opts else None


def fmt(x):
    return f"{x:g}"


def carte(titre, valeur, sous="", couleur=C["teal"], icone=""):
    return (f'<div style="flex:1;min-width:150px;padding:14px 16px;border-radius:16px;'
            f'background:{couleur}22;border:1px solid {couleur}66">'
            f'<div style="font-size:1.5rem">{icone}</div>'
            f'<div style="font-size:.8rem;opacity:.75">{escape(titre)}</div>'
            f'<div style="font-size:1.3rem;font-weight:700;color:{couleur}">{escape(str(valeur))}</div>'
            f'<div style="font-size:.78rem;opacity:.75">{escape(sous)}</div></div>')


def rangee(cartes):
    st.markdown('<div style="display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 16px">'
                + "".join(cartes) + "</div>", unsafe_allow_html=True)


def pastilles(items):
    html = ""
    for icone, label, actif, detail in items:
        col = C["teal"] if actif else C["slate"]
        det = f" · {escape(detail)}" if (detail and actif) else ""
        html += (f'<span style="display:inline-block;margin:4px 6px 4px 0;padding:8px 14px;border-radius:999px;'
                 f'background:{col}{"33" if actif else "14"};border:1px solid {col}88;'
                 f'opacity:{1 if actif else .5}">{icone} <b>{escape(label)}</b>{det}</span>')
    st.markdown(html, unsafe_allow_html=True)


def style(fig, h=320):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=50, b=10), font=dict(size=13))
    return fig


def explication(texte):
    st.markdown(f'<div style="padding:10px 14px;border-left:4px solid {C["indigo"]};'
                f'background:{C["indigo"]}14;border-radius:8px;margin:6px 0 14px">{texte}</div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- PARTIE 1
def rapport_parcours(r, Q, age, m=None):
    forts, pistes = [], []
    st.subheader("🎓 Votre parcours de vie")
    explication("Ces questions explorent ce qu’on appelle la <b>réserve cognitive</b> : la capacité du cerveau à "
                "s’adapter et à bien fonctionner malgré l’âge. On pense qu’elle se construit tout au long de la vie, "
                "grâce aux études, au travail, aux loisirs stimulants et aux relations sociales.")

    annees = num(r, "r1_annees_etudes")
    diplome = r.get("r2_autre") if r.get("r2_diplome") == "Autre" else r.get("r2_diplome")
    nb_prof = sum(1 for i in range(1, 5) if not vide(r.get(f"r4_prof{i}")))
    langues = [r.get(f"r11_l{n}_nom") for n in (1, 2) if not vide(r.get(f"r11_l{n}_nom"))]
    rangee([
        carte("Années d’études", f"{fmt(annees)} ans" if annees is not None else "—", icone="📘", couleur=C["indigo"]),
        carte("Diplôme le plus élevé", diplome or "—", icone="🎓", couleur=C["violet"]),
        carte("Professions exercées", nb_prof, icone="💼", couleur=C["sky"]),
        carte("Langues (hors français)", len(langues), ", ".join(langues), icone="🌍", couleur=C["teal"]),
    ])

    st.markdown("#### Les grands domaines que vous avez cultivés")
    piliers = [
        ("🎓", "Formation continue", r.get("r3_formation") == "Oui", r.get("r3_quoi") or ""),
        ("👥", "Encadrement d’équipe", r.get("r5_encadrement") == "Oui", r.get("r5_profession") or ""),
        ("🌍", "Langues", bool(langues), ", ".join(langues)),
        ("🎵", "Musique / chant", r.get("r12_musique") == "Oui", r.get("r12_musique_activite") or ""),
        ("🎨", "Activité artistique", r.get("r13_art") == "Oui", r.get("r13_art_activite") or ""),
        ("🤝", "Vie associative", r.get("r10_association") == "Oui", r.get("r10_type") or ""),
    ]
    pastilles(piliers)
    n = sum(1 for p in piliers if p[2])
    st.caption(f"Vous avez cultivé **{n} domaine(s) sur {len(piliers)}**. Il n’y a pas de « bonne » réponse : "
               "chaque parcours est unique.")
    if n >= 4:
        forts.append(f"Un parcours de vie riche et varié ({n} domaines sur {len(piliers)}).")

    # --- carte de chaleur des activités selon l'âge
    acts = [("📚 Lecture", "r6_lecture"), ("🧩 Jeux de réflexion", "r7_jeux"),
            ("🎭 Culture", "r8_culture"), ("💡 Apprentissage", "r9_apprentissage")]
    periodes = [("18_30", "18–30 ans"), ("30_65", "30–65 ans"), ("65_plus", "65 ans et + / actuel")]
    labels = ["Jamais", "Rarement", "Qq fois/an", "Qq fois/mois", "Qq fois/sem.", "Presque tous les jours"]
    z, texte = [], []
    for _, qid in acts:
        ligne = []
        for suf, _l in periodes:
            v = r.get(f"{qid}_{suf}")
            opts = Q.get(f"{qid}_{suf}", {}).get("options", [])
            ligne.append(opts.index(v) if v in opts else None)
        z.append(ligne)
        texte.append(["" if v is None else str(v) for v in ligne])
    if any(v is not None for ligne in z for v in ligne):
        st.markdown("#### Vos activités stimulantes au fil de la vie")
        explication("Plus la case est <b>foncée</b>, plus l’activité était fréquente (de 0 = jamais à 5 = presque tous les jours).")
        fig = go.Figure(go.Heatmap(
            z=z, x=[p[1] for p in periodes], y=[a[0] for a in acts], text=texte, texttemplate="%{text}",
            textfont=dict(size=20), zmin=0, zmax=5, xgap=4, ygap=4, hoverongaps=False,
            colorscale=[[0, "#e0f2fe"], [0.4, "#5eead4"], [0.7, "#14b8a6"], [1, "#4f46e5"]],
            colorbar=dict(tickmode="array", tickvals=list(range(6)), ticktext=labels, len=0.9, thickness=14)))
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style(fig, 330))
        actuels = [(a[0], row[2]) for a, row in zip(acts, z) if row[2] is not None]
        for nom, v in actuels:
            if v >= 4:
                forts.append(f"{nom.split(' ', 1)[1]} : une activité régulière aujourd’hui.")
        for (nom, _q), row in zip(acts, z):
            if row[2] is not None and row[2] <= 1 and max([x for x in row[:2] if x is not None] or [0]) >= 3:
                pistes.append(f"{nom.split(' ', 1)[1]} : plus fréquent(e) auparavant. Une reprise douce pourrait vous plaire.")

    # --- frise de vie
    cur = float(age) if age else None
    lignes = []
    for i in range(1, 5):
        d, f = num(r, f"r4_prof{i}_debut"), num(r, f"r4_prof{i}_fin")
        if r.get(f"r4_prof{i}") and d is not None:
            lignes.append(("Métier", r[f"r4_prof{i}"], d, f if f is not None else (cur or d + 1)))
    if r.get("r10_association") == "Oui" and num(r, "r10_debut") is not None:
        d, f = num(r, "r10_debut"), num(r, "r10_fin")
        lignes.append(("Association", r.get("r10_type") or "Association", d,
                       f if f is not None else (cur if r.get("r10_encore") and cur else d + 1)))
    for n_ in (1, 2):
        d, ans = num(r, f"r11_l{n_}_age"), num(r, f"r11_l{n_}_annees")
        if r.get(f"r11_l{n_}_nom") and d is not None:
            lignes.append(("Langue", r[f"r11_l{n_}_nom"], d, d + (ans or 1)))
    for cat, qid in (("Musique", "r12_musique"), ("Art", "r13_art")):
        d, f = num(r, f"{qid}_debut"), num(r, f"{qid}_arret")
        if r.get(qid) == "Oui" and d is not None:
            lignes.append((cat, r.get(f"{qid}_activite") or cat, d,
                           f if f is not None else (cur if r.get(f"{qid}_encore") and cur else d + 1)))
    d, f = num(r, "mv8_debut"), num(r, "mv8_fin")
    if r.get("mv8_sport") == "Oui" and d is not None:
        lignes.append(("Sport", r.get("mv8_activite") or "Sport", d,
                       f if f is not None else (cur if r.get("mv8_encore") and cur else d + 1)))
    if lignes:
        couleurs = {"Métier": C["indigo"], "Association": C["amber"], "Langue": C["teal"],
                    "Musique": C["rose"], "Art": C["violet"], "Sport": C["green"]}
        st.markdown("#### Votre frise de vie")
        explication("Chaque barre montre <b>à quel âge</b> vous avez exercé un métier ou pratiqué une activité. "
                    "Les barres très courtes correspondent à des durées non précisées.")
        fig, vus = go.Figure(), set()
        for cat, nom, d, f in lignes:
            fig.add_trace(go.Bar(y=[f"{cat} · {nom[:26]}"], x=[max(f - d, 1)], base=[d], orientation="h",
                                 marker=dict(color=couleurs[cat], cornerradius=6), name=cat,
                                 showlegend=cat not in vus,
                                 hovertemplate=f"{escape(nom)}<br>de {fmt(d)} à {fmt(f)} ans<extra></extra>"))
            vus.add(cat)
        if cur:
            fig.add_vline(x=cur, line_dash="dot", line_color=C["slate"], annotation_text="Aujourd’hui")
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="Âge (ans)")
        fig.update_layout(barmode="overlay", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(style(fig, 140 + 38 * len(lignes)))
    return dict(cartes=[carte("Domaines cultivés", f"{n} / {len(piliers)}", "parcours de vie", C["indigo"], "🎓")],
                forts=forts, pistes=pistes)


# ---------------------------------------------------------------- PARTIE 2
def rapport_mode_de_vie(r, Q, age, m):
    """Module 1 – Mode de vie : IPAQ, PSQI, MEDAS, tabac et alcool (cotations : cotations.py)."""
    forts, pistes, cartes = [], [], []
    v = cotations.calculer(m, r, age)
    st.subheader("🌿 Votre mode de vie")

    # ------------------------------------------------ activité physique (IPAQ)
    st.markdown("### 🏃 Activité physique")
    explication("Le questionnaire <b>IPAQ</b> mesure votre activité physique des 7 derniers jours en <b>MET-minutes par semaine</b> : "
                "durée × fréquence × intensité (marche = 3 · modérée = 4 · intense = 8). Il vous classe en <b>3 catégories</b> (Craig et al., 2003) : "
                "faible, modérée ou élevée. On vérifie aussi la recommandation <b>CDC-ACSM</b> : au moins <b>150 minutes par semaine</b> d’activité "
                "d’intensité au moins modérée (une minute d’activité intense compte double).")
    total, niveau, equiv = v["ipaq_total"], v["ipaq_niveau"], v["ipaq_minutes_equivalent_modere"]
    if total is not None:
        c1, c2 = st.columns(2)
        top = max(4000.0, total * 1.15)
        g = go.Figure(go.Indicator(
            mode="gauge+number", value=total, number=dict(suffix=" MET-min"), title=dict(text="Score total IPAQ par semaine"),
            gauge=dict(axis=dict(range=[0, top]), bar=dict(color=C["indigo"]),
                       steps=[dict(range=[0, 600], color="rgba(249,115,22,.30)"), dict(range=[600, 3000], color="rgba(16,185,129,.35)"),
                              dict(range=[3000, top], color="rgba(20,184,166,.30)")])))
        c1.plotly_chart(style(g, 280))
        b = go.Figure()
        for nom, cle, col in (("Intense", "ipaq_intense", C["rose"]), ("Modérée", "ipaq_modere", C["amber"]), ("Marche", "ipaq_marche", C["sky"])):
            b.add_trace(go.Bar(x=[nom], y=[v[cle] or 0], marker=dict(color=col, cornerradius=8), text=[f"{fmt(v[cle] or 0)}"],
                               textposition="outside", cliponaxis=False))
        b.update_layout(showlegend=False, yaxis_title="MET-min / semaine", title="Répartition par intensité")
        c2.plotly_chart(style(b, 280))
        top2 = max(300.0, equiv * 1.2)
        g2 = go.Figure(go.Indicator(
            mode="number+gauge", value=equiv, number=dict(suffix=" min", valueformat=".0f"),
            title=dict(text="Minutes d’activité par semaine (intense ×2)"),
            gauge=dict(shape="bullet", axis=dict(range=[0, top2]), bar=dict(color=C["green"] if equiv >= 150 else C["orange"], thickness=0.5),
                       steps=[dict(range=[0, 150], color="rgba(249,115,22,.28)"), dict(range=[150, top2], color="rgba(16,185,129,.35)")],
                       threshold=dict(line=dict(color=C["slate"], width=3), value=150))))
        st.plotly_chart(style(g2, 150))
        niveau_col = {"Faible": C["orange"], "Modéré": C["green"], "Élevé": C["teal"]}.get(niveau, C["slate"])
        cs = [carte("Score total IPAQ", f"{fmt(total)}", "MET-min/semaine", C["indigo"], "🏃"),
              carte("Catégorie d’activité", niveau or "—", v["ipaq_critere"] or "", niveau_col, "📈"),
              carte("Recommandation 150 min", "Atteinte" if equiv >= 150 else "Non atteinte", f"{fmt(round(equiv))} min équivalentes/semaine",
                    C["green"] if equiv >= 150 else C["orange"], "✅" if equiv >= 150 else "🎯")]
        if v["assis_min_jour"] is not None:
            cs.append(carte("Temps assis", f"{v['assis_min_jour'] / 60:.1f} h / jour", "un jour de semaine · hors score IPAQ", C["slate"], "🪑"))
            if v["assis_min_jour"] >= 480:
                pistes.append("Temps assis élevé : une courte pause active toutes les heures est bénéfique.")
        rangee(cs)
        if equiv >= 150:
            forts.append(f"Activité physique : environ {fmt(round(equiv))} min par semaine, la recommandation de 150 min est atteinte (catégorie « {niveau} »).")
        else:
            pistes.append(f"Activité physique : environ {fmt(round(equiv))} min par semaine, sous la recommandation de 150 min. "
                          "Ajoutez progressivement de la marche rapide ou du vélo.")
        cartes.append(carte("Activité physique (IPAQ)", f"{fmt(total)}", f"MET-min/sem · catégorie {niveau}", C["green"] if equiv >= 150 else C["orange"], "🏃"))

    # ------------------------------------------------ sommeil (PSQI)
    st.markdown("### 😴 Sommeil")
    explication("L’indice <b>PSQI</b> évalue la qualité de votre sommeil sur le dernier mois, de 0 à 21 : "
                "<b>plus le score est bas, meilleur est le sommeil</b>. Un score supérieur à <b>5</b> est couramment utilisé comme repère d’un sommeil perturbé.")
    p = v["psqi_total"]
    if p is not None:
        g = go.Figure(go.Indicator(
            mode="number+gauge", value=p, number=dict(suffix=" / 21"), title=dict(text="Score global PSQI"),
            gauge=dict(shape="bullet", axis=dict(range=[0, 21]), bar=dict(color=C["green"] if p <= 5 else C["orange"], thickness=0.5),
                       steps=[dict(range=[0, 5], color="rgba(16,185,129,.35)"), dict(range=[5, 21], color="rgba(249,115,22,.28)")],
                       threshold=dict(line=dict(color=C["slate"], width=3), value=5))))
        st.plotly_chart(style(g, 170))
        noms = ["Qualité ressentie", "Endormissement", "Durée du sommeil", "Efficacité du sommeil", "Perturbations", "Médicaments", "Somnolence en journée"]
        vals = [v[f"psqi_c{i}"] for i in range(1, 8)]
        coul = [[C["green"], C["teal"], C["amber"], C["rose"]][min(x, 3)] for x in vals]
        comp = go.Figure(go.Bar(x=vals, y=noms, orientation="h", marker=dict(color=coul, cornerradius=8), text=vals, textposition="outside", cliponaxis=False))
        comp.update_layout(title="Les 7 composantes (0 = aucune difficulté, 3 = difficulté importante)", xaxis=dict(range=[0, 3.4], dtick=1))
        comp.update_yaxes(autorange="reversed")
        st.plotly_chart(style(comp, 360))
        cs = []
        if v["psqi_efficacite_pct"] is not None:
            cs.append(carte("Efficacité du sommeil", f"{v['psqi_efficacite_pct']:.0f} %", "temps endormi / temps au lit (≥ 85 % : très bon)",
                            C["green"] if v["psqi_efficacite_pct"] > 85 else C["orange"], "🛌"))
        if v["psqi_temps_au_lit_h"] is not None:
            cs.append(carte("Temps passé au lit", f"{v['psqi_temps_au_lit_h']:.1f} h", "par nuit", C["slate"], "🕘"))
        cs.append(carte("Sommeil effectif", f"{fmt(_n_(r, 'mv11_sommeil_h'))} h", "par nuit (repère : 7–9 h)", C["indigo"], "😴"))
        rangee(cs)
        if p <= 5:
            forts.append(f"Un sommeil de bonne qualité d’après le PSQI ({p}/21).")
        else:
            pistes.append(f"Sommeil : votre score PSQI ({p}/21) dépasse le repère de 5. Des horaires réguliers peuvent aider ; "
                          "si la gêne dure, parlez-en à votre médecin.")
        cartes.append(carte("Sommeil (PSQI)", f"{p} / 21", "plus bas = meilleur sommeil", C["green"] if p <= 5 else C["orange"], "😴"))

    # ------------------------------------------------ alimentation (MEDAS)
    st.markdown("### 🥗 Alimentation méditerranéenne")
    explication("Le score <b>MEDAS</b> compte 14 habitudes de l’alimentation méditerranéenne : 1 point par habitude atteinte, de 0 à 14. "
                "<b>Plus il est élevé, plus votre alimentation s’en rapproche.</b> 9 points ou plus est un repère souvent retenu d’une bonne adhésion.")
    mt = v["medas_total"]
    if mt is not None:
        g = go.Figure(go.Indicator(
            mode="number+gauge", value=mt, number=dict(suffix=" / 14"), title=dict(text="Score MEDAS"),
            gauge=dict(shape="bullet", axis=dict(range=[0, 14]), bar=dict(color=C["violet"], thickness=0.5),
                       steps=[dict(range=[0, 9], color="rgba(245,158,11,.28)"), dict(range=[9, 14], color="rgba(16,185,129,.35)")],
                       threshold=dict(line=dict(color=C["slate"], width=3), value=9))))
        st.plotly_chart(style(g, 170))
        items = [(cle, nom) for (cle, _, _), nom in zip(cotations.MEDAS, cotations.MEDAS_NOMS)]
        pastilles([("✅" if v[cle] else "▫️", nom, bool(v[cle]), "") for cle, nom in items])
        st.caption("Habitudes atteintes en couleur ; les autres sont des pistes de progression.")
        manque = [nom for cle, nom in items if not v[cle]]
        if mt >= 9:
            forts.append(f"Une alimentation proche du modèle méditerranéen (MEDAS {mt}/14).")
        else:
            pistes.append(f"Alimentation (MEDAS {mt}/14) : pour progresser, regardez par exemple « {manque[0]} »" + (f" ou « {manque[1]} »." if len(manque) > 1 else "."))
        cartes.append(carte("Alimentation (MEDAS)", f"{mt} / 14", "repère : ≥ 9", C["violet"] if mt >= 9 else C["amber"], "🥗"))

    # ------------------------------------------------ tabac et alcool
    st.markdown("### 🚭 Tabac et alcool")
    cs = []
    statut, pa = v["tabac_statut"], v["tabac_paquets_annees"]
    if statut == 0:
        cs.append(carte("Tabac", "Jamais fumé", "", C["green"], "🚭"))
        forts.append("Vous n’avez jamais fumé régulièrement.")
    elif statut in (1, 2):
        cs.append(carte("Tabac", "Ancien fumeur" if statut == 1 else "Fumeur actuel", f"{fmt(pa)} paquets-années" if pa is not None else "",
                        C["teal"] if statut == 1 else C["orange"], "🚭" if statut == 1 else "🚬"))
        if statut == 1:
            forts.append("Vous avez arrêté de fumer : c’est l’un des meilleurs gestes pour la santé.")
        else:
            pistes.append("Tabac : arrêter est possible à tout âge et vous pouvez être accompagné(e) (Tabac Info Service : 39 89).")
    sem = v["alcool_verres_semaine"]
    if sem is not None:
        cs.append(carte("Alcool", f"≈ {fmt(sem)} verre" + ("" if sem == 1 else "s"), "par semaine (repère : ≤ 10)", C["sky"] if sem <= 10 else C["orange"], "🥂"))
        rangee(cs)
        if pa is not None and statut in (1, 2):
            explication("Un <b>paquet-année</b> correspond à 20 cigarettes par jour pendant 1 an : c’est une mesure de l’exposition cumulée au tabac.")
        explication("Santé publique France recommande de ne pas dépasser <b>10 verres standards par semaine</b> et 2 par jour, avec des jours sans alcool.")
        top = max(15.0, sem * 1.2)
        g = go.Figure(go.Indicator(
            mode="number+gauge", value=sem, number=dict(suffix=" verres", valueformat=".0f"), title=dict(text="Consommation estimée par semaine"),
            gauge=dict(shape="bullet", axis=dict(range=[0, top]), bar=dict(color=C["sky"] if sem <= 10 else C["orange"], thickness=0.5),
                       steps=[dict(range=[0, 10], color="rgba(16,185,129,.35)"), dict(range=[10, top], color="rgba(249,115,22,.30)")],
                       threshold=dict(line=dict(color=C["slate"], width=3), value=10))))
        st.plotly_chart(style(g, 170))
        (forts if sem <= 10 else pistes).append("Une consommation d’alcool dans les repères." if sem <= 10 else
                                                 "Alcool : votre consommation estimée dépasse le repère de 10 verres par semaine.")
        cartes.append(carte("Alcool", f"≈ {fmt(sem)}", "verres standards/semaine · repère : ≤ 10", C["sky"] if sem <= 10 else C["orange"], "🥂"))
    else:
        rangee(cs)
    return dict(cartes=cartes, forts=forts, pistes=pistes)


def _n_(r, k):
    v = r.get(k)
    return 0 if v is None or isinstance(v, bool) else v


def rapport_exposome_psy(r, Q, age, m):
    """Module 2 – Exposome psychosocial : réseau social (LSNS-6), symptômes dépressifs (HAD-D), antécédents."""
    forts, pistes, cartes = [], [], []
    v = cotations.calculer(m, r, age)
    st.subheader("🤝 Votre environnement psychosocial")

    # ------------------------------------------------ réseau social (LSNS-6)
    st.markdown("### 👥 Réseau social")
    explication("L’échelle <b>LSNS-6</b> évalue la place de votre famille et de vos amis dans votre vie : de 0 à 30, "
                "<b>plus le score est élevé, plus votre entourage est présent</b>. Un score inférieur à <b>12</b> est couramment utilisé "
                "comme repère d’un risque d’isolement social.")
    t = v["lsns_total"]
    if t is not None:
        c1, c2 = st.columns(2)
        g = go.Figure(go.Indicator(
            mode="gauge+number", value=t, number=dict(suffix=" / 30"), title=dict(text="Score total LSNS-6"),
            gauge=dict(axis=dict(range=[0, 30]), bar=dict(color=C["indigo"]),
                       steps=[dict(range=[0, 12], color="rgba(249,115,22,.30)"), dict(range=[12, 30], color="rgba(16,185,129,.35)")])))
        c1.plotly_chart(style(g, 300))
        axes = ["Contacts", "Confidences", "Aide"]
        fam = [v["psy1_famille_contact"], v["psy2_famille_confidences"], v["psy3_famille_aide"]]
        ami = [v["psy4_amis_contact"], v["psy5_amis_confidences"], v["psy6_amis_aide"]]
        b = go.Figure()
        b.add_trace(go.Bar(name="Famille", x=axes, y=fam, marker=dict(color=C["sky"], cornerradius=8), text=fam, textposition="outside"))
        b.add_trace(go.Bar(name="Amis", x=axes, y=ami, marker=dict(color=C["violet"], cornerradius=8), text=ami, textposition="outside"))
        b.update_layout(barmode="group", title="Votre entourage (0 à 5)", yaxis=dict(range=[0, 5.8], dtick=1),
                        legend=dict(orientation="h", y=-0.2))
        c2.plotly_chart(style(b, 300))
        c2.caption("Contacts : voir ou parler au moins 1 fois/mois · Confidences : pouvoir se confier · Aide : pouvoir demander de l’aide. 0 = aucun, 5 = 9 personnes ou plus.")
        rangee([carte("Score total", f"{t} / 30", "repère : ≥ 12", C["green"] if t >= 12 else C["orange"], "👥"),
                carte("Famille", f"{v['lsns_famille']} / 15", "", C["sky"], "🏠"), carte("Amis", f"{v['lsns_amis']} / 15", "", C["violet"], "🧑‍🤝‍🧑")])
        if t >= 12:
            forts.append(f"Un entourage présent : score de {t}/30 à l’échelle LSNS-6.")
        else:
            pistes.append(f"Réseau social : votre score ({t}/30) est inférieur au repère de 12. Renouer des liens (associations, activités de groupe) "
                          "peut aider ; vous pouvez aussi en parler à votre médecin.")
        cartes.append(carte("Réseau social (LSNS-6)", f"{t} / 30", "plus haut = entourage plus présent", C["green"] if t >= 12 else C["orange"], "👥"))

    # ------------------------------------------------ symptômes dépressifs (HAD-D)
    st.markdown("### 💬 Moral des derniers temps")
    explication("Le volet « dépression » de l’échelle <b>HAD</b> repère des signes de moral bas, de 0 à 21 : <b>plus le score est bas, mieux c’est</b>. "
                "Repères usuels : <b>0 à 7</b> peu ou pas de signes ; <b>8 à 10</b> quelques signes ; <b>11 et plus</b> signes marqués. "
                "Ce n’est pas un diagnostic : seul un professionnel de santé peut en poser un.")
    h = v["had_d_total"]
    if h is not None:
        g = go.Figure(go.Indicator(
            mode="number+gauge", value=h, number=dict(suffix=" / 21"), title=dict(text="Score HAD-D"),
            gauge=dict(shape="bullet", axis=dict(range=[0, 21]), bar=dict(color=C["green"] if h <= 7 else C["orange"], thickness=0.5),
                       steps=[dict(range=[0, 7], color="rgba(16,185,129,.35)"), dict(range=[7, 10], color="rgba(245,158,11,.30)"),
                              dict(range=[10, 21], color="rgba(249,115,22,.30)")])))
        st.plotly_chart(style(g, 170))
        if h <= 7:
            forts.append(f"Peu de signes de moral bas à l’échelle HAD-D ({h}/21).")
        else:
            pistes.append(f"Moral : votre score HAD-D ({h}/21) montre des signes de moral bas. Parlez-en à votre médecin ; "
                          "en cas de détresse, le 3114 est joignable 24 h/24.")
        cartes.append(carte("Moral (HAD-D)", f"{h} / 21", "plus bas = mieux · repère : ≤ 7", C["green"] if h <= 7 else C["orange"], "💬"))

    # ------------------------------------------------ antécédents dépressifs (descriptif)
    dep = v["dep_antecedent"]
    if dep is not None:
        st.markdown("### 🗂️ Vos antécédents")
        cs = [carte("Dépression diagnostiquée", "Oui" if dep else "Non", "au cours de la vie", C["slate"], "🗂️")]
        if dep:
            if v["dep_age_premier_episode"] is not None:
                cs.append(carte("Premier épisode", f"{fmt(v['dep_age_premier_episode'])} ans", "", C["slate"], "📅"))
            if v["dep_recidive"] is not None:
                cs.append(carte("Épisodes", "Plusieurs" + (f" (≈ {fmt(v['dep_nb_episodes'])})" if v["dep_nb_episodes"] else "") if v["dep_recidive"] else "Un seul",
                                "", C["slate"], "🔁"))
            prise = {0: "Aucune", 1: "Médicaments", 2: "Psychothérapie", 3: "Médicaments + psychothérapie", 4: "Autre"}.get(v["dep_prise_en_charge"])
            if prise:
                cs.append(carte("Prise en charge", prise, "", C["slate"], "🩺"))
        rangee(cs)
        st.caption("Ces informations sont simplement rappelées : aucun score n’est calculé à partir de vos antécédents.")
    return dict(cartes=cartes, forts=forts, pistes=pistes)


def rapport_expositions(r, Q, age, m):
    """Module 3 – Expositions environnementales et professionnelles (descriptif : les indices exploratoires restent dans l'export)."""
    forts, pistes, cartes = [], [], []
    v = cotations.calculer(m, r, age)
    st.subheader("🌍 Vos expositions environnementales")
    explication("Ces questions recensent les produits, lieux de vie et situations auxquels vous avez pu être exposé(e) au cours de votre vie. "
                "Ce sont des informations <b>déclaratives</b> : elles ne mesurent ni une dose réelle, ni un risque individuel.")
    groupes = [("env1", "💼", "Chimiques et professionnelles", C["indigo"]), ("env2", "🛣️", "Environnement extérieur", C["sky"]),
               ("env3", "🏠", "Environnement intérieur", C["teal"])]
    total, cs, barres = 0, [], []
    for g, icone, nom, col in groupes:
        items = cotations.ENV[g][1]
        n, nsp = v[f"{g}_nombre"], v[f"{g}_nb_nsp"]
        total += v[f"{g}_nb_connues"]
        cs.append(carte(nom, f"{n} / {len(items)}" if n is not None else f"≥ {v[g + '_nb_connues']} / {len(items)}", "déclarée(s)" + (f" · {nsp} « je ne sais pas »" if nsp else ""), col, icone))
        for cle, nom_item, avec_freq in items:
            duree = (v[f"{cle}_duree_mois"] / 12 if v.get(f"{cle}_duree_mois") is not None else None) if avec_freq else v.get(f"{cle}_duree_annees")
            if v[f"{cle}_present"] == 1 and duree is not None:
                barres.append((nom_item, duree, col))
    rangee(cs)
    pastilles([("✅" if v[f"{cle}_present"] == 1 else ("❔" if v[f"{cle}_present"] is None else "▫️"), nom_item, v[f"{cle}_present"] == 1, "")
               for g, *_ in groupes for cle, nom_item, _a in cotations.ENV[g][1]])
    st.caption("Expositions déclarées en couleur ; ❔ = « je ne sais pas ».")
    if barres:
        barres.sort(key=lambda b: b[1])
        fig = go.Figure(go.Bar(x=[b[1] for b in barres], y=[b[0] for b in barres], orientation="h",
                               marker=dict(color=[b[2] for b in barres], cornerradius=8), text=[f"{b[1]:.1f} ans" for b in barres],
                               textposition="outside", cliponaxis=False))
        fig.update_layout(title="Durée déclarée de chaque exposition (en années)", xaxis=dict(title="Années", range=[0, max(b[1] for b in barres) * 1.25]))
        st.plotly_chart(style(fig, 140 + 46 * len(barres)))
    else:
        st.caption("Vous n’avez déclaré aucune exposition de ce type.")
    if total == 0 and not any(v[f"{g}_nb_nsp"] for g, *_ in groupes):
        forts.append("Aucune exposition environnementale ou professionnelle particulière déclarée.")
    if v["env1_nombre"]:
        pistes.append("Produits chimiques : respectez les consignes de sécurité et les équipements de protection, et parlez-en à votre médecin si vous avez des questions.")
    if v["env3_tabac_passif_present"] == 1:
        pistes.append("Fumée de tabac des autres : évitez autant que possible les lieux enfumés.")
    if v["env3_humidite_present"] == 1:
        pistes.append("Humidité ou moisissures : aérer et ventiler régulièrement le logement est bénéfique.")
    if v["env3_combustion_present"] == 1:
        pistes.append("Appareil à combustion : faites-le entretenir régulièrement et aérez la pièce.")
    cartes.append(carte("Expositions déclarées", f"{total}", "environnement et métiers", C["indigo"], "🌍"))
    return dict(cartes=cartes, forts=forts, pistes=pistes)


def rapport_sante(r, Q, age, m):
    """Module 4 – Santé générale : IMC, santé cardio-métabolique, vision/audition. Les données les plus sensibles
    (VIH, antécédents neurologiques, ménopause…) ne sont volontairement PAS reprises dans la synthèse : elles restent dans l'export."""
    forts, pistes, cartes = [], [], []
    v = cotations.calculer(m, r, age)
    st.subheader("🩺 Votre santé générale")

    st.markdown("### ⚖️ Poids et corpulence")
    explication("L’<b>indice de masse corporelle (IMC)</b> est le poids (kg) divisé par la taille au carré (m²). Repères adultes de l’OMS : "
                "moins de 18,5 : maigreur ; <b>18,5 à 24,9 : corpulence normale</b> ; 25 à 29,9 : surpoids ; 30 et plus : obésité. "
                "Ces repères sont indicatifs (chez les personnes âgées, d’autres valeurs peuvent être plus adaptées) : votre médecin saura les interpréter.")
    imc = v["imc"]
    if imc is not None:
        g = go.Figure(go.Indicator(
            mode="number+gauge", value=imc, number=dict(suffix=" kg/m²", valueformat=".1f"), title=dict(text="Votre IMC"),
            gauge=dict(shape="bullet", axis=dict(range=[10, 45]), bar=dict(color=C["indigo"], thickness=0.5),
                       steps=[dict(range=[10, 18.5], color="rgba(14,165,233,.30)"), dict(range=[18.5, 25], color="rgba(16,185,129,.35)"),
                              dict(range=[25, 30], color="rgba(245,158,11,.30)"), dict(range=[30, 45], color="rgba(249,115,22,.30)")])))
        st.plotly_chart(style(g, 170))
        rangee([carte("IMC", f"{imc:.1f}", "kg/m²", C["green"] if 18.5 <= imc < 25 else C["amber"], "⚖️"),
                carte("Taille", f"{fmt(v['taille_cm'])} cm", "", C["slate"], "📏"), carte("Poids", f"{fmt(v['poids_kg'])} kg", "", C["slate"], "⚖️")])
        if 18.5 <= imc < 25:
            forts.append(f"Un IMC dans la zone de corpulence normale ({imc:.1f}).")
        elif imc >= 25:
            pistes.append(f"IMC de {imc:.1f} : au-dessus de 25. L’activité physique régulière et l’alimentation y contribuent ; votre médecin peut vous conseiller.")
        else:
            pistes.append(f"IMC de {imc:.1f} : en dessous de 18,5. Parlez-en à votre médecin, notamment en cas de perte de poids récente.")
        cartes.append(carte("IMC", f"{imc:.1f}", "kg/m² · repère : 18,5-24,9", C["green"] if 18.5 <= imc < 25 else C["amber"], "⚖️"))

    st.markdown("### ❤️ Santé cardio-métabolique")
    n = v["cm_nombre"]
    if n is not None:
        presents = [(nom, v[f"cm_{cle}_traitement"]) for cle, nom in cotations.DIAG_CM if v[f"cm_{cle}"] == 1]
        if n == 0:
            st.caption("Vous n’avez déclaré aucun de ces problèmes : hypertension, diabète, cholestérol, autre dyslipidémie, maladie cardiovasculaire.")
            forts.append("Aucun problème cardio-métabolique déclaré.")
        else:
            rangee([carte("Problèmes déclarés", f"{n} / 5", "liste descriptive", C["violet"], "❤️")])
            pastilles([("💊" if t == 1 else "✅", nom, True, "traité actuellement" if t == 1 else "") for nom, t in presents])
            st.caption("Cette liste est descriptive : elle ne hiérarchise pas la gravité des problèmes.")
            pistes.append("Santé cardio-métabolique : un suivi régulier avec votre médecin permet de bien équilibrer ces problèmes.")

    st.markdown("### 👂 Audition et vision")
    cs = []
    aud, app, vis = v["audition_difficulte"], v["audition_appareil"], v["vision_difficulte"]
    if aud is not None:
        cs.append(carte("Audition", "Difficulté" if aud else "Pas de difficulté", "avec appareil auditif" if app == 1 else "", C["amber"] if aud else C["green"], "👂"))
        if aud and app == 0:
            pistes.append("Audition : un bilan auditif (ORL ou audioprothésiste) pourrait vous aider.")
    if vis is not None:
        cs.append(carte("Vision", "Difficulté" if vis else "Pas de difficulté", "malgré la correction" if vis else "", C["amber"] if vis else C["green"], "👁️"))
        if vis:
            pistes.append("Vision : un contrôle ophtalmologique régulier est conseillé.")
    rangee(cs)
    st.caption("Les autres informations médicales de ce module (antécédents neurologiques, etc.) ne sont pas reprises dans cette synthèse : votre médecin y a accès.")
    return dict(cartes=cartes, forts=forts, pistes=pistes)


REGISTRE = {"parcours_vie": rapport_parcours, "mode_de_vie": rapport_mode_de_vie, "exposome_psychosocial": rapport_exposome_psy, "expositions_environnementales": rapport_expositions, "sante_generale": rapport_sante}


# ---------------------------------------------------------------- rapport simple (modules sans rapport dédié)
def rapport_simple(m, r):
    st.subheader(m["titre"])
    res = scoring.score_module(m, r)
    if res:
        st.metric("Score", f"{res['score']} / {res['max']}")
        st.write(res["message"])
    with st.expander("Voir mes réponses"):
        for q in m["questions"]:
            v = r.get(q["id"])
            if q["type"] in ("section", "info") or (q.get("si") and vide(v)):
                continue
            v = ("Oui" if v else "Non") if isinstance(v, bool) else (", ".join(v) if isinstance(v, list) else v)
            st.write(f"**{q['texte']}** : {v if not vide(v) else '—'}")


# ---------------------------------------------------------------- page complète
def afficher_rapport(modules, reponses, age=None):
    modules = [m for m in modules if not m.get("hors_rapport")]
    Q = {q["id"]: q for m in modules for q in m["questions"]}
    st.markdown(
        f'<div style="padding:26px 24px;border-radius:22px;color:white;margin-bottom:14px;'
        f'background:linear-gradient(135deg,{C["indigo"]},{C["teal"]})">'
        f'<div style="font-size:1.9rem;font-weight:800">✨ Votre rapport de synthèse</div>'
        f'<div style="opacity:.9">Merci d’avoir répondu ! Voici ce que racontent vos réponses, partie par partie.</div></div>',
        unsafe_allow_html=True)
    st.info("Ce rapport est **indicatif** : il décrit vos réponses et les compare à des repères de santé publique. "
            "Il ne constitue **pas un diagnostic** et ne remplace pas l’avis d’un professionnel de santé.")

    noms = ["✨ En un coup d’œil"] + [m["titre"].split("–")[0].strip() for m in modules]
    onglets = st.tabs(noms)
    resumes = []
    for tab, m in zip(onglets[1:], modules):
        with tab:
            fonction = REGISTRE.get(m["id"])
            if fonction:
                resumes.append(fonction(reponses, Q, age, m))
            else:
                rapport_simple(m, reponses)
    with onglets[0]:
        cartes = [c for res in resumes for c in res["cartes"]]
        if cartes:
            st.markdown("### Votre synthèse en quelques chiffres")
            rangee(cartes)
        forts = [x for res in resumes for x in res["forts"]]
        pistes = [x for res in resumes for x in res["pistes"]]
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("### 🌱 Vos points forts")
            for x in forts[:8] or ["Merci d’avoir pris le temps de répondre."]:
                st.success(x)
        with c2:
            st.markdown("### 💡 Pistes pour aller plus loin")
            for x in pistes[:8] or ["Pas de piste particulière ressortant de vos réponses."]:
                st.warning(x)
        st.caption("Vous pouvez imprimer ou enregistrer cette page en PDF depuis votre navigateur (Ctrl+P).")
