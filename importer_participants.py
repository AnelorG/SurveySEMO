"""
Importe une liste de participants (Nom, Prénom, Date de naissance) dans les bases, SANS passer par l'interface web.
À lancer dans le terminal, depuis le dossier du projet (SurveySEMO) :

    python importer_participants.py liste.csv              -> APERÇU : montre ce qui serait fait, n'écrit RIEN
    python importer_participants.py liste.csv --appliquer  -> crée réellement les participants

Fichier d'entrée : CSV (séparateur « ; » ou « , »), une ligne d'en-têtes, colonnes reconnues (majuscules/accents indifférents) :
    nom ; prenom ; naissance            (obligatoires ; naissance au format JJ/MM/AAAA ou AAAA-MM-JJ)
    numero                              (facultatif : numéro de randomisation imposé, ex. P017)
    groupe                              (facultatif : TEST ou CONTROL)

Attribution du numéro et du groupe. Le groupe est DÉDUIT du numéro : P001 à P499 = TEST ; P500 à P999 = CONTROL.
  - colonne « numero » renseignée   -> ce numéro est utilisé (et donc le groupe qui en découle) ;
  - sinon colonne « groupe » remplie -> un numéro libre tiré au hasard dans la plage de ce groupe ;
  - sinon                           -> les groupes sont attribués par blocs permutés de 4 (2 TEST + 2 CONTROL, ordre aléatoire),
                                       puis un numéro libre est tiré au hasard dans la plage du groupe.
    Si votre protocole impose une liste de randomisation officielle, fournissez-la dans les colonnes « numero » ou « groupe ».

Après --appliquer, un fichier attribution_AAAAMMJJ_HHMMSS.csv (nom, prénom, naissance, numéro, groupe) est créé : il fait le lien entre
les identités et les numéros. DONNÉE SENSIBLE : rangez-le dans un endroit sécurisé, ne le versez JAMAIS sur GitHub, supprimez la liste d'origine.
Les participants sont créés dans les bases du dossier où le script est lancé : pour la production, lancez-le SUR LE SERVEUR.
"""
import csv
import os
import re
import secrets
import sys
import unicodedata
from datetime import date, datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
import db

PLAGES = {"TEST": range(1, 500), "CONTROL": range(500, 1000)}


def _cle(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", s)


ALIAS = {"nom": "nom", "prenom": "prenom", "naissance": "naissance", "datedenaissance": "naissance", "datenaissance": "naissance",
         "ddn": "naissance", "numero": "numero", "numerorandomisation": "numero", "numerodrandomisation": "numero", "groupe": "groupe"}


def _lire_date(txt):
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(txt.strip(), fmt).date()
        except ValueError:
            pass
    return None


def lire_csv(chemin):
    for enc in ("utf-8-sig", "cp1252"):
        try:
            with open(chemin, encoding=enc, newline="") as f:
                texte = f.read()
            break
        except UnicodeDecodeError:
            continue
    sep = ";" if texte.split("\n", 1)[0].count(";") >= texte.split("\n", 1)[0].count(",") else ","
    lecteur = csv.DictReader(texte.splitlines(), delimiter=sep)
    lignes = []
    for i, brut in enumerate(lecteur, start=2):
        ligne = {ALIAS[_cle(k)]: (v or "").strip() for k, v in brut.items() if k and _cle(k) in ALIAS}
        if any(ligne.values()):
            ligne["_ligne"] = i
            lignes.append(ligne)
    return lignes


def _tirer(groupe, pris):
    libres = [f"P{n:03d}" for n in PLAGES[groupe] if f"P{n:03d}" not in pris]
    if not libres:
        raise SystemExit(f"Plus aucun numéro libre pour le groupe {groupe}.")
    return secrets.choice(libres)


def _blocs(n):
    """n groupes attribués par blocs permutés de 4 (2 TEST + 2 CONTROL, ordre aléatoire)."""
    sortie = []
    while len(sortie) < n:
        bloc = ["TEST", "TEST", "CONTROL", "CONTROL"]
        for i in range(3, 0, -1):
            j = secrets.randbelow(i + 1)
            bloc[i], bloc[j] = bloc[j], bloc[i]
        sortie += bloc
    return sortie[:n]


def preparer(lignes):
    """Valide les lignes et attribue numéros et groupes. Retourne (plan, erreurs)."""
    db.init_db()
    pris = set(db.numeros_existants()) | set(db.numeros_supprimes())
    with db.connexion_identites() as ci:
        pris |= {l[0] for l in ci.execute("SELECT numero FROM identites")}
        deja = {(_cle(n), _cle(p), nai) for n, p, nai in ci.execute("SELECT nom, prenom, naissance FROM identites")}
    erreurs, plan, vus = [], [], set()
    for l in lignes:
        ou = f"ligne {l['_ligne']}"
        nom, prenom, naissance = l.get("nom", ""), l.get("prenom", ""), _lire_date(l.get("naissance", ""))
        if not nom or not prenom:
            erreurs.append(f"{ou} : nom ou prénom manquant"); continue
        if naissance is None or naissance >= date.today():
            erreurs.append(f"{ou} : date de naissance invalide « {l.get('naissance', '')} » (attendu JJ/MM/AAAA)"); continue
        ident = (_cle(nom), _cle(prenom), naissance.isoformat())
        if ident in deja or ident in vus:
            erreurs.append(f"{ou} : {prenom} {nom} ({naissance:%d/%m/%Y}) existe déjà ou apparaît deux fois"); continue
        vus.add(ident)
        numero = db.normaliser_numero(l["numero"]) if l.get("numero") else ""
        groupe = l.get("groupe", "").strip().upper()
        if numero and not re.fullmatch(r"P\d{3}", numero):
            erreurs.append(f"{ou} : numéro « {numero} » invalide (attendu P001 à P999)"); continue
        if groupe and groupe not in PLAGES:
            erreurs.append(f"{ou} : groupe « {groupe} » invalide (TEST ou CONTROL)"); continue
        if numero and numero in pris:
            erreurs.append(f"{ou} : le numéro {numero} est déjà attribué"); continue
        if numero and groupe and db.groupe_pour(numero) != groupe:
            erreurs.append(f"{ou} : le numéro {numero} correspond au groupe {db.groupe_pour(numero)}, pas {groupe}"); continue
        if numero:
            pris.add(numero)
        plan.append(dict(ligne=l["_ligne"], nom=nom, prenom=prenom, naissance=naissance, numero=numero, groupe=groupe))
    # attribution des groupes (blocs permutés) puis tirage des numéros
    sans = [p for p in plan if not p["numero"] and not p["groupe"]]
    for p, g in zip(sans, _blocs(len(sans))):
        p["groupe"] = g
    for p in plan:
        if not p["numero"]:
            p["numero"] = _tirer(p["groupe"], pris)
            pris.add(p["numero"])
        p["groupe"] = db.groupe_pour(p["numero"])
    return plan, erreurs


def appliquer(plan):
    for p in plan:
        db.ajouter_si_absent(p["numero"], p["naissance"])
        db.ajouter_identite_si_absente(p["numero"], p["nom"], p["prenom"], p["naissance"], source="import script")
        db.journaliser("Création du participant", p["numero"], {"groupe": p["groupe"], "source": "import script"}, "import script")
    nom_fichier = f"attribution_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with open(nom_fichier, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["nom", "prenom", "naissance", "numero", "groupe"])
        for p in sorted(plan, key=lambda x: x["numero"]):
            w.writerow([p["nom"], p["prenom"], p["naissance"].strftime("%d/%m/%Y"), p["numero"], p["groupe"]])
    return nom_fichier


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        sys.exit(1)
    plan, erreurs = preparer(lire_csv(args[0]))
    for e in erreurs:
        print("⚠️ ", e)
    print(f"\n{len(plan)} participant(s) à créer ({sum(p['groupe'] == 'TEST' for p in plan)} TEST, "
          f"{sum(p['groupe'] == 'CONTROL' for p in plan)} CONTROL) :")
    for p in sorted(plan, key=lambda x: x["numero"]):
        print(f"  {p['numero']}  {p['groupe']:<8} {p['prenom']} {p['nom']}  ({p['naissance']:%d/%m/%Y})")
    if erreurs:
        print(f"\n{len(erreurs)} ligne(s) refusée(s) (voir ⚠️ ci-dessus) : corrigez le fichier puis relancez.")
        sys.exit(1)
    if "--appliquer" not in sys.argv:
        print("\nAPERÇU seulement : rien n'a été écrit. Ajoutez --appliquer pour créer ces participants.")
        sys.exit(0)
    if input("\nCréer ces participants dans les bases ? Tapez OUI pour confirmer : ").strip() != "OUI":
        print("Annulé, rien n'a été écrit.")
        sys.exit(0)
    print("Participants créés. Fichier d'attribution (SENSIBLE, à ranger en lieu sûr) :", appliquer(plan))
