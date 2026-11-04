"""
Réinitialise la base de données. À lancer dans Anaconda Prompt, depuis le dossier du projet :

    python reinitialiser_base.py reponses      -> efface toutes les réponses (patients conservés)
    python reinitialiser_base.py patient P012  -> efface les réponses d'UN patient
    python reinitialiser_base.py tout          -> REMISE À ZÉRO COMPLÈTE : patients, identités, réponses, suivi,
                                                  journal d'audit et numéros réservés (base vierge, avant mise en production)

(Sans argument, le script vous pose la question.) Une copie de sauvegarde est créée avant toute suppression :
SUPPRIMEZ-LA ensuite si elle contient des données fictives, et ne la copiez jamais sur le serveur.
Vous n'avez pas besoin d'arrêter l'application Streamlit.
"""
import os
import shutil
import sys
from datetime import datetime

os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())
import db


def compter():
    with db.connexion() as c, db.connexion_identites() as ci:
        return dict(patients=c.execute("SELECT COUNT(*) FROM participants").fetchone()[0],
                    reponses=c.execute("SELECT COUNT(*) FROM reponses").fetchone()[0],
                    identites=ci.execute("SELECT COUNT(*) FROM identites").fetchone()[0],
                    suivi=ci.execute("SELECT COUNT(*) FROM suivi").fetchone()[0],
                    journal=ci.execute("SELECT COUNT(*) FROM journal").fetchone()[0])


def reinitialiser(mode, numero=None, confirmer=True):
    db.init_db()
    if mode not in ("reponses", "patient", "tout") or (mode == "patient" and not numero):
        print(__doc__)
        return False
    print("Avant :", compter())
    if confirmer and input(f"Mode « {mode} »{' ' + numero if numero else ''} : action irréversible. Tapez OUI pour confirmer : ").strip() != "OUI":
        print("Annulé, rien n'a été supprimé.")
        return False
    sauvegarde = f"sauvegarde_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy(db.DB_PATH, sauvegarde)
    shutil.copy(db.IDENTITES_PATH, sauvegarde.replace(".db", "_identites.db"))
    print("Sauvegarde créée :", sauvegarde, "(+ _identites) — à supprimer si elle contient des données fictives")
    with db.connexion() as c:
        if mode == "reponses":
            c.execute("DELETE FROM reponses")
            c.execute("UPDATE participants SET tentatives=0")
        elif mode == "patient":
            c.execute("DELETE FROM reponses WHERE numero=?", (db.normaliser_numero(numero),))
            c.execute("UPDATE participants SET tentatives=0 WHERE numero=?", (db.normaliser_numero(numero),))
        else:
            c.execute("DELETE FROM reponses")
            c.execute("DELETE FROM participants")
            c.execute("DELETE FROM meta")
    if mode == "tout":
        with db.connexion_identites() as ci:
            for table in ("identites", "suivi", "journal"):
                ci.execute(f"DELETE FROM {table}")
            ci.execute("DELETE FROM sqlite_sequence")
    print("Après :", compter())
    return True


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        argv = [input("Mode (reponses / patient / tout) : ").strip()]
        if argv[0] == "patient":
            argv.append(input("Numéro du patient : ").strip())
    reinitialiser(argv[0], argv[1] if len(argv) > 1 else None)
