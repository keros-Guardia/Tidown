#!/usr/bin/env python3
"""
Script de migration de la base de données.
Gère les deux cas :
  1. Nouvelle installation → crée les tables via SQLAlchemy
  2. Base existante (sans colonnes lastfm_api_key) → ajoute les colonnes manquantes
"""
import sqlite3
import asyncio
import sys
from database import init_db


SQLITE_DB = "musicapp.db"

MIGRATIONS = [
    # (description, SQL)
    ("Ajout lastfm_api_key",    "ALTER TABLE users ADD COLUMN lastfm_api_key TEXT"),
    ("Ajout lastfm_api_secret", "ALTER TABLE users ADD COLUMN lastfm_api_secret TEXT"),
]


def migrate_existing_db():
    """Applique les migrations sur une base existante."""
    conn = sqlite3.connect(SQLITE_DB)
    cur = conn.cursor()

    # Récupère les colonnes existantes
    cur.execute("PRAGMA table_info(users)")
    existing_cols = {row[1] for row in cur.fetchall()}

    applied = 0
    for desc, sql in MIGRATIONS:
        col_name = sql.split("ADD COLUMN")[1].strip().split()[0]
        if col_name not in existing_cols:
            print(f"  → {desc}...")
            try:
                cur.execute(sql)
                applied += 1
            except sqlite3.OperationalError as e:
                print(f"    ⚠ Ignoré : {e}")

    conn.commit()
    conn.close()
    return applied


async def main():
    import os
    if os.path.exists(SQLITE_DB):
        print(f"Base existante trouvée : {SQLITE_DB}")
        n = migrate_existing_db()
        print(f"Migration terminée — {n} colonne(s) ajoutée(s).")
    else:
        print("Nouvelle installation — création des tables...")
        await init_db()
        print("Tables créées.")


if __name__ == "__main__":
    asyncio.run(main())
