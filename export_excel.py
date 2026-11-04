"""
export_excel.py : export Excel complet des données, depuis l'espace médecin.
Nom du fichier : JJ_MM_AAAA_HH_MM_SS_Export_listing_patient_CMRR_CHUGA.xlsx
Feuilles : Listing patients · Scores et complétion · Réponses par passage · Réponses format long ·
           Dictionnaire variables · Informations.
⚠️ Le fichier contient des données NOMINATIVES et de santé.
"""
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

import cotations
import db
import logique
import suivi

NOM_BASE = "Export_listing_patient_CMRR_CHUGA"
MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
TYPES = {"nombre": "Nombre", "texte_court": "Texte court", "texte_libre": "Texte libre", "oui_non": "Oui / Non",
         "choix_unique": "Choix unique", "choix_multiple": "Choix multiple", "case_a_cocher": "Case à cocher"}
ETATS = {"complet": "Complet", "partiel": "Partiel", "vide": "Non démarré"}
STATUTS = {"termine": "Terminé", "en_cours": "En cours", "non_demarre": "Non démarré"}
FOND_STATUT = {"Terminé": "D1FAE5", "Complet": "D1FAE5", "En cours": "FEF3C7", "Partiel": "FEF3C7", "Non démarré": "E5E7EB"}
BLEU = "0B5CAD"
COULEURS_PARTIES = ["1D4ED8", "0F766E", "7C3AED", "B45309", "BE185D", "0369A1"]
DATE, DATE_HEURE = "dd/mm/yyyy", "dd/mm/yyyy hh:mm"


def nom_fichier(t=None):
    """Ex. 22_10_2026_14_35_07_Export_listing_patient_CMRR_CHUGA.xlsx"""
    return f"{(t or datetime.now()):%d_%m_%Y_%H_%M_%S}_{NOM_BASE}.xlsx"


def _dt(iso):
    try:
        return datetime.fromisoformat(iso) if iso else None
    except ValueError:
        return None


def _age(naissance_iso, ref):
    d = _dt(naissance_iso)
    return None if d is None else ref.year - d.year - ((ref.month, ref.day) < (d.month, d.day))


def _val(v):
    """Valeur d'une réponse telle qu'écrite dans Excel (cellule vide si pas de réponse)."""
    if v is None or v == "" or v == []:
        return None
    if isinstance(v, bool):
        return "Oui" if v else "Non"
    if isinstance(v, list):
        return " ; ".join(map(str, v))
    if isinstance(v, float) and v.is_integer():
        return int(v)
    return v


def _ecrire(wb, nom, couleur_onglet, entetes, lignes, largeurs, figer, formats=None, fonds=None, statuts=(), hauteur=80):
    ws = wb.create_sheet(nom)
    ws.sheet_properties.tabColor = couleur_onglet
    for j, h in enumerate(entetes, 1):
        c = ws.cell(row=1, column=j, value=h)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=(fonds[j - 1] if fonds else BLEU))
        c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.row_dimensions[1].height = hauteur
    formats = formats or {}
    for i, ligne in enumerate(lignes, 2):
        for j, v in enumerate(ligne, 1):
            c = ws.cell(row=i, column=j, value=v)
            if isinstance(v, str) and v.startswith("="):
                c.data_type = "s"  # une réponse « =1+1 » reste du texte (jamais une formule)
            if j in formats:
                c.number_format = formats[j]
            if j in statuts and v in FOND_STATUT:
                c.fill = PatternFill("solid", fgColor=FOND_STATUT[v])
            c.alignment = Alignment(vertical="top", wrap_text=isinstance(v, str) and len(v) > 35)
    for j in range(1, len(entetes) + 1):
        ws.column_dimensions[get_column_letter(j)].width = largeurs[j - 1] if j - 1 < len(largeurs) else 22
    ws.freeze_panes = figer
    ws.auto_filter.ref = f"A1:{get_column_letter(len(entetes))}{max(len(lignes), 1) + 1}"
    return ws


def _condition(q):
    c = q.get("si")
    if not c:
        return "Toujours affichée"
    if "egal" in c:
        v = c["egal"] if isinstance(c["egal"], list) else [c["egal"]]
        return f"Affichée si « {c['question']} » = " + " ou ".join(str(x) for x in v)
    if "sup" in c:
        return f"Affichée si « {c['question']} » > {c['sup']}"
    return f"Affichée si « {c['question']} » est renseignée"


def construire(modules, maintenant=None):
    """Retourne le fichier Excel (octets)."""
    maintenant = maintenant or datetime.now()
    patients, reponses = db.lister_patients(), db.toutes_reponses()
    details, tentatives = db.dates_detaillees(), db.tentatives_connexion()
    dates = {n: {p: max(d2 for _, d2 in mods.values()) for p, mods in ps.items()} for n, ps in details.items()}
    an = suivi.analyser(modules, patients, reponses, dates)
    suivis = an["suivis"]
    consent_ids = [m["id"] for m in modules if m.get("unique")]
    consent_mods = [m for m in modules if m.get("unique")]
    groupe = {l["numero"]: l["groupe"] for l in an["lignes"]}
    suivis_pat = db.lister_suivi()
    nb_suivi = {n: sum(1 for x in suivis_pat if x["numero"] == n) for n in groupe}
    nb_ei = {n: sum(1 for x in suivis_pat if x["numero"] == n and x["categorie"] == "Effet indésirable") for n in groupe}
    wb = Workbook()
    wb.remove(wb.active)

    # ------------------------------------------------ 1) Listing patients
    en = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Nom", "Prénom", "Date de naissance",
          "Âge à la date de l'export (ans)", "Date d'inclusion", "Mode d'inclusion", "Consentement donné",
          "Date du consentement", "Statut du questionnaire (dernier passage)", "Parties complétées (nombre)",
          "Parties à compléter (nombre total)", "Parties complétées (%)", "Nombre de passages",
          "Date de début du 1er passage", "Date de dernière saisie", "Échecs de connexion (compteur actuel)",
          "Compte bloqué (après 5 échecs)", "Suivi : nombre d'entrées", "Effets indésirables déclarés (nombre)"]
    fonds = [BLEU] * len(en)
    for k, m in enumerate(suivis):
        col = COULEURS_PARTIES[k % len(COULEURS_PARTIES)]
        blocs = [f"{m['titre']} – Statut (dernier passage)", f"{m['titre']} – Complétion (%)",
                 f"{m['titre']} – Historique des passages"]
        if m.get("scoring"):
            blocs += [f"{m['titre']} – Score obtenu", f"{m['titre']} – Score maximum", f"{m['titre']} – Interprétation du score"]
        en += blocs
        fonds += [col] * len(blocs)
    lignes = []
    for l in an["lignes"]:
        num, pp = l["numero"], details.get(l["numero"], {})
        d_consent = min((d1 for ps in pp.values() for mid, (d1, _) in ps.items() if mid in consent_ids), default=None)
        premier = l["passages"][0] if l["passages"] else None
        d_debut = min((d1 for d1, _ in pp[premier].values()), default=None) if premier else None
        complets = sum(1 for s in l["dernier"].values() if s["etat"] == "complet")
        ech = tentatives.get(num, 0)
        ligne = [num, l["groupe"], l["nom"] or None, l["prenom"] or None, _dt(l["naissance"]), _age(l["naissance"], maintenant),
                 _dt(l["inclusion"]), {"formulaire": "Espace médecin", "excel": "Import Excel"}.get(l["source"], l["source"] or None),
                 "Oui" if l["consent"] else "Non", _dt(d_consent), STATUTS[l["statut"]], complets, len(suivis),
                 round(l["pct_complets"], 1), len(l["passages"]), _dt(d_debut), _dt(l["derniere_activite"]), ech,
                 "Oui" if ech >= db.MAX_TENTATIVES else "Non", nb_suivi.get(num, 0), nb_ei.get(num, 0)]
        for m in suivis:
            s, h = l["dernier"][m["id"]], l["hist"][m["id"]]
            ligne += [ETATS[s["etat"]], s["pct"],
                      " | ".join(f"{suivi.ordinal(n)} passage : {x['texte']}" + (f" ({x['resume']})" if x.get("resume") else "") for n, x in h) if h else "Aucun passage"]
            if m.get("scoring"):
                sc = s["score"]
                ligne += [sc["score"] if sc else None, sc["max"] if sc else None, sc["message"] if sc else None]
        lignes.append(ligne)
    formats = {5: DATE, 7: DATE, 10: DATE_HEURE, 16: DATE_HEURE, 17: DATE_HEURE}
    pos, statuts = 22, {11}
    for m in suivis:
        statuts.add(pos)
        pos += 6 if m.get("scoring") else 3
    _ecrire(wb, "Listing patients", "0B5CAD", en, lignes, [16, 14, 18, 18, 14, 14, 14, 16, 13, 17, 20, 13, 13, 13, 11, 17, 17, 14, 14, 13, 16] + [26, 22, 44, 14, 14, 42] * len(suivis),
            "C2", formats, fonds, statuts, hauteur=115)

    # ------------------------------------------------ 2) Scores et complétion (1 ligne = patient x passage x partie)
    en2 = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Passage n°", "Partie", "Date de dernière saisie de la partie",
           "Statut de la partie", "Complétion (%)", "Valeur affichée dans le tableau de bord", "Score obtenu", "Score maximum",
           "Interprétation du score"]
    l2 = []
    for p in patients:
        num = p["numero"]
        for n in sorted(reponses.get(num, {})):
            for m in suivis:
                s = suivi.statut_module(m, reponses[num][n])
                d2 = (details.get(num, {}).get(n, {}).get(m["id"]) or (None, None))[1]
                sc = s["score"]
                l2.append([num, groupe[num], n, m["titre"], _dt(d2), ETATS[s["etat"]], s["pct"], s["texte"],
                           sc["score"] if sc else None, sc["max"] if sc else None, sc["message"] if sc else None])
    _ecrire(wb, "Scores et complétion", "10B981", en2, l2, [16, 14, 10, 42, 18, 15, 13, 18, 12, 12, 50], "E2",
            {5: DATE_HEURE}, statuts={6}, hauteur=48)

    # ------------------------------------------------ 2 bis) Scores calculés (cotations du questionnaire)
    mods_cot = [m for m in suivis if cotations.disponible(m["id"])]
    if mods_cot:
        en_c = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Passage n°", "Âge au moment de la saisie (ans)"]
        fonds_c = [BLEU] * 4
        for k, m in enumerate(mods_cot):
            court = m["titre"].split("–")[0].strip()
            for cle, lib in cotations.variables(m["id"]):
                en_c.append(f"[{court}] {lib}")
                fonds_c.append(COULEURS_PARTIES[k % len(COULEURS_PARTIES)])
        lc = []
        for p in patients:
            num = p["numero"]
            for n in sorted(reponses.get(num, {})):
                rep = reponses[num][n]
                ligne = [num, groupe[num], n, rep.get("_age")]
                for m in mods_cot:
                    vals = cotations.calculer(m, rep, rep.get("_age"))
                    ligne += [vals.get(cle) for cle, _ in cotations.variables(m["id"])]
                lc.append(ligne)
        _ecrire(wb, "Scores calculés", "0EA5E9", en_c, lc, [16, 14, 10, 14] + [20] * (len(en_c) - 4), "E2", fonds=fonds_c, hauteur=95)

    # ------------------------------------------------ 3) Réponses par passage (large)
    en3 = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Passage n°", "Statut du passage",
           "Date de début du passage", "Date de dernière saisie du passage"]
    fonds3 = [BLEU] * len(en3)
    colonnes = []
    for k, m in enumerate(modules):
        col = COULEURS_PARTIES[k % len(COULEURS_PARTIES)]
        court = m["titre"].split("–")[0].strip()
        en3.append(f"[{court}] Statut de la partie")
        fonds3.append(col)
        colonnes.append((m, None))
        for q in m["questions"]:
            if q["type"] in ("section", "info"):
                continue
            texte = q["texte"] if len(q["texte"]) <= 140 else q["texte"][:137] + "…"
            en3.append(f"[{court}] {q['id']} — {texte}")
            fonds3.append(col)
            colonnes.append((m, q))
    l3 = []
    for p in patients:
        num = p["numero"]
        for n in sorted(reponses.get(num, {})):
            rep = reponses[num][n]
            dm = details.get(num, {}).get(n, {})
            bornes = list(dm.values())
            ok = all(suivi.statut_module(m, rep)["etat"] == "complet" for m in suivis + consent_mods)
            ligne = [num, groupe[num], n, "Terminé" if ok else "En cours", _dt(min((b[0] for b in bornes), default=None)),
                     _dt(max((b[1] for b in bornes), default=None))]
            for m, q in colonnes:
                ligne.append(ETATS[suivi.statut_module(m, rep)["etat"]] if q is None
                             else (_val(rep.get(q["id"])) if logique.est_visible(q, rep) else None))
            l3.append(ligne)
    _ecrire(wb, "Réponses par passage", "7C3AED", en3, l3, [16, 14, 10, 14, 17, 17] + [26] * (len(en3) - 6), "G2",
            {5: DATE_HEURE, 6: DATE_HEURE}, fonds3, statuts={4} | {i + 1 for i, h in enumerate(en3) if h.endswith("Statut de la partie")},
            hauteur=135)

    # ------------------------------------------------ 4) Réponses format long
    en4 = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Passage n°", "Partie", "Date de saisie de la partie",
           "Identifiant de la question", "Libellé de la question", "Type de question", "Réponse", "Réponse (valeur numérique)"]
    l4 = []
    for p in patients:
        num = p["numero"]
        for n in sorted(reponses.get(num, {})):
            rep = reponses[num][n]
            for m in modules:
                d2 = (details.get(num, {}).get(n, {}).get(m["id"]) or (None, None))[1]
                for q in m["questions"]:
                    if q["type"] in ("section", "info") or not logique.est_visible(q, rep):
                        continue
                    v = _val(rep.get(q["id"]))
                    if v is None:
                        continue
                    l4.append([num, groupe[num], n, m["titre"], _dt(d2), q["id"], q["texte"], TYPES.get(q["type"], q["type"]), v,
                               v if isinstance(v, (int, float)) and not isinstance(v, bool) else None])
    _ecrire(wb, "Réponses format long", "F59E0B", en4, l4, [16, 14, 10, 38, 18, 26, 60, 15, 40, 14], "G2", {5: DATE_HEURE}, hauteur=45)

    # ------------------------------------------------ 4 bis) Suivi et événements
    en6 = ["N° de randomisation", "Groupe (TEST / CONTROL)", "Type d'information", "Options cochées", "Gravité (effets indésirables)",
           "Évolution (effets indésirables)", "Effet indésirable grave", "Date de l'événement", "Commentaire libre",
           "Saisi le", "Saisi par"]
    l6 = [[x["numero"], groupe.get(x["numero"]), x["categorie"], " ; ".join(x["options"]) or None, x["gravite"] or None,
           x["evolution"] or None, ("Oui" if x["grave"] else "Non") if x["categorie"] == "Effet indésirable" else None,
           _dt(x["date_evenement"]), x["commentaire"] or None, _dt(x["cree_le"]), x["cree_par"]] for x in suivis_pat]
    _ecrire(wb, "Suivi et événements", "DC2626", en6, l6, [16, 14, 30, 50, 16, 18, 14, 14, 60, 17, 16], "C2", {8: DATE, 10: DATE_HEURE}, hauteur=48)

    # ------------------------------------------------ 4 ter) Journal d'audit
    def _txt(det):
        if not det:
            return None
        if det.get("efface"):
            return "(contenu effacé)"
        if "motif" in det:
            return f"Motif : {det['motif']}" + (f" — {det['precision']}" if det.get("precision") else "")
        if all(isinstance(v, dict) and "avant" in v for v in det.values()):
            return " ; ".join(f"{k} : {v['avant'] or '—'} → {v['apres'] or '—'}" for k, v in det.items())
        return " ; ".join(f"{k} : {v}" for k, v in det.items())
    en7 = ["Date et heure", "Utilisateur", "Action", "N° de randomisation", "Détails"]
    l7 = [[_dt(j["date_heure"]), j["utilisateur"], j["action"], j["numero"], _txt(j["details"])] for j in db.lire_journal()]
    _ecrire(wb, "Journal d'audit", "475569", en7, l7, [18, 16, 38, 18, 90], "A2", {1: DATE_HEURE}, hauteur=40)

    # ------------------------------------------------ 5) Dictionnaire des variables
    en5 = ["Partie", "N° dans la partie", "Identifiant de la question", "Libellé de la question", "Type de question",
           "Options de réponse", "Points associés aux options (score)", "Obligatoire", "Condition d'affichage"]
    l5 = []
    for m in modules:
        k = 0
        for q in m["questions"]:
            if q["type"] in ("section", "info"):
                continue
            k += 1
            l5.append([m["titre"], k, q["id"], q["texte"], TYPES.get(q["type"], q["type"]),
                       " | ".join(map(str, q.get("options", []))) or ("Oui | Non" if q["type"] == "oui_non" else None),
                       " | ".join(map(str, q["scores"])) if q.get("scores") else None,
                       "Oui" if q.get("obligatoire", True) else "Non", _condition(q)])
    _ecrire(wb, "Dictionnaire variables", "64748B", en5, l5, [38, 10, 28, 70, 15, 60, 20, 11, 45], "D2", hauteur=40)

    # ------------------------------------------------ 6) Informations
    n_pass = sum(len(v) for v in reponses.values())
    infos = [
        ("Fichier", nom_fichier(maintenant)),
        ("Généré le", f"{maintenant:%d/%m/%Y à %H:%M:%S}"),
        ("Patients inclus", len(patients)),
        ("Passages enregistrés (tous patients)", n_pass),
        ("Parties suivies", len(suivis)),
        ("⚠️ Confidentialité", "Ce fichier contient des données NOMINATIVES (nom, prénom, date de naissance) et des données de santé. "
                              "À conserver uniquement sur un poste ou serveur sécurisé, sans transmission par e-mail non chiffré."),
        ("Feuille « Listing patients »", "1 ligne par patient : identité, groupe, consentement, avancement et état de chaque partie (dernier passage + historique)."),
        ("Feuille « Scores calculés »", "Variables dérivées du questionnaire (IPAQ, PSQI C1-C7, MEDAS, paquets-années, alcool…), 1 ligne par patient et par passage ; cellule vide = non calculable."),
        ("Feuille « Scores et complétion »", "1 ligne par patient, par passage et par partie : statut, complétion (%) et score éventuel."),
        ("Feuille « Réponses par passage »", "1 ligne par patient et par passage ; 1 colonne par question (en-tête : [Partie] identifiant — libellé)."),
        ("Feuille « Réponses format long »", "1 ligne par réponse (patient × passage × question) : pratique pour R, Python, SPSS, tableaux croisés."),
        ("Feuille « Suivi et événements »", "Effets indésirables, remarques liées à l'essai, plaintes, conditions de complétion et autres informations saisies par les médecins."),
        ("Feuille « Journal d'audit »", "Traçabilité : créations, modifications, ajouts de suivi, déblocages, exports et suppressions (date, utilisateur, action). Un patient supprimé n'y laisse que son numéro, la date et le motif."),
        ("Patients supprimés", "Ils n'apparaissent dans aucune autre feuille ; leurs numéros ne sont jamais réattribués."),
        ("Feuille « Dictionnaire variables »", "Liste de toutes les questions : identifiant, libellé, type, options, score, caractère obligatoire, condition d'affichage."),
        ("Définition : partie complète", "Toutes les questions obligatoires visibles sont renseignées. Une partie partiellement remplie n'est PAS complète."),
        ("Définition : complétion (%)", "Pour une partie incomplète : questions obligatoires renseignées / questions obligatoires à renseigner ; 0 % si non démarrée."),
        ("Définition : score", "Calculé uniquement pour les parties qui définissent une règle de score ; sinon une partie complète est notée 100 %."),
        ("Définition : dernier passage", "Statuts, statistiques et valeurs du listing = dernier passage de chaque patient. L'historique complet est dans les autres feuilles."),
        ("Parties non repassées", "Lors d'un nouveau passage partiel, les parties non repassées sont recopiées avec leur date de saisie d'origine."),
        ("Groupe", "Numéro P000 inférieur à 500 : TEST ; 500 et plus : CONTROL."),
        ("Cellules vides", "Question non posée (condition d'affichage non remplie) ou sans réponse. Choix multiples séparés par « ; »."),
        ("Couleurs", "Vert = terminé/complet ; orange = en cours/partiel ; gris = non démarré."),
    ]
    ws = _ecrire(wb, "Informations", "94A3B8", ["Information", "Détail"], [list(x) for x in infos], [38, 130], "A2", hauteur=28)
    for row in ws.iter_rows(min_row=2):
        row[0].font = Font(bold=True)
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
    ws.auto_filter.ref = None

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
