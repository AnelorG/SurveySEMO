"""
scoring.py : calcule le score d'un module à partir de son fichier YAML.
Règle : on additionne les 'scores' des options choisies pour les questions
listées dans scoring > questions (questions à choix unique uniquement).
"""


def score_module(module, reponses):
    config = module.get("scoring")
    if not config:
        return None
    total, maximum = 0, 0
    for q in module["questions"]:
        if q["id"] not in config["questions"] or "scores" not in q:
            continue
        maximum += max(q["scores"])
        valeur = reponses.get(q["id"])
        if valeur in q["options"]:
            total += q["scores"][q["options"].index(valeur)]
    message = ""
    for tranche in config.get("interpretation", []):
        if tranche["min"] <= total <= tranche["max"]:
            message = tranche["message"]
    return {"score": total, "max": maximum, "message": message}
