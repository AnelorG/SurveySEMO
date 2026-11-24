"""
cotations.py : calcul des variables dérivées (scores) du questionnaire RC-EA-EH, d'après les consignes « Cotation » et « Cotation et normalisation »
du document de validation (version du 12/11/2026). Ce fichier ne contient aucun affichage.
Les seuils sont regroupés en tête de chaque bloc pour être modifiés facilement.
Utilisation : cotations.calculer("mode_de_vie", reponses, age) -> {cle: valeur}  (None si non calculable)
"""

import re


# ---------------------------------------------------------------- outils
def _n(rep, k):
    v = rep.get(k)
    return None if v is None or v == "" or isinstance(v, bool) else float(v)


def _duree_minutes(rep, prefixe, defaut=None):
    """heures*60 + minutes ; si « Je ne sais pas » est coché -> valeur moyenne par défaut (ou None)."""
    if rep.get(f"{prefixe}_nsp"):
        return defaut
    h, m = _n(rep, f"{prefixe}_heures"), _n(rep, f"{prefixe}_minutes")
    return None if h is None or m is None else h * 60 + m


def _hhmm(v):
    try:
        h, m = str(v).split(":")[:2]
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _points(module, rep, qid):
    """Code d'une réponse à choix unique, lu dans la liste `scores` du fichier YAML du module."""
    q = next((x for x in module["questions"] if x["id"] == qid), None)
    v = rep.get(qid)
    if q is None or v not in q.get("options", []) or "scores" not in q:
        return None
    return q["scores"][q["options"].index(v)]


def _r(x, n=1):
    return None if x is None else round(x + 0.0, n)


# ---------------------------------------------------------------- IPAQ (activité physique)
MET = {"intense": 8.0, "modere": 4.0, "marche": 3.0}            # valeurs retenues pour l'étude (vigorous 8 ; moderate 4 ; walk 3)
DEFAUT_MIN = {"intense": 20, "modere": 20, "marche": 30}      # « Je ne sais pas » : minutes/jour moyennes
IPAQ_QUESTIONS = {"intense": ("mv1_jours_intense", "mv2_intense"), "modere": ("mv3_jours_modere", "mv4_modere"),
                  "marche": ("mv5_jours_marche", "mv6_marche")}


def ipaq(rep):
    jours, mins, mets = {}, {}, {}
    for nom, (qj, pref) in IPAQ_QUESTIONS.items():
        j = _n(rep, qj)
        jours[nom] = j
        if j is None:
            mins[nom] = mets[nom] = None
        elif j == 0:
            mins[nom], mets[nom] = 0.0, 0.0                    # 0 jour : activité = 0 et durée non posée
        else:
            mins[nom] = _duree_minutes(rep, pref, DEFAUT_MIN[nom])
            mets[nom] = None if mins[nom] is None else MET[nom] * j * mins[nom]
    complet = all(v is not None for v in mets.values())
    total = sum(mets.values()) if complet else None          # MET-min/semaine = durée x fréquence x MET, sommé sur les 3 domaines
    niveau = critere = None
    if complet:  # catégories de Craig et al. (2003), protocole IPAQ forme courte
        jt = sum(jours.values())                              # jours « toutes intensités confondues » (somme des 3 réponses)
        min_ok = all(mins[k] >= 30 for k in ("modere", "marche") if jours[k] > 0)
        if jours["intense"] >= 3 and total >= 1500:
            niveau, critere = "Élevé", "A : ≥ 3 jours d’activité intense et ≥ 1 500 MET-min/semaine"
        elif jt >= 7 and total >= 3000:
            niveau, critere = "Élevé", "B : 7 jours d’activité (toutes intensités) et ≥ 3 000 MET-min/semaine"
        elif jours["intense"] >= 3 and mins["intense"] >= 20:
            niveau, critere = "Modéré", "A : ≥ 3 jours avec au moins 20 min d’activité intense"
        elif jours["modere"] + jours["marche"] >= 5 and min_ok:
            niveau, critere = "Modéré", "B : ≥ 5 jours avec au moins 30 min d’activité modérée ou de marche"
        elif jt >= 5 and total >= 600:
            niveau, critere = "Modéré", "C : ≥ 5 jours (toutes intensités) et ≥ 600 MET-min/semaine"
        else:
            niveau, critere = "Faible", "Ne remplit pas les critères des catégories modérée ou élevée"
    # recommandation CDC-ACSM : ≥ 150 min/semaine d'activité d'intensité au moins modérée, l'activité intense comptant DOUBLE (méthode d'Armstrong)
    tot_min = {k: (None if mins[k] is None or jours[k] is None else jours[k] * mins[k]) for k in mins}
    minutes = None if None in tot_min.values() else sum(tot_min.values())
    equiv = None if minutes is None else tot_min["modere"] + tot_min["marche"] + 2 * tot_min["intense"]
    assis = None if rep.get("mv7_assis_nsp") else _duree_minutes(rep, "mv7_assis")
    return {"ipaq_intense": _r(mets["intense"]), "ipaq_modere": _r(mets["modere"]), "ipaq_marche": _r(mets["marche"]),
            "ipaq_total": _r(total), "ipaq_niveau": niveau, "ipaq_critere": critere, "ipaq_minutes_semaine": _r(minutes),
            "ipaq_minutes_equivalent_modere": _r(equiv), "ipaq_recommandation_150": None if equiv is None else int(equiv >= 150),
            "ipaq_pct_repere_150": None if equiv is None else _r(equiv / 150 * 100, 0),
            "assis_min_jour": assis}


# ---------------------------------------------------------------- PSQI (sommeil)
def _c4(eff):
    return None if eff is None else 0 if eff > 85 else 1 if eff >= 75 else 2 if eff >= 65 else 3


def _recode_sum(s, bornes):
    """Recodage d'une somme : bornes = [(max, code), ...]."""
    return None if s is None else next(code for mx, code in bornes if s <= mx)


def psqi(module, rep):
    c1 = _points(module, rep, "mv13_qualite")
    latence = _n(rep, "mv9_latence")
    code_lat = None if latence is None else 0 if latence <= 15 else 1 if latence <= 30 else 2 if latence <= 60 else 3
    a = _points(module, rep, "mv12a")
    c2 = _recode_sum(None if code_lat is None or a is None else code_lat + a, [(0, 0), (2, 1), (4, 2), (6, 3)])
    h = _n(rep, "mv11_sommeil_h")
    c3 = None if h is None else 0 if h >= 7 else 1 if h >= 6 else 2 if h >= 5 else 3
    coucher, lever = _hhmm(rep.get("mv8_coucher")), _hhmm(rep.get("mv10_lever"))
    au_lit = None if coucher is None or lever is None else ((lever - coucher) % 1440) / 60 or None
    eff = None if au_lit is None or h is None else h / au_lit * 100
    c4 = _c4(eff)
    perturb = [_points(module, rep, f"mv12{x}") for x in "bcdefghi"]
    if rep.get("mv12j_description"):
        perturb.append(_points(module, rep, "mv12j_frequence"))
    c5 = _recode_sum(None if None in perturb else sum(perturb), [(0, 0), (9, 1), (18, 2), (27, 3)])
    c6 = _points(module, rep, "mv14_medicaments")
    s7 = (_points(module, rep, "mv15_somnolence"), _points(module, rep, "mv16_enthousiasme"))
    c7 = _recode_sum(None if None in s7 else sum(s7), [(0, 0), (2, 1), (4, 2), (6, 3)])
    cs = [c1, c2, c3, c4, c5, c6, c7]
    return {"psqi_temps_au_lit_h": _r(au_lit, 2), "psqi_efficacite_pct": _r(eff, 1),
            **{f"psqi_c{i + 1}": c for i, c in enumerate(cs)}, "psqi_total": None if None in cs else sum(cs),
            "psqi_pct": None if None in cs else _r(sum(cs) / 21 * 100, 0)}


# ---------------------------------------------------------------- MEDAS (alimentation) : 14 items, 1 point si le critère est atteint
# (clé, opérateur, seuil). Seuils de la VERSION ORIGINALE du MEDAS (Schröder et al., 2011), tels que dans le document de validation du 12/11/2026.
#  - MV22 : viande rouge < 1 portion par JOUR ; la question est posée par SEMAINE -> critère atteint si < 7 portions/semaine.
#  - MV23 (beurre, crème) < 1/jour ; MV24 (boissons sucrées) < 1/jour ; MV28 (pâtisseries) < 3/semaine : inégalités STRICTES.
#  - MV20 : l'original demande aussi au moins 1 portion de légumes crus ; la question n'étant pas posée séparément, seul le seuil ≥ 2 portions est appliqué.
MEDAS = [("mv18_huile_principale", "oui", None), ("mv19_huile_cuilleres", ">=", 4), ("mv20_legumes", ">=", 2),
         ("mv21_fruits", ">=", 3), ("mv22_viande_rouge", "<", 7), ("mv23_beurre", "<", 1),
         ("mv24_boissons_sucrees", "<", 1), ("mv25_vin", ">=", 7), ("mv26_legumineuses", ">=", 3),
         ("mv27_poisson", ">=", 3), ("mv28_patisseries", "<", 3), ("mv29_fruits_coque", ">=", 3),
         ("mv30_volaille", "oui", None), ("mv31_sofrito", ">=", 2)]
MEDAS_NOMS = ["Huile d’olive principale", "Huile d’olive ≥ 4 c./jour", "Légumes ≥ 2/jour", "Fruits ≥ 3/jour", "Viande rouge < 1/jour",
              "Beurre/crème < 1/jour", "Boissons sucrées < 1/jour", "Vin ≥ 7/semaine", "Légumineuses ≥ 3/sem.", "Poisson ≥ 3/sem.",
              "Pâtisseries < 3/sem.", "Fruits à coque ≥ 3/sem.", "Volaille > viande rouge", "Sauce « sofrito » ≥ 2/sem."]


def medas(rep):
    pts = {}
    for cle, op, seuil in MEDAS:
        if op == "oui":
            v = rep.get(cle)
            pts[cle] = None if v not in ("Oui", "Non") else int(v == "Oui")
        else:
            v = _n(rep, cle)
            pts[cle] = None if v is None else int(v >= seuil if op == ">=" else v < seuil)
    pts["medas_total"] = None if None in pts.values() else sum(pts.values())
    pts["medas_pct"] = None if pts["medas_total"] is None else _r(pts["medas_total"] / 14 * 100, 0)
    return pts


# ---------------------------------------------------------------- tabac et alcool
def tabac_alcool(rep, age):
    v = rep.get("mv32_tabac")
    statut = {"Non": 0, "Oui, mais j’ai arrêté": 1, "Oui, je fume actuellement": 2}.get(v)
    debut, arret, cig = _n(rep, "mv32_debut"), _n(rep, "mv32_arret"), _n(rep, "mv32_cigarettes")
    age = _n(rep, "_age") if _n(rep, "_age") is not None else age
    duree = None
    if statut == 1 and debut is not None and arret is not None:
        duree = max(arret - debut, 0)
    elif statut == 2 and debut is not None and age is not None:
        duree = max(age - debut, 0)
    pa = 0.0 if statut == 0 else (None if duree is None or cig is None else cig / 20 * duree)
    jours, verres = _n(rep, "mv33_jours_alcool"), _n(rep, "mv34_verres")
    hebdo = 0.0 if jours == 0 else (None if jours is None or verres is None else jours * verres)
    return {"tabac_statut": statut, "tabac_duree_ans": duree, "tabac_paquets_annees": _r(pa),
            "alcool_jours_semaine": jours, "alcool_verres_par_jour": verres, "alcool_verres_semaine": _r(hebdo),
            # repères Santé publique France : au plus 10 verres standards/semaine, au plus 2 par jour, avec des jours sans alcool
            "alcool_repere_semaine": None if hebdo is None else int(hebdo <= 10),
            "alcool_repere_jour": 1 if jours == 0 else (None if verres is None else int(verres <= 2)),
            "alcool_jours_sans": None if jours is None else _r(7 - jours, 0),
            "alcool_repere_jours_sans": None if jours is None else int(jours < 7)}


# ---------------------------------------------------------------- MODULE 2 : réseau social (LSNS-6), HAD-D, antécédents dépressifs
LSNS_FAMILLE = ["psy1_famille_contact", "psy2_famille_confidences", "psy3_famille_aide"]
LSNS_AMIS = ["psy4_amis_contact", "psy5_amis_confidences", "psy6_amis_aide"]
HAD_D = ["psy7_plaisir", "psy8_rire", "psy9_humeur", "psy10_ralenti", "psy11_apparence", "psy12_se_rejouir", "psy13_livre"]
PRISE_EN_CHARGE = {"Non": 0, "Oui, traitement médicamenteux": 1, "Oui, suivi psychologique / psychothérapie": 2, "Oui, les deux": 3, "Autre": 4}


def _somme(codes):
    return None if None in codes else sum(codes)


def exposome_psy(module, rep):
    out = {}
    for cle in LSNS_FAMILLE + LSNS_AMIS + HAD_D:
        out[cle] = _points(module, rep, cle)
    out["lsns_famille"] = _somme([out[c] for c in LSNS_FAMILLE])
    out["lsns_amis"] = _somme([out[c] for c in LSNS_AMIS])
    out["lsns_total"] = _somme([out["lsns_famille"], out["lsns_amis"]])
    out["had_d_total"] = _somme([out[c] for c in HAD_D])
    out["lsns_pct"] = None if out["lsns_total"] is None else _r(out["lsns_total"] / 30 * 100, 0)
    out["had_d_pct"] = None if out["had_d_total"] is None else _r(out["had_d_total"] / 21 * 100, 0)
    dep = {"Non": 0, "Oui": 1}.get(rep.get("psy14_depression"))        # « Je ne sais pas » = manquant
    out["dep_antecedent"] = dep
    oui = dep == 1
    out["dep_age_premier_episode"] = _n(rep, "psy14_age") if oui and not rep.get("psy14_age_nsp") else None
    recidive = {"Non": 0, "Oui": 1}.get(rep.get("psy14_plusieurs")) if oui else None
    out["dep_recidive"] = recidive
    out["dep_nb_episodes"] = _n(rep, "psy14_nb") if recidive == 1 and not rep.get("psy14_nb_nsp") else None
    out["dep_prise_en_charge"] = PRISE_EN_CHARGE.get(rep.get("psy14_prise")) if oui else None
    return out


# ---------------------------------------------------------------- MODULE 3 : expositions (indices exploratoires)
# (clé, nom court, a une fréquence ?)
ENV = {"env1": ("ENV1 – Expositions chimiques et professionnelles", [("env1_solvants", "Solvants, peintures, colles", True), ("env1_pesticides", "Pesticides", True),
                                                            ("env1_fumees", "Fumées, poussières, gaz", True), ("env1_autre", "Autre produit chimique", True)]),
       "env2": ("ENV2 – Environnement extérieur", [("env2_route", "Route à forte circulation", False), ("env2_autoroute", "Autoroute / voie rapide", False),
                                                  ("env2_zone_industrielle", "Zone industrielle", False), ("env2_usine", "Usine / site industriel", False),
                                                  ("env2_autre", "Autre pollution extérieure", False)]),
       "env3": ("ENV3 – Environnement intérieur", [("env3_tabac_passif", "Tabagisme passif", True), ("env3_humidite", "Humidité / moisissures", True),
                                                  ("env3_combustion", "Appareil à combustion", True), ("env3_autre", "Autre exposition intérieure", True)])}


def expositions(module, rep):
    """Pour chaque exposition : présence (Non=0, Oui=1, « Je ne sais pas » = manquant), durée, fréquence (jours/mois) et indice
    exploratoire = durée en mois x jours/mois. Aucune dose globale : les indices sont conservés séparément."""
    out = {}
    for groupe, (_, items) in ENV.items():
        connus = [0, 0]
        for cle, _nom, avec_freq in items:
            p = {"Non": 0, "Oui": 1}.get(rep.get(cle))
            out[f"{cle}_present"] = p
            connus[0] += p or 0
            connus[1] += p is None
            if avec_freq:
                a, mo = _n(rep, f"{cle}_annees"), _n(rep, f"{cle}_mois")
                mois = None if p != 1 or a is None else a * 12 + (mo or 0)
                freq = _points(module, rep, f"{cle}_freq") if p == 1 else None
                out[f"{cle}_duree_mois"], out[f"{cle}_freq_j_mois"] = mois, freq
                out[f"{cle}_indice"] = 0 if p == 0 else (None if p is None or mois is None or freq is None else _r(mois * freq))
            else:
                out[f"{cle}_duree_annees"] = _n(rep, f"{cle}_annees") if p == 1 else None
        out[f"{groupe}_nombre"] = None if connus[1] else connus[0]            # décompte vide si au moins un item est « Je ne sais pas »
        out[f"{groupe}_pct"] = None if connus[1] else _r(connus[0] / len(items) * 100, 0)   # % du maximum du bloc
        out[f"{groupe}_nb_nsp"], out[f"{groupe}_nb_connues"] = connus[1], connus[0]
    return out


def _variables_env():
    v = []
    for groupe, (titre, items) in ENV.items():
        court = titre.split("–")[0].strip()
        for cle, nom, avec_freq in items:
            v.append((f"{cle}_present", f"{court} – {nom} : présence (0 = non ; 1 = oui)"))
            if avec_freq:
                v += [(f"{cle}_duree_mois", f"{court} – {nom} : durée (mois)"), (f"{cle}_freq_j_mois", f"{court} – {nom} : fréquence estimée (jours/mois)"),
                      (f"{cle}_indice", f"{court} – {nom} : indice cumulatif exploratoire (jours-exposition)")]
            else:
                v.append((f"{cle}_duree_annees", f"{court} – {nom} : durée (années)"))
        v += [(f"{groupe}_nombre", f"{court} – nombre d'expositions présentes (vide si une réponse « Je ne sais pas »)"),
              (f"{groupe}_pct", f"{court} – nombre d'expositions en % du maximum du bloc (indice exploratoire)"),
              (f"{groupe}_nb_nsp", f"{court} – nombre de réponses « Je ne sais pas »"),
              (f"{groupe}_nb_connues", f"{court} – expositions présentes parmi les réponses connues")]
    return v


# ---------------------------------------------------------------- MODULE 4 : santé générale et antécédents
DIAG_CM = [("hta", "Hypertension artérielle"), ("diabete", "Diabète"), ("ldl", "Cholestérol LDL élevé"),
           ("dyslipidemie", "Autre dyslipidémie / triglycérides élevés"), ("cardiovasculaire", "Maladie cardiovasculaire")]
_NON_OUI = {"Non": 0, "Oui": 1}


def _age_extrait(texte):
    """Premier nombre (0-110) trouvé dans un texte libre « âge ou période » (ex. « 42 ans » -> 42) ; None sinon."""
    import re
    trouves = re.findall(r"\d+", str(texte or ""))
    return int(trouves[0]) if trouves and int(trouves[0]) <= 110 else None


def sante_generale(module, rep):
    out = {}
    sel = rep.get("sant1_diagnostics") or []
    inconnu = (not sel) or "Je ne sais pas" in sel
    for cle, nom in DIAG_CM:
        out[f"cm_{cle}"] = None if inconnu else int(nom in sel)
        out[f"cm_{cle}_traitement"] = _NON_OUI.get(rep.get(f"sant1_ttt_{cle}")) if out[f"cm_{cle}"] == 1 else None
    out["cm_nombre"] = None if inconnu else sum(out[f"cm_{c}"] for c, _ in DIAG_CM)
    t, p = _n(rep, "sant2_taille_cm"), _n(rep, "sant3_poids_kg")
    out["taille_cm"], out["poids_kg"] = t, p
    out["imc"] = None if t is None or p is None or t == 0 else _r(p / (t / 100) ** 2, 1)
    aud = _NON_OUI.get(rep.get("sant4_audition"))
    out["audition_difficulte"], out["audition_appareil"] = aud, _NON_OUI.get(rep.get("sant4_appareil")) if aud == 1 else None
    out["vision_difficulte"] = _NON_OUI.get(rep.get("sant5_vision"))
    avc = _NON_OUI.get(rep.get("sant6_avc"))
    out["avc"], out["avc_nombre"], out["avc_age_premier"] = avc, _n(rep, "sant6_nb") if avc == 1 else None, _n(rep, "sant6_age") if avc == 1 else None
    tcc = _NON_OUI.get(rep.get("sant7_tcc"))
    out["tcc"] = tcc
    out["tcc_nombre"] = _n(rep, "sant7_nb") if tcc == 1 else None
    out["tcc_perte_connaissance"] = _NON_OUI.get(rep.get("sant7_perte_connaissance")) if tcc == 1 else None
    out["tcc_hospitalisation"] = _NON_OUI.get(rep.get("sant7_hospitalisation")) if tcc == 1 else None
    out["tcc_age_periode_texte"] = rep.get("sant7_age_periode") if tcc == 1 else None
    out["tcc_age_extrait"] = _age_extrait(rep.get("sant7_age_periode")) if tcc == 1 else None
    neuro = _NON_OUI.get(rep.get("sant8_neuro"))
    out["neuro_autre"], out["neuro_autre_texte"] = neuro, rep.get("sant8_precision") if neuro == 1 else None
    v = rep.get("sant9_vih")
    out["vih_diagnostic"] = _NON_OUI.get(v)
    out["vih_type_reponse"] = None if v is None else ("Réponse" if v in _NON_OUI else v)        # manquant distinct : « Je ne sais pas » ≠ refus
    out["vih_traitement_arv"] = _NON_OUI.get(rep.get("sant9_arv")) if out["vih_diagnostic"] == 1 else None
    thm = rep.get("sant10_thm")
    out["thm"] = 0 if thm == "Non" else 1 if thm in ("Oui, actuellement", "Oui, par le passé") else None
    out["thm_statut"] = thm
    out["thm_age_debut"] = _n(rep, "sant10_age_debut") if out["thm"] == 1 else None
    a, mo = _n(rep, "sant10_duree_annees"), _n(rep, "sant10_duree_mois")
    out["thm_duree_mois"] = a * 12 + (mo or 0) if out["thm"] == 1 and a is not None else None
    return out


def _variables_sante():
    v = []
    for cle, nom in DIAG_CM:
        v += [(f"cm_{cle}", f"Cardio-métabolique – {nom} (0 = non ; 1 = oui)"), (f"cm_{cle}_traitement", f"Cardio-métabolique – {nom} : traitement actuel (0 = non ; 1 = oui)")]
    return v + [
        ("cm_nombre", "Cardio-métabolique – nombre de diagnostics (0-5, descriptif ; vide si « Je ne sais pas »)"), ("taille_cm", "Taille (cm)"), ("poids_kg", "Poids (kg)"),
        ("imc", "IMC (kg/m²)"), ("audition_difficulte", "Audition – difficulté importante actuelle (0/1)"), ("audition_appareil", "Audition – appareil auditif actuel (0/1)"),
        ("vision_difficulte", "Vision – difficulté importante actuelle malgré correction (0/1)"), ("avc", "AVC – antécédent (0/1)"),
        ("avc_nombre", "AVC – nombre approximatif"), ("avc_age_premier", "AVC – âge au premier (ans)"), ("tcc", "Traumatisme crânien – antécédent (0/1)"),
        ("tcc_nombre", "Traumatisme crânien – nombre"), ("tcc_perte_connaissance", "Traumatisme crânien – perte de connaissance (0/1)"),
        ("tcc_hospitalisation", "Traumatisme crânien – hospitalisation (0/1)"), ("tcc_age_periode_texte", "Traumatisme crânien – âge ou période (texte libre)"),
        ("tcc_age_extrait", "Traumatisme crânien – âge extrait automatiquement du texte (ans)"), ("neuro_autre", "Autre maladie neurologique (0/1)"),
        ("neuro_autre_texte", "Autre maladie neurologique – précision (texte libre)"), ("vih_diagnostic", "VIH – diagnostic (0/1 ; vide si ne sait pas ou refus)"),
        ("vih_type_reponse", "VIH – type de réponse (Réponse / Je ne sais pas / Je préfère ne pas répondre)"), ("vih_traitement_arv", "VIH – traitement antirétroviral actuel (0/1)"),
        ("thm", "Traitement hormonal de la ménopause (0 = non ; 1 = oui ; vide = ne sait pas / non concernée)"), ("thm_statut", "Traitement hormonal de la ménopause – réponse donnée"),
        ("thm_age_debut", "Traitement hormonal de la ménopause – âge au début (ans)"), ("thm_duree_mois", "Traitement hormonal de la ménopause – durée (mois)")]


# ---------------------------------------------------------------- MODULE 5 : réserve cognitive (QEV / LEQ)
# Structure (Valenzuela & Sachdev, 2007 ; version française C. Berr & D. Villebrun ; harmonisation Ourry et al., 2021) : 3 périodes de vie
# (13-30 ans, 30-65 ans, depuis 65 ans) ; chaque période = sous-score NON SPÉCIFIQUE + sous-score SPÉCIFIQUE ; score total LEQ = somme des 3 périodes.
#
# CALCULÉ ICI (barème publié, sans ambiguïté) :
#  - sous-score NON SPÉCIFIQUE de chaque période : 7 domaines cotés de 0 à 5, soit 35 au maximum.
#      G1, G2, G3, G5, G6 : Jamais 0 · Moins d'une fois par mois 1 · Chaque mois 2 · Tous les 15 jours 3 · Chaque semaine 4 · Chaque jour 5.
#      G4 (activité physique) : valeur MAXIMALE des trois intensités. Si une intensité manque, le maximum n'est déterminable que lorsqu'une
#         autre intensité est déjà cotée à 5.
#      G7 (voyages) : points selon le nombre de zones cochées (table LEQ_POINTS_VOYAGES) ; « Aucun » = 0 ; « Aucun » avec une zone = à clarifier (manquant).
#      G8 (autres loisirs) : descriptif, sans points. Réponse vide = manquante ; domaine non cotable = sous-score manquant.
#  - composante « responsabilité d'encadrement » de la période 30-65 ans : 0 personne 8 · 1-5 personnes 16 · 6-10 personnes 24 · plus de 10 personnes 32
#      (valeur la plus élevée sur les tranches d'âge ; absence d'encadrement = 8). Composante intermédiaire, NON normalisée.
#
# NON CALCULÉ (barème absent des sources publiques ; annexe de Valenzuela & Sachdev 2007 et tableaux supplémentaires S1-S2 d'Ourry et al. 2021 à obtenir) :
#  - sous-scores SPÉCIFIQUES (éducation ; profession inversée + encadrement + formation supplémentaire ; vie sociale et recherche d'information après 65 ans),
#    leur normalisation (même poids que les sous-scores non spécifiques) et donc le SCORE TOTAL LEQ. Ces valeurs restent vides dans l'export.
#    Règle française déjà connue pour l'éducation : 2 ans de secondaire = +0 ; 3 ans = +4 ; 2 dernières années = +8.
LEQ_PERIODES = [("ja", "13 à 30 ans"), ("ad", "30 à 65 ans"), ("se", "depuis 65 ans")]
# Voyages (G7) : nombre de zones cochées (0 à 8) -> points. Règle retenue dans le document de validation : 1 point par zone, plafonné à 5.
# Variante décrite dans la littérature (Chan et al., 2022) : 1-2 zones = 1 ; 3-4 = 2 ; 5 = 3 ; 6-7 = 4 ; toutes = 5
# -> pour l'utiliser, remplacer la table ci-dessous par {0: 0, 1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 4, 7: 4, 8: 5}.
LEQ_POINTS_VOYAGES = {0: 0, 1: 1, 2: 2, 3: 3, 4: 4, 5: 5, 6: 5, 7: 5, 8: 5}
LEQ_ENCADREMENT = {"Aucune personne encadrée / sans objet": 8, "1–5 personnes": 16, "6–10 personnes": 24, "Plus de 10 personnes": 32}
LEQ_DOMAINES = [("g1_famille", "visites"), ("g2_musique", "musique"), ("g3_art", "loisirs artistiques"), ("g4", "activité physique"),
                ("g5_lecture", "lecture"), ("g6_langue", "deuxième langue"), ("g7_voyages", "voyages")]


def _leq_g4(module, rep, p):
    vals = [_points(module, rep, f"{p}_g4_{k}") for k in ("faible", "moyenne", "intense")]
    if 5 in vals:
        return 5
    return None if None in vals else max(vals)


def _leq_g7(rep, p):
    v = rep.get(f"{p}_g7_voyages")
    if not isinstance(v, list) or not v:
        return None
    zones = [x for x in v if x != "Aucun"]
    if "Aucun" in v and zones:
        return None                                   # incohérent : à clarifier avec le participant
    return LEQ_POINTS_VOYAGES[min(len(zones), 8)]


def _leq_encadrement(rep):
    """Responsabilité d'encadrement 30-65 ans : 8 / 16 / 24 / 32 (plus forte valeur des tranches d'âge) ; None si non concerné ou non renseigné."""
    age = rep.get("_age")
    if age is not None and age < 30:
        return None
    enc = rep.get("ad_s2_encadrement")
    if enc == "Non":
        return LEQ_ENCADREMENT["Aucune personne encadrée / sans objet"]
    if enc != "Oui":
        return None
    vals = [LEQ_ENCADREMENT.get(v) for k, v in rep.items() if re.fullmatch(r"ad_s2_\d+_\d+_effectif", k)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else None


def reserve_cognitive(module, rep):
    out, generaux = {}, []
    for p, _lbl in LEQ_PERIODES:
        pts = [_points(module, rep, f"{p}_g1_famille"), _points(module, rep, f"{p}_g2_musique"), _points(module, rep, f"{p}_g3_art"),
               _leq_g4(module, rep, p), _points(module, rep, f"{p}_g5_lecture"), _points(module, rep, f"{p}_g6_langue"), _leq_g7(rep, p)]
        for (cle, _n), x in zip(LEQ_DOMAINES, pts):
            out[f"leq_{p}_{cle.split('_')[0]}"] = x
        total = None if None in pts else sum(pts)
        out[f"leq_{p}_general"] = total
        out[f"leq_{p}_general_pct"] = None if total is None else _r(total / 35 * 100, 0)
        generaux.append(total)
    out["leq_ad_encadrement"] = _leq_encadrement(rep)
    out["leq_general_somme"] = None if None in generaux else sum(generaux)          # sur 105, si les trois périodes sont disponibles
    out["leq_general_somme_pct"] = None if out["leq_general_somme"] is None else _r(out["leq_general_somme"] / 105 * 100, 0)
    return out


def _variables_leq():
    v = []
    for p, lbl in LEQ_PERIODES:
        for (cle, nom), _ in zip(LEQ_DOMAINES, range(7)):
            v.append((f"leq_{p}_{cle.split('_')[0]}", f"LEQ {lbl} – {cle.split('_')[0].upper()} {nom} (0-5)"))
        v += [(f"leq_{p}_general", f"LEQ – sous-score NON SPÉCIFIQUE {lbl} (0-35 ; vide si un domaine manque ou si la période ne concerne pas le participant)"),
              (f"leq_{p}_general_pct", f"LEQ – sous-score non spécifique {lbl} en % du maximum (score ÷ 35 × 100)")]
    return v + [("leq_ad_encadrement", "LEQ 30 à 65 ans – responsabilité d'encadrement : composante intermédiaire du score spécifique, non normalisée (8 = aucune personne encadrée ; 16 = 1-5 ; 24 = 6-10 ; 32 = plus de 10)"),
                ("leq_general_somme", "LEQ – somme des trois sous-scores NON SPÉCIFIQUES (0-105 ; vide si une période manque). Ce n'est PAS le score total LEQ (scores spécifiques non calculés)"),
                ("leq_general_somme_pct", "LEQ – somme des sous-scores non spécifiques en % du maximum (somme ÷ 105 × 100)")]


# ---------------------------------------------------------------- variables (ordre et libellés pour l'export)
VARIABLES = {"mode_de_vie": (
    [("ipaq_intense", "IPAQ – activité intense (MET-min/semaine, MET = 8)"), ("ipaq_modere", "IPAQ – activité modérée (MET-min/semaine, MET = 4)"),
     ("ipaq_marche", "IPAQ – marche (MET-min/semaine, MET = 3)"), ("ipaq_total", "IPAQ – score total (MET-min/semaine)"),
     ("ipaq_niveau", "IPAQ – catégorie d'activité (Craig 2003 : Faible / Modéré / Élevé)"),
     ("ipaq_critere", "IPAQ – critère de la catégorie atteinte"), ("ipaq_minutes_semaine", "Activité physique totale (minutes/semaine, sans pondération)"),
     ("ipaq_minutes_equivalent_modere", "Activité physique (minutes/semaine, activité intense comptée x2)"),
     ("ipaq_recommandation_150", "Recommandation CDC-ACSM atteinte : ≥ 150 min/semaine (0 = non ; 1 = oui)"),
     ("ipaq_pct_repere_150", "Activité physique en % du repère de 150 min/semaine (minutes équivalentes ÷ 150 × 100)"), ("assis_min_jour", "Temps assis (minutes/jour, hors total IPAQ)"),
     ("psqi_temps_au_lit_h", "PSQI – temps passé au lit (heures)"), ("psqi_efficacite_pct", "PSQI – efficacité habituelle du sommeil (%)"),
     ("psqi_c1", "PSQI C1 – qualité subjective du sommeil (0-3)"), ("psqi_c2", "PSQI C2 – latence d'endormissement (0-3)"),
     ("psqi_c3", "PSQI C3 – durée du sommeil (0-3)"), ("psqi_c4", "PSQI C4 – efficacité habituelle du sommeil (0-3)"),
     ("psqi_c5", "PSQI C5 – perturbations du sommeil (0-3)"), ("psqi_c6", "PSQI C6 – médicaments pour dormir (0-3)"),
     ("psqi_c7", "PSQI C7 – dysfonctionnement diurne (0-3)"), ("psqi_total", "PSQI – score global (0-21, plus élevé = sommeil plus altéré)"),
     ("psqi_pct", "PSQI – score en % du maximum (score ÷ 21 × 100)")]
    + [(c, f"MEDAS – point {c[:4].upper()} ({nom})") for (c, _, _), nom in zip(MEDAS, MEDAS_NOMS)]
    + [("medas_total", "MEDAS – score total (0-14, plus élevé = meilleure adhésion)"),
       ("medas_pct", "MEDAS – score en % du maximum (score ÷ 14 × 100)"),
       ("tabac_statut", "Tabac – statut (0 = jamais ; 1 = ancien ; 2 = actuel)"), ("tabac_duree_ans", "Tabac – durée (années)"),
       ("tabac_paquets_annees", "Tabac – paquets-années"), ("alcool_jours_semaine", "Alcool – jours de consommation par semaine"),
       ("alcool_verres_par_jour", "Alcool – verres standards par jour de consommation"),
       ("alcool_verres_semaine", "Alcool – consommation estimée (verres standards/semaine)"),
       ("alcool_repere_semaine", "Alcool – repère Santé publique France : au plus 10 verres/semaine (0 = non ; 1 = oui)"),
       ("alcool_repere_jour", "Alcool – repère Santé publique France : au plus 2 verres par jour de consommation (0 = non ; 1 = oui)"),
       ("alcool_jours_sans", "Alcool – jours sans alcool par semaine"),
       ("alcool_repere_jours_sans", "Alcool – repère Santé publique France : au moins un jour sans alcool par semaine (0 = non ; 1 = oui)")]),
}
VARIABLES["exposome_psychosocial"] = (
    [(c, f"LSNS-6 – code {c[:4].upper()} (0-5)") for c in LSNS_FAMILLE + LSNS_AMIS]
    + [("lsns_famille", "LSNS-6 – sous-score famille (0-15)"), ("lsns_amis", "LSNS-6 – sous-score amis (0-15)"),
       ("lsns_total", "LSNS-6 – score total (0-30, plus élevé = engagement social plus important)"),
       ("lsns_pct", "LSNS-6 – score en % du maximum (score ÷ 30 × 100)")]
    + [(c, f"HAD-D – code {c[:5].upper()} (0-3)") for c in HAD_D]
    + [("had_d_total", "HAD-D – score total (0-21, plus élevé = plus de symptômes dépressifs)"),
       ("had_d_pct", "HAD-D – score en % du maximum (score ÷ 21 × 100)"),
       ("dep_antecedent", "Antécédent de dépression diagnostiquée (0 = non ; 1 = oui)"),
       ("dep_age_premier_episode", "Dépression – âge au premier épisode (ans)"),
       ("dep_recidive", "Dépression – plusieurs épisodes (0 = non ; 1 = oui)"), ("dep_nb_episodes", "Dépression – nombre d'épisodes"),
       ("dep_prise_en_charge", "Dépression – prise en charge (0 = aucune ; 1 = médicament ; 2 = psychothérapie ; 3 = les deux ; 4 = autre)")])
VARIABLES["expositions_environnementales"] = _variables_env()
VARIABLES["sante_generale"] = _variables_sante()
VARIABLES["reserve_cognitive"] = _variables_leq()
REGISTRE = {"mode_de_vie": "ok", "exposome_psychosocial": "ok", "expositions_environnementales": "ok", "sante_generale": "ok", "reserve_cognitive": "ok"}


def disponible(module_id):
    return module_id in REGISTRE


def variables(module_id):
    return VARIABLES.get(module_id, [])


def calculer(module, rep, age=None):
    """module : dictionnaire YAML du module. Retourne {clé: valeur} dans l'ordre de `variables`."""
    mid = module["id"]
    v = {}
    if mid == "mode_de_vie":
        v.update(ipaq(rep))
        v.update(psqi(module, rep))
        v.update(medas(rep))
        v.update(tabac_alcool(rep, age))
    elif mid == "exposome_psychosocial":
        v.update(exposome_psy(module, rep))
    elif mid == "expositions_environnementales":
        v.update(expositions(module, rep))
    elif mid == "sante_generale":
        v.update(sante_generale(module, rep))
    elif mid == "reserve_cognitive":
        v.update(reserve_cognitive(module, rep))
    else:
        return {}
    return {cle: v.get(cle) for cle, _ in VARIABLES[mid]}


def resume(valeurs):
    """Résumé court pour l'infobulle du tableau de bord."""
    if not valeurs:
        return None
    morceaux = []
    if valeurs.get("ipaq_total") is not None:
        morceaux.append(f"IPAQ {valeurs['ipaq_total']:g}")
    if valeurs.get("psqi_total") is not None:
        morceaux.append(f"PSQI {valeurs['psqi_total']}/21")
    if valeurs.get("medas_total") is not None:
        morceaux.append(f"MEDAS {valeurs['medas_total']}/14")
    env = [f"{g.upper()} {valeurs[g + '_nombre']}/{t}" for g, t in (("env1", 4), ("env2", 5), ("env3", 4)) if valeurs.get(g + "_nombre") is not None]
    if env:
        morceaux.append(" · ".join(env))
    if valeurs.get("imc") is not None:
        morceaux.append(f"IMC {valeurs['imc']:g}" + (f" · CM {valeurs['cm_nombre']}/5" if valeurs.get("cm_nombre") is not None else ""))
    if valeurs.get("lsns_total") is not None:
        morceaux.append(f"LSNS-6 {valeurs['lsns_total']}/30")
    if valeurs.get("had_d_total") is not None:
        morceaux.append(f"HAD-D {valeurs['had_d_total']}/21")
    if valeurs.get("leq_general_somme") is not None:
        morceaux.append(f"LEQ non spécifique {valeurs['leq_general_somme']}/105")
    return " · ".join(morceaux) or None
