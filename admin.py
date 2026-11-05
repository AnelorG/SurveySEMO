"""
admin.py : espace médecin (connexion, tableau de bord, dossier patient, ajout de patient).
Identifiants provisoires : voir ADMIN_LOGIN / ADMIN_MOT_DE_PASSE dans config.py.
"""
import hmac
from datetime import date, datetime
from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import accueil
import config
import db
import export_excel
import logique
import rendu_html
import report
import suivi

C = report.C
TAILLE_PAGE = 15

STYLE = " ".join("""
.block-container{max-width:1320px;padding-top:1.4rem;}
section[data-testid="stSidebar"]{background:#fff;border-right:1px solid var(--line);}
.med-titre{font-family:var(--f);font-size:2.1rem;font-weight:800;letter-spacing:-.03em;color:var(--ink);margin:.1rem 0 0;}
.med-sous{font-family:var(--f);color:var(--muted);margin:0 0 .6rem;}
.section{font-family:var(--f);font-size:1.2rem;font-weight:800;color:var(--ink);margin:2.2rem 0 .3rem;letter-spacing:-.01em;}
.note{font-family:var(--f);font-size:.86rem;color:var(--muted);margin:0 0 .8rem;line-height:1.45;}
.th{font-family:var(--f);font-size:.7rem;font-weight:700;color:#6b7a90;text-transform:uppercase;letter-spacing:.07em;}
.cell{font-family:var(--f);font-size:.92rem;color:var(--ink);}
.chip{position:relative;display:inline-block;min-width:64px;text-align:center;padding:4px 10px;border-radius:999px;font:700 .82rem var(--f);cursor:default;}
.chip.ok{background:rgba(16,185,129,.15);color:#047857;}
.chip.partiel{background:rgba(245,158,11,.20);color:#b45309;}
.chip.vide{background:rgba(100,116,139,.14);color:#475569;}
.chip:hover::after{content:attr(data-tip);position:absolute;z-index:99;left:50%;top:125%;transform:translateX(-50%);white-space:pre;
 background:#0b1f3a;color:#fff;padding:8px 12px;border-radius:10px;font:500 .78rem/1.5 var(--f);text-align:left;box-shadow:0 12px 24px rgba(11,31,58,.28);}
.grp{display:inline-block;padding:3px 10px;border-radius:8px;font:800 .72rem var(--f);letter-spacing:.06em;}
.grp.TEST{background:rgba(14,165,233,.15);color:#0369a1;}.grp.CONTROL{background:rgba(139,92,246,.15);color:#6d28d9;}.grp.x{background:#eef2f7;color:#64748b;}
[class*="st-key-ligne_"]{background:#fff;border:1px solid var(--line);border-radius:14px;padding:6px 14px;margin-bottom:6px;transition:box-shadow .15s,border-color .15s;}
[class*="st-key-ligne_"]:hover{border-color:#b6d9f2;box-shadow:0 8px 20px -12px rgba(0,134,195,.5);}
[class*="st-key-ligne_"],[class*="st-key-ligne_"] *{overflow:visible !important;}
[class*="st-key-ligne_"] [data-testid="stMarkdownContainer"] p{margin:0 !important;}
.cell{line-height:1.6;}
.st-key-ligne_entete{background:none !important;border:0 !important;box-shadow:none !important;padding:0 14px !important;margin-bottom:0 !important;}
[class*="st-key-num_"] button{background:none;border:0;padding:0;min-height:0;box-shadow:none;justify-content:flex-start;position:relative;top:6px;}
[class*="st-key-num_"] button p{color:#0086c3 !important;font-weight:800;text-decoration:underline dotted;}
.st-key-btn_ajout button{background:linear-gradient(135deg,#009EE0,#3b4cca);border:0;color:#fff !important;}
.st-key-btn_ajout button p{color:#fff !important;}
.st-key-nav_tableau button{background:rgba(0,158,224,.10);border:0;color:#0077b6 !important;justify-content:flex-start;}
.st-key-nav_tableau button p{color:#0077b6 !important;font-weight:800;}
.dossier{font-family:var(--f);border-radius:22px;padding:22px 26px;color:#fff;background:linear-gradient(135deg,#009EE0,#3b4cca);margin:.4rem 0 1rem;}
.dossier .grp{background:rgba(255,255,255,.24);color:#fff;}.dossier b{font-size:2rem;letter-spacing:-.02em}.dossier span{opacity:.92}
.de{font-family:var(--f);font-weight:800;font-size:1.5rem;color:var(--ink);letter-spacing:.02em;}
.sv{font-family:var(--f);background:#fff;border:1px solid var(--line);border-left:5px solid var(--c,#64748b);border-radius:14px;padding:12px 16px;margin:8px 0;}
.sv .t{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-weight:800;color:var(--ink);}
.sv .puce{display:inline-block;padding:2px 10px;border-radius:999px;background:rgba(100,116,139,.13);font:600 .78rem var(--f);color:#334155;margin:2px 4px 2px 0;}
.sv .com{color:#1f2d44;margin:.4rem 0 .2rem;white-space:pre-wrap;}.sv .pied{font-size:.78rem;color:var(--muted);}
.danger{font-family:var(--f);border:1px solid #fecaca;background:#fef2f2;border-radius:16px;padding:16px 20px;color:#7f1d1d;line-height:1.5;}
.st-key-sup_go button{background:#dc2626 !important;border:0;color:#fff !important;}.st-key-sup_go button p{color:#fff !important;}
.st-key-sup_go button:disabled{background:#e5e7eb !important;}.st-key-sup_go button:disabled p{color:#9ca3af !important;}
.st-key-mod_suppr_btn button{border-color:#fecaca;color:#b91c1c !important;}
""".split())


# ------------------------------------------------------------------ outils
def _date_fr(iso, avec_age=False):
    if not iso:
        return "—"
    d = datetime.fromisoformat(iso).date()
    txt = d.strftime("%d/%m/%Y")
    if avec_age:
        auj = date.today()
        txt += f" ({auj.year - d.year - ((auj.month, auj.day) < (d.month, d.day))} ans)"
    return txt


def _age(iso):
    if not iso:
        return None
    d = datetime.fromisoformat(iso).date()
    auj = date.today()
    return auj.year - d.year - ((auj.month, auj.day) < (d.month, d.day))


def _utilisateur():
    return st.session_state.get("med_utilisateur", "médecin")


def _court(m):
    return m["titre"].split("–")[0].strip()


def _badge_groupe(g):
    return f'<span class="grp {g if g in ("TEST", "CONTROL") else "x"}">{escape(g)}</span>'


def _donnees(modules):
    return suivi.analyser(modules, db.lister_patients(), db.toutes_reponses(), db.dates_passages())


# ------------------------------------------------------------------ connexion
def _connexion(aller):
    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        st.markdown(accueil.entete_connexion("Espace médecin", "Connectez-vous pour accéder au tableau de bord."),
                    unsafe_allow_html=True)
        with st.form("login_medecin"):
            identifiant = st.text_input("Identifiant")
            mdp = st.text_input("Mot de passe", type="password")
            ok = st.form_submit_button("Se connecter")
        if ok:
            bon_id = hmac.compare_digest(identifiant.strip().encode(), getattr(config, "ADMIN_LOGIN", "cercog").encode())
            bon_mdp = hmac.compare_digest(mdp.encode(), getattr(config, "ADMIN_MOT_DE_PASSE", "cercog").encode())
            if bon_id and bon_mdp:
                st.session_state["medecin"] = True
                st.session_state["med_utilisateur"] = identifiant.strip()
                st.rerun()
            st.error("Identifiant ou mot de passe incorrect.")
        if st.button("← Retour à l’accueil", key="retour_admin"):
            aller("accueil")


# ------------------------------------------------------------------ ajout d'un patient
@st.dialog("Ajouter un nouveau patient")
def dialogue_ajout():
    fait = st.session_state.get("aj_fait")
    if fait:
        numero, groupe, naissance = fait
        st.success("Patient enregistré.")
        st.markdown(f'<div class="de">{numero}</div>' f'<p class="note">Groupe {_badge_groupe(groupe)} · à remettre au patient avec sa '
                    f'date de naissance ({_date_fr(naissance)}) pour qu’il se connecte.</p>', unsafe_allow_html=True)
        if st.button("Fermer", type="primary", key="aj_fermer"):
            st.session_state.pop("aj_fait", None)
            st.rerun()
        return
    nom = st.text_input("Nom", key="aj_nom")
    prenom = st.text_input("Prénom", key="aj_prenom")
    naissance = st.date_input("Date de naissance (obligatoire)", value=None, min_value=date(1900, 1, 1),
                              max_value=date.today(), format="DD/MM/YYYY", key="aj_naiss")
    st.markdown('<p class="note" style="margin:.4rem 0 .2rem">Numéro de randomisation</p>', unsafe_allow_html=True)
    c1, c2 = st.columns([1, 3], vertical_alignment="center")
    if c1.button("🎲", key="aj_de", help="Tirer un numéro au hasard (P001 à P999)"):
        st.session_state["aj_numero"] = db.tirer_numero()
    numero = st.session_state.get("aj_numero")
    if numero:
        c2.markdown(f'<span class="de">{numero}</span> &nbsp; {_badge_groupe(db.groupe_pour(numero))}', unsafe_allow_html=True)
    else:
        c2.markdown('<span class="note">Cliquez sur le dé pour tirer un numéro.</span>', unsafe_allow_html=True)
    if st.button("Enregistrer le patient", type="primary", disabled=not (naissance and numero), key="aj_save"):
        if db.ajouter_patient(numero, nom.strip(), prenom.strip(), naissance, _utilisateur()):
            st.session_state["aj_fait"] = (numero, db.groupe_pour(numero), naissance.isoformat())
            st.session_state.pop("aj_numero", None)
            st.rerun(scope="fragment")
        else:
            st.error("Ce numéro vient d’être attribué : tirez-en un autre.")
            st.session_state.pop("aj_numero", None)


# ------------------------------------------------------------------ export des données
@st.dialog("Exporter les données")
def dialogue_export():
    n_pat = len(db.lister_patients())
    n_pass = sum(len(v) for v in db.toutes_reponses().values())
    st.markdown(f"Fichier Excel complet : **{n_pat} patient(s)**, **{n_pass} passage(s)**.")
    st.markdown('<p class="note">9 feuilles : listing des patients · scores et complétion · réponses par passage · '
                'scores calculés · réponses au format long · suivi et événements · journal d’audit · dictionnaire des variables · informations.</p>', unsafe_allow_html=True)
    st.warning("Ce fichier contient des données **nominatives** et de santé : conservez-le sur un poste ou un serveur sécurisé "
               "et ne l’envoyez pas par e-mail non chiffré.")
    if st.button("Générer le fichier Excel", type="primary", key="exp_gen"):
        with st.spinner("Génération du fichier…"):
            t = datetime.now()
            st.session_state["exp_fichier"] = (export_excel.nom_fichier(t), export_excel.construire(logique.charger_modules(), t))
            db.journaliser("Export des données", None, {"fichier": st.session_state["exp_fichier"][0]}, _utilisateur())
    fichier = st.session_state.get("exp_fichier")
    if fichier:
        st.success(f"Fichier prêt : {fichier[0]}")
        st.download_button("⬇️ Télécharger le fichier Excel", fichier[1], file_name=fichier[0], mime=export_excel.MIME, key="exp_dl")


# ------------------------------------------------------------------ barre latérale
def _barre_laterale(aller):
    with st.sidebar:
        st.markdown(accueil.logo_html(64), unsafe_allow_html=True)
        st.markdown('<p class="note" style="margin:.6rem 0 1rem">Espace médecin</p>', unsafe_allow_html=True)
        if st.button("📊  Tableau de bord", key="nav_tableau"):
            st.session_state["med_dossier"] = None
            st.session_state["med_vue"] = None
            st.rerun()
        st.markdown("<div style='height:.8rem'></div>", unsafe_allow_html=True)
        if st.button("➕  Ajouter un nouveau patient", key="btn_ajout"):
            for k in ("aj_fait", "aj_numero", "aj_nom", "aj_prenom", "aj_naiss"):
                st.session_state.pop(k, None)
            dialogue_ajout()
        if st.button("✏️  Modifier un patient", key="btn_modif"):
            _ouvrir_modification(st.session_state.get("med_dossier"))
        if st.button("📤  Exporter les données", key="btn_export"):
            st.session_state.pop("exp_fichier", None)
            dialogue_export()
        st.markdown("<div style='height:2rem'></div>", unsafe_allow_html=True)
        if st.button("← Accueil", key="med_accueil"):
            aller("accueil")
        if st.button("Se déconnecter", key="med_deconnexion"):
            for k in [k for k in st.session_state if k.startswith(("med", "aj_", "rapport_"))] + ["medecin"]:
                st.session_state.pop(k, None)
            aller("accueil")


# ------------------------------------------------------------------ graphiques
def _vide(texte):
    st.markdown(f'<p class="note">{texte}</p>', unsafe_allow_html=True)


def _g_groupes(an):
    nt, nc = an["par_groupe"]["TEST"]["n"], an["par_groupe"]["CONTROL"]["n"]
    fig = go.Figure(go.Pie(labels=["TEST", "CONTROL"], values=[nt, nc], hole=.7, sort=False, textinfo="label+value",
                           marker=dict(colors=[C["sky"], C["violet"]], line=dict(color="#fff", width=4))))
    fig.add_annotation(text=f"<b>{an['n']}</b><br><span style='font-size:13px'>patients</span>", showarrow=False, font=dict(size=30))
    fig.update_layout(showlegend=False, title="Répartition des groupes")
    return report.style(fig, 320)


def _g_statuts(an):
    fig = go.Figure()
    for lab, n, col in (("Terminé", an["n_termine"], C["green"]), ("En cours", an["n_en_cours"], C["amber"]),
                        ("Non démarré", an["n_non_demarre"], "#94a3b8")):
        fig.add_trace(go.Bar(y=[""], x=[n], orientation="h", name=lab, marker=dict(color=col, cornerradius=10),
                             text=[n if n else ""], textposition="inside", textfont=dict(color="#fff", size=16)))
    fig.update_layout(barmode="stack", title="Avancement des patients", legend=dict(orientation="h", y=-0.25, traceorder="normal"),
                      xaxis=dict(visible=False), yaxis=dict(visible=False))
    return report.style(fig, 190)


def _g_modules(an, modules):
    mods = an["suivis"]
    vals = [an["par_module"][m["id"]] for m in mods]
    fig = go.Figure(go.Bar(
        x=vals, y=[_court(m) for m in mods], orientation="h", text=[f"{v:.0f} %" for v in vals], textposition="outside",
        cliponaxis=False, marker=dict(color=vals, cmin=0, cmax=100, cornerradius=10,
                                      colorscale=[[0, "#fda4af"], [.5, "#fcd34d"], [1, "#34d399"]])))
    fig.update_layout(title="Patients ayant complété chaque partie", xaxis=dict(range=[0, 112], ticksuffix=" %"))
    fig.update_yaxes(autorange="reversed")
    return report.style(fig, 120 + 56 * len(mods))


def _g_patients(an):
    fig = go.Figure()
    if an["n"] > 1:
        fig.add_hrect(y0=max(an["moyenne"] - an["sd"], 0), y1=min(an["moyenne"] + an["sd"], 100),
                      fillcolor=C["indigo"], opacity=.10, line_width=0)
    fig.add_hline(y=an["moyenne"], line_dash="dot", line_color=C["indigo"])
    for g, col in (("TEST", C["sky"]), ("CONTROL", C["violet"])):
        ls = [l for l in an["lignes"] if l["groupe"] == g]
        fig.add_trace(go.Bar(x=[l["numero"] for l in ls], y=[l["pct_complets"] for l in ls], name=g,
                             marker=dict(color=col, cornerradius=8)))
    fig.update_layout(title=f"Parties complétées par patient · moyenne {an['moyenne']:.0f} % ± {an['sd']:.0f} (zone ombrée)", yaxis=dict(range=[0, 105], ticksuffix=" %"),
                      legend=dict(orientation="h", y=-0.2), barmode="group")
    return report.style(fig, 360)


# ------------------------------------------------------------------ tableau de bord
def _tableau_de_bord(modules):
    an = _donnees(modules)
    st.markdown('<div class="med-titre">Tableau de bord</div>'
                f'<p class="med-sous">Mis à jour le {datetime.now():%d/%m/%Y à %H:%M}</p>', unsafe_allow_html=True)
    if an["n"] == 0:
        st.info("Aucun patient inclus pour l’instant. Utilisez « Ajouter un nouveau patient » dans le menu de gauche.")
        return

    st.markdown('<div class="section">👥 Inclusion</div>', unsafe_allow_html=True)
    pg = an["par_groupe"]
    report.rangee([
        report.carte("Patients inclus", an["n"], icone="👥", couleur=C["indigo"]),
        report.carte("Groupe TEST", pg["TEST"]["n"], icone="🧪", couleur=C["sky"]),
        report.carte("Groupe CONTROL", pg["CONTROL"]["n"], icone="⚖️", couleur=C["violet"]),
        report.carte("Questionnaire terminé", f"{an['n_termine']} / {an['n']}", f"{100 * an['n_termine'] / an['n']:.0f} % des patients",
                     icone="✅", couleur=C["green"]),
        report.carte("Ont repassé le test", an["n_repasses"], icone="🔁", couleur=C["teal"]),
    ])
    c1, c2 = st.columns([1, 1.5], gap="large", vertical_alignment="center")
    c1.plotly_chart(_g_groupes(an))
    c2.plotly_chart(_g_statuts(an))

    st.markdown('<div class="section">📈 Complétion des questionnaires</div>', unsafe_allow_html=True)
    st.markdown('<p class="note">Un module compte comme complété seulement si <b>toutes</b> ses questions obligatoires sont '
                'renseignées (un module partiel n’est pas complété). Calculs sur le <b>dernier passage</b> de chaque patient.</p>',
                unsafe_allow_html=True)
    report.rangee([
        report.carte("Parties complétées · tous patients", f"{an['moyenne']:.0f} % ± {an['sd']:.0f}", "moyenne ± écart type entre patients",
                     icone="🎯", couleur=C["indigo"]),
        report.carte("Parties complétées · par module", f"{an['module_moyenne']:.0f} % ± {an['module_sd']:.0f}",
                     "moyenne ± écart type entre modules", icone="🧩", couleur=C["teal"]),
        report.carte("Groupe TEST", f"{pg['TEST']['moyenne']:.0f} % ± {pg['TEST']['sd']:.0f}", f"{pg['TEST']['n']} patients",
                     icone="🧪", couleur=C["sky"]),
        report.carte("Groupe CONTROL", f"{pg['CONTROL']['moyenne']:.0f} % ± {pg['CONTROL']['sd']:.0f}", f"{pg['CONTROL']['n']} patients",
                     icone="⚖️", couleur=C["violet"]),
    ])
    c1, c2 = st.columns(2, gap="large")
    c1.plotly_chart(_g_modules(an, modules))
    c2.plotly_chart(_g_patients(an))

    st.markdown('<div class="section">📋 Patients</div>', unsafe_allow_html=True)
    st.markdown('<p class="note">Survolez un score pour voir l’historique des passages. Cliquez sur un numéro pour ouvrir le dossier. '
                'Sans règle de score définie pour un module, une partie complète s’affiche « 100 % ».</p>', unsafe_allow_html=True)
    _tableau_patients(an)


def _chip(l, m):
    dernier, hist = l["dernier"][m["id"]], l["hist"][m["id"]]
    tip = "&#10;".join(f"{suivi.ordinal(n)} passage : {escape(s['texte'])}" + (f" — {escape(s['resume'])}" if s.get("resume") else "") for n, s in hist) if hist else "Aucun passage"
    classe = {"complet": "ok", "partiel": "partiel", "vide": "vide"}[dernier["etat"]]
    return f'<span class="chip {classe}" data-tip="{tip}">{escape(dernier["texte"])}</span>'


def _tableau_patients(an):
    recherche = st.text_input("🔍 Rechercher (numéro, nom, prénom)", key="med_recherche").strip().lower()
    lignes = [l for l in an["lignes"] if not recherche or recherche in f"{l['numero']} {l['nom']} {l['prenom']}".lower()]
    pages = max((len(lignes) - 1) // TAILLE_PAGE + 1, 1)
    if st.session_state.get("med_recherche_prec") != recherche:
        st.session_state["med_page"], st.session_state["med_recherche_prec"] = 0, recherche
    page = min(st.session_state.get("med_page", 0), pages - 1)
    suivis = an["suivis"]
    poids = [1, .9, 1.3, 1.3, 1.1] + [1] * len(suivis) + [.8]
    entetes = ["N° rando", "Groupe", "Nom", "Prénom", "Naissance"] + [_court(m) for m in suivis] + ["Consent."]
    with st.container(key="ligne_entete"):
        for col, t in zip(st.columns(poids), entetes):
            col.markdown(f'<div class="th">{escape(t)}</div>', unsafe_allow_html=True)
    for l in lignes[page * TAILLE_PAGE:(page + 1) * TAILLE_PAGE]:
        with st.container(key=f"ligne_{l['numero']}"):
            cols = st.columns(poids, vertical_alignment="center")
            if cols[0].button(l["numero"], key=f"num_{l['numero']}"):
                st.session_state["med_dossier"] = l["numero"]
                st.rerun()
            cols[1].markdown(_badge_groupe(l["groupe"]), unsafe_allow_html=True)
            cols[2].markdown(f'<div class="cell">{escape(l["nom"]) or "—"}</div>', unsafe_allow_html=True)
            cols[3].markdown(f'<div class="cell">{escape(l["prenom"]) or "—"}</div>', unsafe_allow_html=True)
            cols[4].markdown(f'<div class="cell">{_date_fr(l["naissance"])}</div>', unsafe_allow_html=True)
            for col, m in zip(cols[5:5 + len(suivis)], suivis):
                col.markdown(_chip(l, m), unsafe_allow_html=True)
            cols[-1].markdown(f'<div class="cell">{"✔" if l["consent"] else "—"}</div>', unsafe_allow_html=True)
    if not lignes:
        _vide("Aucun patient ne correspond à la recherche.")
    if pages > 1:
        p1, p2, p3 = st.columns([1, 2, 1], vertical_alignment="center")
        if p1.button("‹ Précédent", disabled=page == 0, key="pg_prec"):
            st.session_state["med_page"] = page - 1
            st.rerun()
        p2.markdown(f'<p class="note" style="text-align:center;margin:0">Page {page + 1} / {pages} · {len(lignes)} patients</p>',
                    unsafe_allow_html=True)
        if p3.button("Suivant ›", disabled=page >= pages - 1, key="pg_suiv"):
            st.session_state["med_page"] = page + 1
            st.rerun()


# ------------------------------------------------------------------ dossier d'un patient
def _fmt(v):
    if v is None or v == "" or v == []:
        return "—"
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    if isinstance(v, list):
        return ", ".join(map(str, v))
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _dossier(modules, numero):
    an = _donnees(modules)
    l = next((x for x in an["lignes"] if x["numero"] == numero), None)
    if l is None:
        st.session_state["med_dossier"] = None
        st.rerun()
    b1, b2, _ = st.columns([1.2, 1.1, 4])
    if b1.button("← Retour au tableau de bord", key="med_retour"):
        st.session_state["med_dossier"] = None
        st.rerun()
    if b2.button("✏️ Modifier ce patient", key="med_modifier_dossier"):
        _ouvrir_modification(numero)
    nom = f"{l['prenom']} {l['nom']}".strip() or "Identité non renseignée"
    st.markdown(f'<div class="dossier"><b>{numero}</b> &nbsp; {_badge_groupe(l["groupe"])}<br><span>{escape(nom)} · né(e) le '
                f'{_date_fr(l["naissance"], True)} · {len(l["passages"])} passage(s)'
                f'{" · dernière activité le " + _date_fr(l["derniere_activite"][:10]) if l["derniere_activite"] else ""}</span></div>',
                unsafe_allow_html=True)
    if not l["passages"]:
        st.info("Ce patient n’a pas encore répondu au questionnaire.")
        return
    dates = db.dates_passages().get(numero, {})
    passage = l["passages"][-1]
    if len(l["passages"]) > 1:
        passage = st.selectbox("Passage affiché", l["passages"], index=len(l["passages"]) - 1, key="med_passage",
                               format_func=lambda p: f"{suivi.ordinal(p)} passage · {_date_fr((dates.get(p) or '')[:10])}")
    rep = db.charger_reponses(numero, passage)

    cle = f"rapport_{numero}_{passage}"
    c1, c2, _ = st.columns([1.4, 1, 3], vertical_alignment="center")
    if c1.button("📄 Générer le rapport de synthèse", key="med_prep", type="primary"):
        with st.spinner("Génération du rapport…"):
            st.session_state[cle] = rendu_html.generer(
                modules, rep, age=_age(l["naissance"]),
                entete=f"Participant {numero} · groupe {l['groupe']} · {suivi.ordinal(passage)} passage")
    if cle in st.session_state:
        if c2.button("Fermer l’aperçu", key="med_fermer"):
            st.session_state.pop(cle, None)
            st.rerun()
    if cle in st.session_state:
        st.markdown('<p class="note">Rapport prêt, au format A4. Cliquez sur <b>« Imprimer / Enregistrer en PDF »</b> dans l’aperçu ci-dessous, '
                    'puis choisissez <b>« Enregistrer au format PDF »</b> comme destination (ou votre imprimante).</p>', unsafe_allow_html=True)
        components.html(st.session_state[cle].decode("utf-8"), height=820, scrolling=True)

    t1, t2, t3 = st.tabs(["📊 Synthèse graphique", "🔢 Réponses détaillées", "🕘 Historique des scores"])
    with t1:
        report.afficher_rapport(modules, rep, age=_age(l["naissance"]))
    with t2:
        for m in modules:
            s = suivi.statut_module(m, rep)
            with st.expander(f"{m['titre']} · {s['texte']}" + ("" if s["etat"] == "complet" else " (incomplet)")):
                lignes = [{"Question": q["texte"], "Réponse": _fmt(rep.get(q["id"]))} for q in m["questions"]
                          if q["type"] not in ("section", "info") and logique.est_visible(q, rep)]
                if lignes:
                    st.dataframe(pd.DataFrame(lignes), hide_index=True)
    with t3:
        lignes = []
        for m in an["suivis"]:
            ligne = {"Partie": m["titre"]}
            for n, s in l["hist"][m["id"]]:
                ligne[f"{suivi.ordinal(n)} passage"] = s["texte"]
            lignes.append(ligne)
        st.dataframe(pd.DataFrame(lignes).fillna("—"), hide_index=True)


# ------------------------------------------------------------------ modifier un patient
CATEGORIES = {
    "Effet indésirable": ("#dc2626", ["Fatigue / somnolence", "Céphalées", "Troubles du sommeil", "Nausées / troubles digestifs",
                                      "Vertiges / malaise", "Anxiété / humeur dépressive", "Troubles de l’attention ou de la mémoire",
                                      "Réaction cutanée", "Aucun effet indésirable déclaré"]),
    "Remarque liée à l’essai": ("#4f46e5", ["Écart au protocole", "Information transmise au promoteur", "Participation suspendue temporairement",
                                           "Retrait de consentement évoqué", "Perdu de vue / injoignable", "Changement de coordonnées",
                                           "Changement de traitement"]),
    "Plainte du patient": ("#d97706", ["Difficulté d’utilisation du site", "Questionnaire trop long", "Questions mal comprises",
                                       "Gêne face à certaines questions", "Problème de connexion ou d’identifiants",
                                       "Souhait d’arrêter de participer", "Inquiétude sur la confidentialité des données"]),
    "Condition de complétion du questionnaire": ("#0d9488", ["Complété sans aide", "Complété avec l’aide d’un proche",
                                                              "Complété avec l’aide d’un membre de l’équipe", "Complété à domicile",
                                                              "Complété lors d’une consultation", "Complété sur ordinateur",
                                                              "Complété sur smartphone ou tablette", "Complété en plusieurs fois",
                                                              "Interrompu : fatigue", "Interrompu : difficulté de compréhension",
                                                              "Interrompu : problème technique"]),
    "Autre information": ("#64748b", []),
}
GRAVITES = ["Légère", "Modérée", "Sévère"]
EVOLUTIONS = ["En cours", "Résolu", "Résolu avec séquelles", "Inconnue"]
MOTIFS = ["Retrait de consentement avec demande d’effacement des données", "Demande d’exercice du droit à l’effacement (RGPD)",
          "Patient inclus par erreur", "Doublon (patient déjà inclus sous un autre numéro)",
          "Patient non éligible (critère de non-inclusion découvert après l’inclusion)",
          "Données de test ou compte de démonstration", "Autre (à préciser)"]
MOTIF_AUTRE = MOTIFS[-1]
CHOISIR = "— Choisir un motif —"


def _ouvrir_modification(numero):
    if numero:
        st.session_state["mod_patient"] = numero
    st.session_state["med_vue"] = "modifier"
    st.rerun()


def _flash():
    f = st.session_state.pop("med_flash", None)
    if f:
        {"ok": st.success, "erreur": st.error}.get(f[0], st.info)(f[1])


def _cb_suivi(numero, slug):
    """Callback du bouton « Enregistrer » (s'exécute avant le rafraîchissement de la page)."""
    ss = st.session_state
    categorie = ss.get("sv_type")
    options, commentaire = ss.get(f"sv_opts_{slug}", []), (ss.get("sv_com") or "").strip()
    if not options and not commentaire:
        ss["med_flash"] = ("erreur", "Cochez au moins une option ou écrivez un commentaire avant d’enregistrer.")
        return
    est_ei = categorie == "Effet indésirable"
    db.ajouter_suivi(numero, categorie, options, ss.get("sv_grav") if est_ei else None, ss.get("sv_evol") if est_ei else None,
                     ss.get("sv_grave") if est_ei else False, ss.get("sv_date"), commentaire, _utilisateur())
    ss[f"sv_opts_{slug}"], ss["sv_com"], ss["sv_grave"] = [], "", False
    ss["med_flash"] = ("ok", f"Information enregistrée dans le suivi de {numero}.")


@st.dialog("Supprimer définitivement ce patient ?")
def dialogue_suppression(numero):
    if st.session_state.get("sup_fait"):
        st.success(f"Le patient {numero} a été supprimé.")
        if st.button("Retour au tableau de bord", type="primary", key="sup_fin"):
            for k in ("sup_fait", "sup_motif", "sup_prec", "sup_ok", "mod_patient"):
                st.session_state.pop(k, None)
            st.session_state["med_vue"], st.session_state["med_dossier"] = None, None
            st.rerun()
        return
    st.markdown(
        f'<div class="danger"><b>⚠️ Cette action est irréversible.</b><br>Toutes les données du patient <b>{numero}</b> '
        'sont effacées de la base de données actuelle : identité, réponses aux questionnaires et suivi. '
        'Elles n’apparaîtront donc <b>plus dans les prochains exports</b>, qu’ils soient manuels ou automatiques '
        '(prévu chaque soir à 22 h).<br><br>Seule une trace minimale reste dans le journal d’audit : numéro, date, motif et '
        'utilisateur, sans aucune donnée personnelle ni de santé. Ce numéro ne sera jamais réattribué.</div>', unsafe_allow_html=True)
    motif = st.selectbox("Motif de la suppression (obligatoire)", [CHOISIR] + MOTIFS, key="sup_motif")
    precision = st.text_area("Précisions" + (" (obligatoire)" if motif == MOTIF_AUTRE else " (facultatif)"), key="sup_prec",
                             help="Ne saisissez ni nom ni information de santé.")
    compris = st.checkbox("J’ai compris que cette suppression est définitive et irréversible : les données de ce patient "
                          "seront effacées et ne pourront pas être récupérées.", key="sup_ok")
    pret = motif != CHOISIR and compris and (motif != MOTIF_AUTRE or bool(precision.strip()))
    if st.button("Supprimer définitivement", disabled=not pret, key="sup_go"):
        db.supprimer_patient(numero, motif, precision, _utilisateur())
        for k in [k for k in st.session_state if k.startswith("rapport_")] + ["exp_fichier"]:
            st.session_state.pop(k, None)  # aucun fichier déjà préparé ne doit contenir ce patient
        st.session_state["sup_fait"] = True
        st.rerun(scope="fragment")


def _txt_journal(e):
    d = e["details"]
    if not d:
        return ""
    if d.get("efface"):
        return "(contenu effacé)"
    if "motif" in d:
        return f"Motif : {d['motif']}" + (f" — {d['precision']}" if d.get("precision") else "")
    if all(isinstance(v, dict) and "avant" in v for v in d.values()):
        return " ; ".join(f"{k} : {v['avant'] or '—'} → {v['apres'] or '—'}" for k, v in d.items())
    return " ; ".join(f"{k} : {v}" for k, v in d.items())


def _modifier():
    b1, _ = st.columns([1.2, 5])
    if b1.button("← Retour au tableau de bord", key="mod_retour"):
        st.session_state["med_vue"] = None
        st.rerun()
    st.markdown('<div class="med-titre">Modifier un patient</div>', unsafe_allow_html=True)
    patients = db.lister_patients()
    if not patients:
        st.info("Aucun patient à modifier.")
        return
    par_num = {p["numero"]: p for p in patients}
    libelle = lambda n: f"{n} · {(par_num[n]['prenom'] + ' ' + par_num[n]['nom']).strip() or 'identité non renseignée'} · {par_num[n]['groupe']}"
    if st.session_state.get("mod_patient") not in par_num:
        st.session_state.pop("mod_patient", None)
    numero = st.selectbox("Patient (tapez un numéro ou un nom pour chercher)", list(par_num), key="mod_patient", format_func=libelle)
    p = par_num[numero]
    st.markdown(f'<div class="dossier"><b>{numero}</b> &nbsp; {_badge_groupe(p["groupe"])}<br><span>'
                f'{escape((p["prenom"] + " " + p["nom"]).strip() or "Identité non renseignée")} · né(e) le '
                f'{_date_fr(p["naissance"], True)}</span></div>', unsafe_allow_html=True)
    _flash()
    t1, t2, t3 = st.tabs(["✏️ Informations de base", "📝 Suivi et remarques", "🗑️ Supprimer le patient"])

    with t1:
        st.markdown('<p class="note">Modifiez le nom, le prénom ou la date de naissance. Les changements sont enregistrés dans le journal d’audit.</p>',
                    unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        nom = c1.text_input("Nom", value=p["nom"], key=f"mod_nom_{numero}")
        prenom = c2.text_input("Prénom", value=p["prenom"], key=f"mod_prenom_{numero}")
        naiss = c3.date_input("Date de naissance", value=datetime.fromisoformat(p["naissance"]).date() if p["naissance"] else None,
                              min_value=date(1900, 1, 1), max_value=date.today(), format="DD/MM/YYYY", key=f"mod_naiss_{numero}")
        change = naiss is not None and (nom.strip() != p["nom"] or prenom.strip() != p["prenom"] or naiss.isoformat() != p["naissance"])
        if st.button("Enregistrer les modifications", type="primary", disabled=not change, key="mod_save"):
            ch = db.modifier_identite(numero, nom, prenom, naiss, _utilisateur())
            noms = {"nom": "nom", "prenom": "prénom", "naissance": "date de naissance"}
            msg = "Modifié : " + ", ".join(noms[k] for k in ch) + "."
            if "naissance" in ch:
                msg += " Le patient doit désormais se connecter avec sa nouvelle date de naissance."
            st.session_state["med_flash"] = ("ok", msg)
            st.rerun()
        if db.tentatives_connexion().get(numero, 0) >= db.MAX_TENTATIVES:
            st.warning("Le compte de ce patient est bloqué (trop d’échecs de connexion).")
            if st.button("🔓 Débloquer le compte", key="mod_debloquer"):
                db.debloquer_compte(numero, _utilisateur())
                st.session_state["med_flash"] = ("ok", "Compte débloqué.")
                st.rerun()

    with t2:
        categorie = st.selectbox("Type d’information", list(CATEGORIES), key="sv_type")
        couleur, options = CATEGORIES[categorie]
        slug = "".join(ch for ch in categorie.lower() if ch.isalpha())[:12]
        if categorie == "Effet indésirable":
            st.markdown('<p class="note">Un effet indésirable <b>grave</b> doit être déclaré sans délai au promoteur selon la procédure '
                        'de l’étude : cette application ne remplace pas cette déclaration.</p>', unsafe_allow_html=True)
        if options:
            st.multiselect("Options prédéfinies", options, key=f"sv_opts_{slug}", placeholder="Choisir une ou plusieurs options")
        else:
            st.session_state.setdefault(f"sv_opts_{slug}", [])
        if categorie == "Effet indésirable":
            g1, g2, g3 = st.columns(3, vertical_alignment="bottom")
            g1.selectbox("Gravité", GRAVITES, key="sv_grav")
            g2.selectbox("Évolution", EVOLUTIONS, key="sv_evol")
            g3.checkbox("Effet indésirable grave", key="sv_grave")
        st.date_input("Date de l’événement", value=date.today(), max_value=date.today(), format="DD/MM/YYYY", key="sv_date")
        st.text_area("Commentaire libre", key="sv_com", placeholder="Précisions, contexte, décision prise…")
        st.button("Enregistrer dans le suivi", type="primary", key="sv_save", on_click=_cb_suivi, args=(numero, slug))
        st.markdown('<div class="section" style="font-size:1.05rem;margin-top:1.4rem">Historique du suivi</div>', unsafe_allow_html=True)
        entrees = db.lister_suivi(numero)
        if not entrees:
            _vide("Aucune information de suivi enregistrée pour ce patient.")
        for e in entrees:
            coul = CATEGORIES.get(e["categorie"], ("#64748b", []))[0]
            extra = ""
            if e["categorie"] == "Effet indésirable":
                extra = f' · {escape(e["gravite"] or "")} · {escape(e["evolution"] or "")}' + (" · <span style='color:#b91c1c'>GRAVE</span>" if e["grave"] else "")
            puces = "".join(f'<span class="puce">{escape(o)}</span>' for o in e["options"])
            st.markdown(f'<div class="sv" style="--c:{coul}"><div class="t">{escape(e["categorie"])}{extra}'
                        f'<span style="font-weight:500;color:#64748b;font-size:.85rem">{_date_fr(e["date_evenement"])}</span></div>'
                        f'{puces}<div class="com">{escape(e["commentaire"])}</div>'
                        f'<div class="pied">Saisi le {_date_fr(e["cree_le"][:10])} par {escape(e["cree_par"] or "")}</div></div>', unsafe_allow_html=True)
        with st.expander("🕘 Journal des modifications de ce patient"):
            journal = db.lire_journal(numero)
            if journal:
                st.dataframe(pd.DataFrame([{"Date et heure": e["date_heure"].replace("T", " "), "Utilisateur": e["utilisateur"],
                                            "Action": e["action"], "Détails": _txt_journal(e)} for e in journal]), hide_index=True)

    with t3:
        st.markdown('<div class="danger">La suppression efface définitivement l’identité, les réponses et le suivi de ce patient. '
                    'Elle nécessite un motif et une confirmation.</div>', unsafe_allow_html=True)
        st.markdown("<div style='height:.6rem'></div>", unsafe_allow_html=True)
        if st.button("🗑️ Supprimer ce patient…", key="mod_suppr_btn"):
            for k in ("sup_fait", "sup_motif", "sup_prec", "sup_ok"):
                st.session_state.pop(k, None)
            dialogue_suppression(numero)


# ------------------------------------------------------------------ point d'entrée
def afficher(aller):
    if not st.session_state.get("medecin"):
        _connexion(aller)
        return
    st.markdown(f"<style>{STYLE}</style>", unsafe_allow_html=True)
    db.init_db()
    modules = logique.charger_modules()
    _barre_laterale(aller)
    if st.session_state.get("med_vue") == "modifier":
        _modifier()
    elif st.session_state.get("med_dossier"):
        _dossier(modules, st.session_state["med_dossier"])
    else:
        _tableau_de_bord(modules)
