"""
app.py : l'application Streamlit (ce que voit le participant).
NE PAS lancer avec F5 dans Spyder : voir LISEZMOI.md (commande streamlit run app.py).
"""
import glob
import os
import re
from datetime import date, datetime

import plotly.graph_objects as go
import streamlit as st
import yaml

import accueil
import admin
import config
import db
import report
from logique import charger_modules, est_manquante, est_vide, est_visible, premiere_etape

DOSSIER = os.path.dirname(os.path.abspath(__file__))
st.set_page_config(page_title=accueil.TITRE_PAGE, page_icon="🩺", initial_sidebar_state="expanded")


def _streamlit_assez_recent(minimum=(1, 40)):
    """Le design (accueil, espace médecin) demande Streamlit >= 1.40."""
    morceaux = tuple(int(x) for x in re.findall(r"\d+", st.__version__)[:2])
    return morceaux >= minimum


if not _streamlit_assez_recent():
    st.error(f"Votre version de Streamlit ({st.__version__}) est trop ancienne pour cette application (il faut la version 1.40 ou plus).")
    st.write("Fermez l'application (Ctrl+C dans Anaconda Prompt), puis tapez :")
    st.code("pip install --upgrade streamlit", language="bash")
    st.write("Relancez ensuite : `streamlit run app.py`")
    st.stop()
db.init_db()


# ---------- Fonctions utilitaires ----------
def premier_module_modifiable(modules):
    """Index du 1er module qui n'est pas marqué 'unique: true' (ex. le consentement, qui ne s'affiche qu'une fois)."""
    return next((i for i, m in enumerate(modules) if not m.get("unique")), 0)


def afficher_question(q, ancienne):
    """Affiche le bon type de champ selon q['type'] et renvoie la réponse saisie."""
    t = q["type"]
    label = q["texte"] + ("" if q.get("obligatoire", True) else " *(facultatif)*")
    cle = q["id"]
    if t == "section":
        st.subheader(q["texte"])
        return None
    if t == "info":
        st.markdown(q["texte"])
        return None
    if t == "texte_libre":
        return st.text_area(label, value=ancienne or "", key=cle)
    if t == "texte_court":
        return st.text_input(label, value=ancienne or "", key=cle)
    if t == "nombre":
        return st.number_input(
            label,
            min_value=float(q.get("min", 0)),
            max_value=float(q.get("max", 1000)),
            step=float(q.get("pas", 1)),
            value=None if ancienne is None else float(ancienne),
            format="%g",
            key=cle,
        )
    if t in ("choix_unique", "oui_non"):
        options = ["Oui", "Non"] if t == "oui_non" else q["options"]
        index = options.index(ancienne) if ancienne in options else None
        return st.radio(label, options, index=index, key=cle, horizontal=q.get("horizontal", False))
    if t == "choix_multiple":
        defaut = [o for o in (ancienne or []) if o in q["options"]]
        return st.multiselect(label, q["options"], default=defaut, key=cle)
    if t == "case_a_cocher":
        return st.checkbox(label, value=bool(ancienne), key=cle)
    if t == "heure":
        try:
            valeur = datetime.strptime(ancienne, "%H:%M").time() if ancienne else None
            choisie = st.time_input(label, value=valeur, key=cle, step=300)
            return choisie.strftime("%H:%M") if choisie else None
        except TypeError:  # version de Streamlit sans heure vide : saisie texte HH:MM
            return st.text_input(label + " (HH:MM)", value=ancienne or "", key=cle) or None
    st.warning(f"Type de question inconnu : {t}")
    return None


def passage_complet(modules, pid, p):
    return premiere_etape(modules, db.charger_reponses(pid, p)) == len(modules)


def ouvrir_passage(modules, pid, p):
    """Ouvre un passage existant (reprise d'un questionnaire en cours)."""
    rep = db.charger_reponses(pid, p)
    st.session_state.update(passage=p, reponses=rep, etape=premiere_etape(modules, rep),
                            parcours=list(range(len(modules))), source=None, copie_ids=[])
    st.rerun()


def demarrer_repassage(modules, ids_a_refaire):
    """Nouveau passage : les parties choisies sont vierges, les autres sont recopiées du passage affiché."""
    pid, source = st.session_state["pid"], st.session_state["passage"]
    ancien = db.charger_reponses(pid, source)
    copie_ids = [m["id"] for m in modules if m["id"] not in ids_a_refaire]
    reponses = {q["id"]: ancien[q["id"]] for m in modules if m["id"] in copie_ids
                for q in m["questions"] if q["id"] in ancien}
    parcours = [i for i, m in enumerate(modules) if m["id"] in ids_a_refaire]
    nouveau = max(db.liste_passages(pid) or [0]) + 1
    st.session_state.update(passage=nouveau, reponses=reponses, etape=parcours[0],
                            parcours=parcours, source=source, copie_ids=copie_ids)
    st.rerun()


def date_fr(iso):
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "?"


def afficher_page_rapport(modules, pid):
    passages = db.liste_passages(pid)
    complets = [p for p in passages if passage_complet(modules, pid, p)]
    choisi = st.session_state["passage"] if st.session_state["passage"] in complets else complets[-1]
    if len(complets) > 1:
        choisi = st.selectbox("📅 Synthèse affichée", complets, index=complets.index(choisi), key="synthese_choisie",
                              format_func=lambda p: f"Passage n°{p} du {date_fr(db.date_passage(pid, p))}")
    report.afficher_rapport(modules, db.charger_reponses(pid, choisi), age=st.session_state.get("age"))

    st.divider()
    en_cours = [p for p in passages if p not in complets and p > complets[-1]]
    if en_cours:
        st.info("Vous avez commencé à repasser le questionnaire sans le terminer.")
        if st.button("▶ Reprendre mon questionnaire en cours"):
            ouvrir_passage(modules, pid, en_cours[-1])
    if config.AUTORISER_REPASSAGE:
        with st.expander("🔁 Repasser le questionnaire"):
            st.write("Vous pouvez repasser **tout le questionnaire** ou **seulement certaines parties**. "
                     "Vos réponses précédentes sont **conservées** : cela crée un nouveau passage, "
                     "avec une nouvelle synthèse.")
            titres = {m["id"]: m["titre"] for m in modules if not m.get("unique")}
            mode = st.radio("Que souhaitez-vous repasser ?", ["Tout le questionnaire", "Seulement certaines parties"],
                            key="choix_refaire")
            if mode == "Tout le questionnaire":
                selection = list(titres)
            else:
                selection = st.multiselect("Parties à repasser", list(titres), key="sel_refaire",
                                           format_func=lambda i: titres[i])
            if st.button("Commencer", disabled=not selection, type="primary"):
                demarrer_repassage(modules, selection)


def aller(page):
    """Navigation entre l'accueil, l'accès patient et l'accès médecin (lien direct : ?acces=patient)."""
    st.session_state["page"] = page
    if page == "accueil":
        st.query_params.clear()
    else:
        st.query_params["acces"] = page
    st.rerun()


# ---------- 1) Accueil / Connexion ----------
accueil.appliquer_style()
if "pid" not in st.session_state:
    if "page" not in st.session_state:
        demande = st.query_params.get("acces", "accueil")
        st.session_state["page"] = demande if demande in ("patient", "medecin") else "accueil"
    if st.session_state["page"] == "accueil":
        accueil.afficher(aller)
        st.stop()
    if st.session_state["page"] == "medecin":
        admin.afficher(aller)
        st.stop()

    _, centre, _ = st.columns([1, 2, 1])
    with centre:
        st.markdown(accueil.entete_connexion(
            "Accès patient", "Connectez-vous avec votre numéro de randomisation et votre date de naissance."),
            unsafe_allow_html=True)
        with st.form("login"):
            numero = st.text_input("Numéro de randomisation")
            naissance = st.date_input("Date de naissance", value=date(1980, 1, 1),
                                      min_value=date(1900, 1, 1), max_value=date.today(),
                                      format="DD/MM/YYYY")
            ok = st.form_submit_button("Se connecter")
        if ok:
            numero = db.normaliser_numero(numero)
            statut = db.verifier_participant(numero, naissance)
            if statut == "ok":
                modules = charger_modules()
                passages = db.liste_passages(numero)
                complets = [p for p in passages if passage_complet(modules, numero, p)]
                # Questionnaire terminé -> synthèse du dernier passage complet ; sinon reprise là où on s'était arrêté
                p = complets[-1] if complets else (passages[-1] if passages else 1)
                rep = db.charger_reponses(numero, p)
                auj = date.today()
                age = auj.year - naissance.year - ((auj.month, auj.day) < (naissance.month, naissance.day))
                st.session_state.update(pid=numero, age=age, passage=p, reponses=rep,
                                        etape=premiere_etape(modules, rep), parcours=list(range(len(modules))),
                                        source=None, copie_ids=[])
                st.rerun()
            elif statut == "bloque":
                st.error("Compte bloqué après trop d'essais. Contactez l'équipe de l'étude.")
            else:
                st.error("Identifiants incorrects.")
        if st.button("← Retour à l’accueil", key="retour_login"):
            aller("accueil")
    st.stop()

# ---------- 2) Questionnaire ----------
modules = charger_modules()
pid = st.session_state["pid"]
reponses = st.session_state["reponses"]
etape = st.session_state["etape"]
passage = st.session_state["passage"]
parcours = st.session_state["parcours"]

with st.sidebar:
    st.write(f"Connecté : **{pid}**")
    if passage > 1:
        st.caption(f"Passage n°{passage}")
    st.caption(f"Streamlit {st.__version__}")
    if st.button("Se déconnecter"):
        st.session_state.clear()
        st.query_params.clear()
        st.rerun()

if etape >= len(modules):
    afficher_page_rapport(modules, pid)
    st.stop()

m = modules[etape]
pos = parcours.index(etape) if etape in parcours else 0
numerotes = [i for i in parcours if not modules[i].get("unique")]
if etape in numerotes:
    k = numerotes.index(etape)
    st.progress(k / len(numerotes), text=f"Étape {k + 1} sur {len(numerotes)}")
st.header(m["titre"])
st.write(m.get("introduction", ""))

saisies = {}
for q in m["questions"]:
    if est_visible(q, saisies):
        saisies[q["id"]] = afficher_question(q, reponses.get(q["id"]))
    else:
        saisies[q["id"]] = None  # question masquée par une condition
precedents = [i for i in parcours[:pos] if not modules[i].get("unique")]
est_dernier = pos == len(parcours) - 1
col1, col2 = st.columns(2)
precedent = col1.button("← Précédent", disabled=not precedents, key=f"prec_{m['id']}")
suivant = col2.button("Terminer ✔" if est_dernier else "Suivant →", key=f"suiv_{m['id']}", type="primary")

if precedent:
    st.session_state["etape"] = precedents[-1]
    st.rerun()

if suivant:
    manquantes = [q["texte"] for q in m["questions"]
                  if est_visible(q, saisies) and est_manquante(q, saisies[q["id"]])]
    conflits = [q["texte"] for q in m["questions"] if q["type"] == "choix_multiple" and q.get("exclusives") and est_visible(q, saisies)
                and len(saisies[q["id"]] or []) > 1 and any(x in q["exclusives"] for x in saisies[q["id"]])]
    if conflits and not manquantes:
        st.error("Certaines réponses ne peuvent pas être combinées : « " + " » ou « ".join(next(q["exclusives"] for q in m["questions"] if q.get("exclusives")))
                 + " » doit être choisi seul (sans autre réponse).")
    elif manquantes:
        st.toast("⚠️ Certains éléments obligatoires ne sont pas complétés", icon="⚠️")
        st.error("Merci de compléter les éléments obligatoires suivants :\n\n- " + "\n- ".join(manquantes))
    else:
        a_sauver = {q["id"]: saisies[q["id"]] for q in m["questions"]
                    if q["type"] not in ("section", "info")}
        a_sauver["_age"] = st.session_state.get("age")  # âge au moment de la saisie (calculs de cotation)
        reponses.update(a_sauver)
        db.sauver_reponses(pid, m["id"], a_sauver, passage)
        if st.session_state.get("source"):  # nouveau passage : on recopie les parties non repassées
            db.copier_modules(pid, st.session_state["source"], passage, st.session_state["copie_ids"])
        st.session_state["etape"] = len(modules) if est_dernier else parcours[pos + 1]
        st.rerun()
