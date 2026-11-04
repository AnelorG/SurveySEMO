"""Exporte toutes les réponses dans export_reponses.csv (1 ligne par participant et par passage). Lancer avec F5."""
import sqlite3
import pandas as pd
import db

with sqlite3.connect(db.DB_PATH) as c:
    df = pd.read_sql_query("SELECT numero, passage, question_id, valeur FROM reponses", c)
large = df.pivot(index=["numero", "passage"], columns="question_id", values="valeur")
large.to_csv("export_reponses.csv", sep=";", encoding="utf-8-sig")
print("Export terminé :", large.shape[0], "ligne(s) (participant x passage)")
