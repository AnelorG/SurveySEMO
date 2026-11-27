"""
Réglages de l'application.

SÉCURITÉ : l'identifiant et le mot de passe de l'espace investigateur ne sont PLUS écrits dans le code.
Ils sont lus, dans cet ordre, dans :
  1. des variables d'environnement (serveur UGA : à définir dans la configuration du service) ;
  2. les « secrets » Streamlit : fichier .streamlit/secrets.toml (en local ou sur le serveur) ou, sur Streamlit Cloud,
     Settings > Secrets. Ce fichier ne doit JAMAIS être versionné (il figure dans .gitignore).
Noms attendus :  ADMIN_LOGIN  et  ADMIN_MOT_DE_PASSE_HASH  (empreinte à générer avec : python generer_hash_mdp.py).
(ADMIN_MOT_DE_PASSE, en clair, est encore accepté mais déconseillé.)
Si rien n'est configuré, l'accès investigateur est FERMÉ (aucun identifiant par défaut).
"""
import hashlib
import hmac
import os

# Les participants peuvent-ils repasser le questionnaire (en entier ou certaines parties) après l'avoir terminé ?
# Leurs réponses précédentes sont toujours conservées (chaque remplissage = un « passage » numéroté).
AUTORISER_REPASSAGE = True


def _secret(nom):
    v = os.environ.get(nom)
    if v:
        return v
    try:
        import streamlit as st
        v = st.secrets.get(nom)
        return str(v) if v else None
    except Exception:
        return None


def hacher_mot_de_passe(mdp, sel=None, iterations=600_000):
    """Empreinte PBKDF2-SHA256 salée : « pbkdf2_sha256$itérations$sel$empreinte »."""
    sel = sel or os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", mdp.encode(), sel, iterations)
    return f"pbkdf2_sha256${iterations}${sel.hex()}${h.hex()}"


def _verifier_hash(mdp, enregistre):
    try:
        _algo, it, sel, h = enregistre.split("$")
        calc = hashlib.pbkdf2_hmac("sha256", mdp.encode(), bytes.fromhex(sel), int(it))
        return hmac.compare_digest(calc.hex(), h)
    except Exception:
        return False


def acces_investigateur_configure():
    return bool(_secret("ADMIN_LOGIN")) and bool(_secret("ADMIN_MOT_DE_PASSE_HASH") or _secret("ADMIN_MOT_DE_PASSE"))


def verifier_investigateur(identifiant, mdp):
    login, h, clair = _secret("ADMIN_LOGIN"), _secret("ADMIN_MOT_DE_PASSE_HASH"), _secret("ADMIN_MOT_DE_PASSE")
    if not login or not (h or clair):
        return False
    bon_id = hmac.compare_digest(identifiant.strip().encode(), login.encode())
    bon_mdp = _verifier_hash(mdp, h) if h else hmac.compare_digest(mdp.encode(), clair.encode())
    return bon_id and bon_mdp
