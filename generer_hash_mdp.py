"""
Génère l'empreinte du mot de passe de l'espace investigateur (le mot de passe lui-même n'est jamais enregistré).
    python generer_hash_mdp.py
Recopiez ensuite la ligne affichée dans .streamlit/secrets.toml (ou Streamlit Cloud > Settings > Secrets, ou une variable d'environnement).
"""
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

mdp = getpass.getpass("Nouveau mot de passe (12 caractères minimum) : ")
if len(mdp) < 12:
    sys.exit("Trop court : choisissez au moins 12 caractères.")
if mdp != getpass.getpass("Confirmez le mot de passe : "):
    sys.exit("Les deux saisies sont différentes.")
print('\nÀ placer dans .streamlit/secrets.toml (en plus de ADMIN_LOGIN = "votre_identifiant") :\n')
print(f'ADMIN_MOT_DE_PASSE_HASH = "{config.hacher_mot_de_passe(mdp)}"')
