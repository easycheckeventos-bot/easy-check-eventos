import os
import sqlite3
import psycopg2
from urllib.parse import urlparse

SQLITE_NAME = "easycheck.db"

def is_postgres():
    return bool(os.environ.get("DATABASE_URL"))

def get_conn():
    """
    - Se DATABASE_URL existir -> Postgres (Render)
    - Senão -> SQLite (PC)
    """
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        # Render às vezes usa postgres://, psycopg2 aceita, mas vamos normalizar
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(db_url, sslmode="require")
    else:
        return sqlite3.connect(SQLITE_NAME)

def placeholder():
    # Postgres usa %s, SQLite usa ?
    return "%s" if is_postgres() else "?"

def init_db():
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhante TEXT NOT NULL,
            entrou TEXT NOT NULL DEFAULT 'Não'
        );
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhante TEXT NOT NULL,
            entrou TEXT NOT NULL DEFAULT 'Não'
        );
        """)
    conn.commit()
    cur.close()
    conn.close()
