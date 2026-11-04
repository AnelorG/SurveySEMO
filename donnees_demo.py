"""
Crée des patients FICTIFS (noms inventés, réponses aléatoires) pour découvrir le tableau de bord. F5 dans Spyder.
⚠️ À utiliser sur une base de TEST uniquement. Pour tout effacer ensuite : reinitialiser_base.py (MODE = "tout").
"""
import os
import random
import sys
from datetime import date

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
import db
import logique

# (numéro, nom, prénom, naissance, état, parties repassées lors des passages 2, 3...)
PATIENTS = [
    ("P012", "Martin", "Claire", date(1961, 3, 14), "complet", [["mode_de_vie"]]),
    ("P047", "Bernard", "Louis", date(1955, 7, 2), "complet", []),
    ("P103", "Petit", "Sophie", date(1972, 11, 23), "complet", [["mode_de_vie"], ["mode_de_vie"]]),
    ("P188", "Robert", "Jean", date(1948, 1, 9), "partiel", []),
    ("P251", "Richard", "Anne", date(1980, 5, 30), "complet", []),
    ("P299", "Durand", "Paul", date(1967, 9, 17), "debut", []),
    ("P345", "Dubois", "Marie", date(1958, 12, 5), "aucun", []),
    ("P512", "Moreau", "Pierre", date(1950, 4, 21), "complet", [["mode_de_vie"]]),
    ("P548", "Laurent", "Élise", date(1975, 8, 8), "complet", []),
    ("P603", "Simon", "Marc", date(1963, 2, 27), "partiel", []),
    ("P677", "Michel", "Nadia", date(1969, 10, 12), "complet", []),
    ("P731", "Lefebvre", "Hugo", date(1953, 6, 3), "partiel", []),
    ("P805", "Garcia", "Julie", date(1985, 1, 19), "complet", [["mode_de_vie"]]),
    ("P902", "Roux", "Antoine", date(1946, 11, 30), "aucun", []),
]


def valeur(q, rng):
    t = q["type"]
    if t == "oui_non":
        return rng.choice(["Oui", "Non"])
    if t == "choix_unique":
        return rng.choice(q["options"])
    if t == "choix_multiple":
        libres = [o for o in q["options"] if o not in q.get("exclusives", [])]
        choix = rng.sample(libres, rng.randint(0, len(libres)))
        return choix or [q["exclusives"][0] if q.get("exclusives") else q["options"][0]]
    if t == "nombre":
        lo, hi = q.get("min", 0), q.get("max", 100)
        return float(round(lo + (hi - lo) * rng.random() * 0.45))
    if t == "texte_court":
        return rng.choice(["Infirmier", "Enseignant", "Guitare", "Randonnée", "Anglais"])
    if t == "texte_libre":
        return "RAS"
    if t == "case_a_cocher":
        return True if q.get("obligatoire", True) else rng.choice([True, False])
    if t == "heure":
        return "07:00" if "lever" in q["id"] else rng.choice(["22:30", "23:00", "23:30"])
    return None


def remplir(m, rng, partiel=False, age=None):
    reponses = {}
    for q in m["questions"]:
        if q["type"] in ("section", "info"):
            continue
        reponses[q["id"]] = valeur(q, rng) if logique.est_visible(q, reponses) else None
    reponses["_age"] = age
    if partiel:  # la 2e moitié des réponses données est effacée
        donnees = [k for k, v in reponses.items() if v not in (None, "", [], False)]
        for k in donnees[len(donnees) // 2:]:
            reponses[k] = None
    return reponses


def creer(confirmer=True):
    if confirmer and input(f"Ajouter {len(PATIENTS)} patients FICTIFS à la base ? Tapez OUI : ").strip() != "OUI":
        print("Annulé.")
        return
    db.init_db()
    modules = logique.charger_modules()
    for graine, (numero, nom, prenom, naissance, etat, repassages) in enumerate(PATIENTS):
        rng = random.Random(graine)
        db.ajouter_patient(numero, nom, prenom, naissance)
        age = date.today().year - naissance.year
        if etat == "aucun":
            continue
        courant = {}
        for m in modules:
            if m.get("unique") or etat != "debut" or m is modules[1]:
                courant[m["id"]] = remplir(m, rng, partiel=(etat == "debut" and m is modules[1]), age=age)
            if etat == "debut" and not m.get("unique") and m is not modules[1]:
                break
        if etat == "partiel":  # la dernière partie est seulement entamée
            dernier = [m for m in modules if not m.get("unique")][-1]
            courant[dernier["id"]] = remplir(dernier, rng, partiel=True, age=age)
        for p, a_refaire in enumerate([[]] + repassages, start=1):
            for m in modules:
                if m["id"] in a_refaire:
                    courant[m["id"]] = remplir(m, rng, age=age)
            for m in modules:
                if m["id"] in courant:
                    db.sauver_reponses(numero, m["id"], courant[m["id"]], p)
    print(f"{len(PATIENTS)} patients fictifs créés.")


if __name__ == "__main__":
    creer()
