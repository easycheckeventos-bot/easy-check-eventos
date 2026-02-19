import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

def is_postgres():
    return os.environ.get("DATABASE_URL", "").startswith("postgres")

def placeholder():
    # SQLite usa "?" e Postgres (psycopg2) usa "%s"
    return "%s" if is_postgres() else "?"

def get_conn():
    url = os.environ.get("DATABASE_URL")
    if url and url.startswith("postgres"):
        return psycopg2.connect(url)
    return sqlite3.connect("easycheck.db")

def ensure_schema():
    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        # 1) cria tabela se não existir
        cur.execute("""
        CREATE TABLE IF NOT EXISTS convidados (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            mesa TEXT NOT NULL,
            acompanhantes INT NOT NULL DEFAULT 0,
            entrou TEXT NOT NULL DEFAULT 'Não'
        );
        """)

        # 2) MIGRAÇÕES: adiciona colunas se faltarem (não dá erro se já existir)
        cur.execute("ALTER TABLE convidados ADD COLUMN IF NOT EXISTS token TEXT;")
        cur.execute("ALTER TABLE convidados ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();")

        # 3) índice único do token (só faz sentido depois da coluna existir)
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_token ON convidados(token);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_convidados_nome ON convidados(nome);")

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
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_convidados_token ON convidados(token);")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_convidados_nome ON convidados(nome);")

    conn.commit()
    cur.close()
    conn.close()
