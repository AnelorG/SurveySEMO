"""
db.py : tout ce qui touche à la base de données SQLite.
SQLite = un simple fichier (questionnaire.db) créé automatiquement à côté du code.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "questionnaire.db")
IDENTITES_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "identites.db")
MAX_TENTATIVES = 5  # après 5 échecs, le compte est bloqué


def connexion():
    return sqlite3.connect(DB_PATH)


def normaliser_numero(v):
    """'  p001 ' -> 'P001' : évite les erreurs de casse ou d'espaces à la connexion."""
    return str(v).strip().upper()


def connexion_identites():
    return sqlite3.connect(IDENTITES_PATH)


def init_db():
    """Crée les tables si elles n'existent pas encore."""
    with connexion_identites() as ci:
        # FICHIER SÉPARÉ (identites.db) : nom, prénom, date de naissance. Jamais mélangé aux réponses.
        ci.execute("""CREATE TABLE IF NOT EXISTS identites (
            numero TEXT PRIMARY KEY, nom TEXT, prenom TEXT, naissance TEXT,
            groupe TEXT, date_inclusion TEXT, source TEXT)""")
        # Suivi du patient : effets indésirables, remarques, plaintes, conditions de complétion...
        ci.execute("""CREATE TABLE IF NOT EXISTS suivi (
            id INTEGER PRIMARY KEY AUTOINCREMENT, numero TEXT NOT NULL, categorie TEXT NOT NULL, options TEXT,
            gravite TEXT, evolution TEXT, grave INTEGER DEFAULT 0, date_evenement TEXT, commentaire TEXT,
            cree_le TEXT, cree_par TEXT)""")
        # Journal d'audit : qui a fait quoi, quand (jamais de réponse aux questionnaires)
        ci.execute("""CREATE TABLE IF NOT EXISTS journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT, date_heure TEXT, utilisateur TEXT, action TEXT, numero TEXT, details TEXT)""")
    with connexion() as c:
        # Table 1 : qui peut se connecter (la date de naissance n'est JAMAIS stockée en clair)
        c.execute("""CREATE TABLE IF NOT EXISTS participants (
            numero TEXT PRIMARY KEY,
            sel TEXT NOT NULL,
            hash_naissance TEXT NOT NULL,
            tentatives INTEGER NOT NULL DEFAULT 0)""")
        # Petite table pour mémoriser des informations techniques (ex. date de dernière lecture de l'Excel)
        c.execute("CREATE TABLE IF NOT EXISTS meta (cle TEXT PRIMARY KEY, valeur TEXT)")
        # Table 2 : une ligne par réponse (numéro + passage + question).
        # "passage" = 1 pour le 1er remplissage, 2 si le participant repasse le questionnaire, etc.
        # (migration automatique des anciennes bases qui n'avaient pas cette colonne)
        colonnes = [l[1] for l in c.execute("PRAGMA table_info(reponses)")]
        migrer = bool(colonnes) and "passage" not in colonnes
        if migrer:
            c.execute("ALTER TABLE reponses RENAME TO reponses_ancienne")
        c.execute("""CREATE TABLE IF NOT EXISTS reponses (
            numero TEXT NOT NULL,
            passage INTEGER NOT NULL DEFAULT 1,
            question_id TEXT NOT NULL,
            module_id TEXT NOT NULL,
            valeur TEXT,
            date_maj TEXT,
            PRIMARY KEY (numero, passage, question_id))""")
        if migrer:
            c.execute("""INSERT INTO reponses (numero, passage, question_id, module_id, valeur, date_maj)
                         SELECT numero, 1, question_id, module_id, valeur, date_maj FROM reponses_ancienne""")
            c.execute("DROP TABLE reponses_ancienne")


def _hash(naissance, sel_hex):
    """Transforme la date de naissance en empreinte irréversible (PBKDF2 + sel aléatoire)."""
    return hashlib.pbkdf2_hmac(
        "sha256", naissance.isoformat().encode(), bytes.fromhex(sel_hex), 200_000
    ).hex()


def lire_meta(cle):
    with connexion() as c:
        ligne = c.execute("SELECT valeur FROM meta WHERE cle=?", (cle,)).fetchone()
    return ligne[0] if ligne else None


def ecrire_meta(cle, valeur):
    with connexion() as c:
        c.execute("INSERT OR REPLACE INTO meta (cle, valeur) VALUES (?,?)", (cle, str(valeur)))


def numeros_existants():
    with connexion() as c:
        return {l[0] for l in c.execute("SELECT numero FROM participants")}


def ajouter_si_absent(numero, naissance):
    """Ajoute le participant s'il n'existe pas. N'écrase JAMAIS un participant existant."""
    sel = os.urandom(16).hex()
    with connexion() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO participants (numero, sel, hash_naissance, tentatives) VALUES (?,?,?,0)",
            (numero, sel, _hash(naissance, sel)),
        )
        return cur.rowcount == 1


def mettre_a_jour_naissance(numero, naissance):
    """Corrige la date de naissance d'un participant existant. Ne touche pas à ses réponses."""
    with connexion() as c:
        sel, h = c.execute("SELECT sel, hash_naissance FROM participants WHERE numero=?", (numero,)).fetchone()
        if hmac.compare_digest(_hash(naissance, sel), h):
            return False
        nouveau_sel = os.urandom(16).hex()
        c.execute("UPDATE participants SET sel=?, hash_naissance=?, tentatives=0 WHERE numero=?",
                  (nouveau_sel, _hash(naissance, nouveau_sel), numero))
        return True


def creer_participant(numero, naissance):
    numero = normaliser_numero(numero)
    sel = os.urandom(16).hex()
    with connexion() as c:
        c.execute(
            "INSERT OR REPLACE INTO participants (numero, sel, hash_naissance, tentatives) VALUES (?,?,?,0)",
            (numero, sel, _hash(naissance, sel)),
        )


def debloquer(numero):
    with connexion() as c:
        c.execute("UPDATE participants SET tentatives=0 WHERE numero=?", (numero,))


def verifier_participant(numero, naissance):
    """Retourne 'ok', 'bloque' ou 'refuse'."""
    with connexion() as c:
        ligne = c.execute(
            "SELECT sel, hash_naissance, tentatives FROM participants WHERE numero=?", (numero,)
        ).fetchone()
        if ligne is None:
            return "refuse"
        sel, hash_attendu, tentatives = ligne
        if tentatives >= MAX_TENTATIVES:
            return "bloque"
        if hmac.compare_digest(_hash(naissance, sel), hash_attendu):
            c.execute("UPDATE participants SET tentatives=0 WHERE numero=?", (numero,))
            return "ok"
        c.execute("UPDATE participants SET tentatives=tentatives+1 WHERE numero=?", (numero,))
        return "refuse"


def sauver_reponses(numero, module_id, reponses, passage=1):
    """Enregistre (ou met à jour) les réponses d'un module pour un passage donné."""
    maintenant = datetime.now().isoformat(timespec="seconds")
    with connexion() as c:
        for qid, valeur in reponses.items():
            c.execute(
                """INSERT INTO reponses (numero, passage, question_id, module_id, valeur, date_maj)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(numero, passage, question_id)
                   DO UPDATE SET valeur=excluded.valeur, date_maj=excluded.date_maj""",
                (numero, passage, qid, module_id, json.dumps(valeur, ensure_ascii=False), maintenant),
            )


def liste_passages(numero):
    with connexion() as c:
        return [l[0] for l in c.execute(
            "SELECT DISTINCT passage FROM reponses WHERE numero=? ORDER BY passage", (numero,))]


def date_passage(numero, passage):
    with connexion() as c:
        l = c.execute("SELECT MAX(date_maj) FROM reponses WHERE numero=? AND passage=?", (numero, passage)).fetchone()
    return l[0] if l and l[0] else None


def charger_reponses(numero, passage=None):
    """Réponses d'un passage (par défaut : le plus récent)."""
    if passage is None:
        p = liste_passages(numero)
        passage = p[-1] if p else 1
    with connexion() as c:
        lignes = c.execute(
            "SELECT question_id, valeur FROM reponses WHERE numero=? AND passage=?", (numero, passage)
        ).fetchall()
    return {qid: json.loads(v) for qid, v in lignes}


def copier_modules(numero, de_passage, vers_passage, module_ids):
    """Recopie dans un nouveau passage les réponses des modules que le participant ne repasse pas."""
    if not module_ids:
        return
    marques = ",".join("?" * len(module_ids))
    with connexion() as c:
        c.execute(
            f"""INSERT OR IGNORE INTO reponses (numero, passage, question_id, module_id, valeur, date_maj)
                SELECT numero, ?, question_id, module_id, valeur, date_maj FROM reponses
                WHERE numero=? AND passage=? AND module_id IN ({marques})""",
            (vers_passage, numero, de_passage, *module_ids))


# ---------------------------------------------------------------- espace médecin
def groupe_pour(numero):
    """P000 : numéro < 500 -> groupe TEST ; sinon CONTROL."""
    chiffres = re.sub(r"\D", "", str(numero))
    if not chiffres:
        return "?"
    return "TEST" if int(chiffres) < 500 else "CONTROL"


def ajouter_identite_si_absente(numero, nom, prenom, naissance, source="excel"):
    with connexion_identites() as ci:
        cur = ci.execute(
            "INSERT OR IGNORE INTO identites (numero, nom, prenom, naissance, groupe, date_inclusion, source) VALUES (?,?,?,?,?,?,?)",
            (numero, nom or "", prenom or "", naissance.isoformat() if naissance else "", groupe_pour(numero),
             datetime.now().isoformat(timespec="seconds"), source))
        return cur.rowcount == 1


def numero_pris(numero):
    with connexion_identites() as ci:
        dans_identites = ci.execute("SELECT 1 FROM identites WHERE numero=?", (numero,)).fetchone() is not None
    return dans_identites or numero in numeros_existants() or numero in numeros_supprimes()


def tirer_numero():
    """Numéro de randomisation au hasard : P001 à P999, jamais déjà attribué. None si tout est pris."""
    pris = numeros_existants() | numeros_supprimes()
    with connexion_identites() as ci:
        pris |= {l[0] for l in ci.execute("SELECT numero FROM identites")}
    libres = [f"P{n:03d}" for n in range(1, 1000) if f"P{n:03d}" not in pris]
    return secrets.choice(libres) if libres else None


def ajouter_patient(numero, nom, prenom, naissance, utilisateur="médecin"):
    """Inclut un patient (formulaire médecin). Retourne False si le numéro existe déjà."""
    init_db()
    if numero_pris(numero):
        return False
    ajouter_si_absent(numero, naissance)
    ajouter_identite_si_absente(numero, nom, prenom, naissance, source="formulaire")
    journaliser("Création du patient", numero, {"groupe": groupe_pour(numero)}, utilisateur)
    return True


def lister_patients():
    """Tous les patients inclus (base des participants) + identité si connue."""
    with connexion_identites() as ci:
        ident = {l[0]: l[1:] for l in ci.execute(
            "SELECT numero, nom, prenom, naissance, groupe, date_inclusion, source FROM identites")}
    patients = []
    for numero in sorted(numeros_existants()):
        nom, prenom, naissance, groupe, inclusion, source = ident.get(numero, ("", "", "", groupe_pour(numero), "", ""))
        patients.append(dict(numero=numero, nom=nom, prenom=prenom, naissance=naissance,
                             groupe=groupe or groupe_pour(numero), inclusion=inclusion, source=source))
    return patients


def toutes_reponses():
    """{numero: {passage: {question_id: valeur}}} en une seule requête."""
    sortie = {}
    with connexion() as c:
        for numero, passage, qid, v in c.execute("SELECT numero, passage, question_id, valeur FROM reponses"):
            sortie.setdefault(numero, {}).setdefault(passage, {})[qid] = json.loads(v)
    return sortie


def dates_passages():
    """{numero: {passage: date de dernière modification}}."""
    sortie = {}
    with connexion() as c:
        for numero, passage, d in c.execute("SELECT numero, passage, MAX(date_maj) FROM reponses GROUP BY numero, passage"):
            sortie.setdefault(numero, {})[passage] = d
    return sortie


def dates_detaillees():
    """{numero: {passage: {module_id: (première saisie, dernière saisie)}}}."""
    sortie = {}
    with connexion() as c:
        for numero, passage, module_id, d1, d2 in c.execute(
                "SELECT numero, passage, module_id, MIN(date_maj), MAX(date_maj) FROM reponses GROUP BY numero, passage, module_id"):
            sortie.setdefault(numero, {}).setdefault(passage, {})[module_id] = (d1, d2)
    return sortie


def tentatives_connexion():
    """{numero: nombre d'échecs de connexion consécutifs} (un compte est bloqué à partir de MAX_TENTATIVES)."""
    with connexion() as c:
        return {n: t for n, t in c.execute("SELECT numero, tentatives FROM participants")}


# ---------------------------------------------------------------- journal d'audit, modification, suivi, suppression
def journaliser(action, numero=None, details=None, utilisateur="système"):
    with connexion_identites() as ci:
        ci.execute("INSERT INTO journal (date_heure, utilisateur, action, numero, details) VALUES (?,?,?,?,?)",
                   (datetime.now().isoformat(timespec="seconds"), utilisateur, action, numero,
                    json.dumps(details, ensure_ascii=False) if details is not None else None))


def lire_journal(numero=None):
    """Entrées du journal (les plus récentes d'abord), pour un patient ou pour tous."""
    requete = "SELECT date_heure, utilisateur, action, numero, details FROM journal"
    with connexion_identites() as ci:
        lignes = ci.execute(requete + (" WHERE numero=?" if numero else "") + " ORDER BY id DESC",
                            (numero,) if numero else ()).fetchall()
    return [dict(date_heure=a, utilisateur=b, action=c, numero=n, details=json.loads(e) if e else None)
            for a, b, c, n, e in lignes]


def numeros_supprimes():
    with connexion_identites() as ci:
        return {l[0] for l in ci.execute("SELECT numero FROM journal WHERE action='Suppression du patient' AND numero IS NOT NULL")}


def get_identite(numero):
    with connexion_identites() as ci:
        l = ci.execute("SELECT nom, prenom, naissance FROM identites WHERE numero=?", (numero,)).fetchone()
    return dict(nom=l[0], prenom=l[1], naissance=l[2]) if l else dict(nom="", prenom="", naissance="")


def modifier_identite(numero, nom, prenom, naissance, utilisateur="médecin"):
    """Met à jour nom / prénom / date de naissance. Si la date change, la connexion du patient est mise à jour.
    Retourne {champ: (avant, après)} (vide si rien n'a changé)."""
    avant = get_identite(numero)
    apres = dict(nom=nom.strip(), prenom=prenom.strip(), naissance=naissance.isoformat())
    changements = {k: (avant[k], apres[k]) for k in apres if (avant[k] or "") != apres[k]}
    if not changements:
        return {}
    with connexion_identites() as ci:
        ci.execute("INSERT OR IGNORE INTO identites (numero, nom, prenom, naissance, groupe, date_inclusion, source) VALUES (?,?,?,?,?,?,?)",
                   (numero, "", "", "", groupe_pour(numero), datetime.now().isoformat(timespec="seconds"), "espace médecin"))
        ci.execute("UPDATE identites SET nom=?, prenom=?, naissance=? WHERE numero=?",
                   (apres["nom"], apres["prenom"], apres["naissance"], numero))
    if "naissance" in changements:
        mettre_a_jour_naissance(numero, naissance)  # le patient devra utiliser la nouvelle date pour se connecter
    journaliser("Modification des informations de base", numero,
                {k: {"avant": a, "apres": b} for k, (a, b) in changements.items()}, utilisateur)
    return changements


def debloquer_compte(numero, utilisateur="médecin"):
    debloquer(numero)
    journaliser("Déblocage du compte patient", numero, None, utilisateur)


def ajouter_suivi(numero, categorie, options, gravite, evolution, grave, date_evenement, commentaire, utilisateur="médecin"):
    with connexion_identites() as ci:
        ci.execute("""INSERT INTO suivi (numero, categorie, options, gravite, evolution, grave, date_evenement, commentaire, cree_le, cree_par)
                      VALUES (?,?,?,?,?,?,?,?,?,?)""",
                   (numero, categorie, json.dumps(options, ensure_ascii=False), gravite, evolution, int(bool(grave)),
                    date_evenement.isoformat() if date_evenement else "", (commentaire or "").strip(),
                    datetime.now().isoformat(timespec="seconds"), utilisateur))
    journaliser("Ajout d'un suivi", numero, {"categorie": categorie, "grave": bool(grave)}, utilisateur)


def lister_suivi(numero=None):
    requete = "SELECT numero, categorie, options, gravite, evolution, grave, date_evenement, commentaire, cree_le, cree_par FROM suivi"
    with connexion_identites() as ci:
        lignes = ci.execute(requete + (" WHERE numero=?" if numero else "") + " ORDER BY date_evenement DESC, id DESC",
                            (numero,) if numero else ()).fetchall()
    cles = ("numero", "categorie", "options", "gravite", "evolution", "grave", "date_evenement", "commentaire", "cree_le", "cree_par")
    sortie = []
    for l in lignes:
        e = dict(zip(cles, l))
        e["options"], e["grave"] = json.loads(e["options"] or "[]"), bool(e["grave"])
        sortie.append(e)
    return sortie


def supprimer_patient(numero, motif, precision="", utilisateur="médecin"):
    """Efface DÉFINITIVEMENT le patient : identité, réponses, suivi. Ne subsiste qu'une trace minimale dans le journal
    (numéro, date, motif, utilisateur) ; les anciennes entrées du journal sur ce patient sont vidées de leur contenu."""
    with connexion() as c:
        c.execute("DELETE FROM reponses WHERE numero=?", (numero,))
        c.execute("DELETE FROM participants WHERE numero=?", (numero,))
    with connexion_identites() as ci:
        ci.execute("DELETE FROM identites WHERE numero=?", (numero,))
        ci.execute("DELETE FROM suivi WHERE numero=?", (numero,))
        ci.execute("UPDATE journal SET details='{\"efface\": true}' WHERE numero=? AND details IS NOT NULL", (numero,))
    journaliser("Suppression du patient", numero, {"motif": motif, "precision": (precision or "").strip()}, utilisateur)
