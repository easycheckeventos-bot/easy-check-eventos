import os
import sqlite3
from urllib.parse import urlparse

DATABASE_URL = os.environ.get("DATABASE_URL")  # Render Postgres
SQLITE_PATH = os.environ.get("SQLITE_PATH", "easycheck.db")


def is_postgres():
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))


def placeholder():
    return "%s" if is_postgres() else "?"


def get_conn():
    if is_postgres():
        import psycopg2
        return psycopg2.connect(DATABASE_URL)
    else:
        conn = sqlite3.connect(SQLITE_PATH)
        return conn


def ensure_schema():
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhantes INT NOT NULL DEFAULT 0,
            entrou TEXT NOT NULL DEFAULT 'Não',
            token TEXT
        );
        """)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_token ON convidados(token);")
    else:
        # SQLite
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhantes INTEGER NOT NULL DEFAULT 0,
            entrou TEXT NOT NULL DEFAULT 'Não',
            token TEXT
        );
        """)
        try:
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_token ON convidados(token);")
        except:
            pass

    conn.commit()
    cur.close()
    conn.close()
