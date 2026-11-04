"""
suivi.py : calculs du tableau de bord médecin (aucun affichage ici).
Règles :
- Seul le DERNIER passage de chaque patient compte pour les statistiques et la valeur affichée.
- Un module est « complet » uniquement si toutes ses questions obligatoires visibles sont renseignées.
- Pourcentage d'un module partiel = questions obligatoires renseignées / questions obligatoires à renseigner.
- Si le module définit un bloc « scoring » (voir scoring.py), sa valeur complète est « score/maximum » ;
  sinon elle est « 100 % ».
"""
from statistics import mean, stdev

import cotations
import logique
import scoring


def ecart_type(valeurs):
    return stdev(valeurs) if len(valeurs) > 1 else 0.0


def modules_suivis(modules):
    """Modules comptés dans le suivi : tout sauf le consentement (unique) et les modules hors rapport."""
    return [m for m in modules if not m.get("unique") and not m.get("hors_rapport")]


def ordinal(n):
    return "1er" if n == 1 else f"{n}ème"


def _repondu(v):
    return not (v is None or v == "" or v == [] or v is False)


VIDE = dict(etat="vide", pct=0, texte="0 %", score=None, resume=None)


def statut_module(m, rep):
    """Retourne {etat: vide|partiel|complet, pct, texte, score}."""
    questions = [q for q in m["questions"] if q["type"] not in ("section", "info")]
    if not any(_repondu(rep.get(q["id"])) for q in questions):
        return dict(VIDE)
    requises = [q for q in questions if q.get("obligatoire", True) and logique.est_visible(q, rep)]
    manquantes = [q for q in requises if logique.est_manquante(q, rep.get(q["id"]))]
    if not manquantes:
        sc = scoring.score_module(m, rep) if m.get("scoring") else None
        texte = f"{sc['score']}/{sc['max']}" if sc and sc["max"] else "100 %"
        resume = cotations.resume(cotations.calculer(m, rep)) if cotations.disponible(m["id"]) else None
        return dict(etat="complet", pct=100, texte=texte, score=sc, resume=resume)
    pct = int(100 * (len(requises) - len(manquantes)) / len(requises)) if requises else 0
    return dict(etat="partiel", pct=pct, texte=f"{pct} %", score=None, resume=None)


def analyser(modules, patients, reponses, dates):
    """Assemble, pour chaque patient, l'historique par module + les statistiques globales."""
    suivis = modules_suivis(modules)
    consentements = [m for m in modules if m.get("unique")]
    lignes = []
    for p in patients:
        par_passage = reponses.get(p["numero"], {})
        passages = sorted(par_passage)
        hist = {m["id"]: [(n, statut_module(m, par_passage[n])) for n in passages] for m in suivis}
        dernier = {mid: (h[-1][1] if h else dict(VIDE)) for mid, h in hist.items()}
        complets = sum(1 for s in dernier.values() if s["etat"] == "complet")
        consent = None
        if consentements:
            consent = bool(passages) and all(
                statut_module(m, par_passage[passages[-1]])["etat"] == "complet" for m in consentements)
        statut = "non_demarre" if not passages else ("termine" if suivis and complets == len(suivis) else "en_cours")
        lignes.append(dict(p, passages=passages, hist=hist, dernier=dernier, consent=consent, statut=statut,
                           pct_complets=100 * complets / len(suivis) if suivis else 0.0,
                           derniere_activite=max(dates.get(p["numero"], {}).values(), default="")))
    pcts = [l["pct_complets"] for l in lignes]
    par_groupe = {}
    for g in ("TEST", "CONTROL"):
        v = [l["pct_complets"] for l in lignes if l["groupe"] == g]
        par_groupe[g] = dict(n=len(v), moyenne=mean(v) if v else 0.0, sd=ecart_type(v))
    par_module = {m["id"]: (100 * sum(1 for l in lignes if l["dernier"][m["id"]]["etat"] == "complet") / len(lignes)
                            if lignes else 0.0) for m in suivis}
    vm = list(par_module.values())
    return dict(
        lignes=lignes, suivis=suivis, n=len(lignes),
        moyenne=mean(pcts) if pcts else 0.0, sd=ecart_type(pcts), par_groupe=par_groupe,
        par_module=par_module, module_moyenne=mean(vm) if vm else 0.0, module_sd=ecart_type(vm),
        n_termine=sum(1 for l in lignes if l["statut"] == "termine"),
        n_en_cours=sum(1 for l in lignes if l["statut"] == "en_cours"),
        n_non_demarre=sum(1 for l in lignes if l["statut"] == "non_demarre"),
        n_repasses=sum(1 for l in lignes if len(l["passages"]) > 1))
