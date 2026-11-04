"""
logique.py : règles communes à l'application patient et à l'espace médecin
(lecture des modules, questions visibles, questions obligatoires manquantes...).
"""
import glob
import os

import yaml

DOSSIER = os.path.dirname(os.path.abspath(__file__))


def charger_modules():
    """Lit tous les fichiers modules/*.yaml, dans l'ordre alphabétique (00_, 01_, 02_, ...)."""
    modules = []
    for f in sorted(glob.glob(os.path.join(DOSSIER, "modules", "*.yaml"))):
        with open(f, encoding="utf-8") as fh:
            modules.append(yaml.safe_load(fh))
    return modules


def est_vide(v):
    return v is None or v == "" or v == []


def est_manquante(q, v):
    """Vrai si la question est obligatoire et n'a pas de réponse valide (une case à cocher obligatoire doit être cochée)."""
    if not q.get("obligatoire", True) or q["type"] in ("section", "info"):
        return False
    if q["type"] == "case_a_cocher":
        return not v
    return est_vide(v)


def est_visible(q, saisies):
    """Question conditionnelle : 'si: {question: id, egal: valeur}', '{... rempli: true}', '{... sup: 0}' (nombre > 0) ou '{... contient: option}' (choix multiples)."""
    cond = q.get("si")
    if not cond:
        return True
    v = saisies.get(cond["question"])
    if "egal" in cond:
        attendues = cond["egal"] if isinstance(cond["egal"], list) else [cond["egal"]]
        return v in attendues
    if "contient" in cond:
        return isinstance(v, list) and cond["contient"] in v
    if "sup" in cond:
        return v is not None and v > cond["sup"]
    if cond.get("rempli"):
        return not est_vide(v)
    return True


def premiere_etape(modules, reponses):
    """Reprend au premier module dont une question obligatoire n'a pas de réponse."""
    for i, m in enumerate(modules):
        for q in m["questions"]:
            if est_visible(q, reponses) and est_manquante(q, reponses.get(q["id"])):
                return i
    return len(modules)
