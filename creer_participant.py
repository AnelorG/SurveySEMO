"""
Script à lancer dans Spyder (touche F5) pour créer les participants autorisés.
Modifiez la liste ci-dessous : (numéro de randomisation, date de naissance).
"""
from datetime import date
import db

PARTICIPANTS = [
    ("P001", date(1980, 5, 17)),
    ("P002", date(1992, 11, 3)),
]
# Pour débloquer un participant après 5 échecs : db.debloquer("P001")

db.init_db()
for numero, naissance in PARTICIPANTS:
    db.creer_participant(numero, naissance)
    print("Participant créé :", numero)
