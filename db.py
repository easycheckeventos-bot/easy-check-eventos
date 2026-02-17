import os
import sqlite3
import psycopg2

SQLITE_NAME = "easycheck.db"

def is_postgres():
    return bool(os.environ.get("DATABASE_URL"))

def get_conn():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(db_url, sslmode="require")
    return sqlite3.connect(SQLITE_NAME)

def placeholder():
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
            acompanhantes INT NOT NULL DEFAULT 0,
            entrou TEXT NOT NULL DEFAULT 'Não'
        );
        """)
    else:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhantes INTEGER NOT NULL DEFAULT 0,
            entrou TEXT NOT NULL DEFAULT 'Não'
        );
        """)

    conn.commit()
    cur.close()
    conn.close()
