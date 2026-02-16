from flask import Flask, render_template, request, redirect, url_for, Response
import os
import csv
from io import TextIOWrapper
from db import get_conn, placeholder, init_db, is_postgres

app = Flask(__name__)
init_db()

# ====== ADMIN (senha só para adicionar/importar) ======
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "1234")

def require_admin():
    auth = request.authorization
    if not auth or auth.username != ADMIN_USER or auth.password != ADMIN_PASS:
        return Response(
            "Auth required", 401,
            {"WWW-Authenticate": 'Basic realm="EasyCheck Admin"'}
        )
    return None

# ====== EXISTENTE ======
@app.route("/")
def home():
    return redirect(url_for("dashboard"))

def get_stats():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM convidados")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM convidados WHERE entrou='Sim'")
    entrou = cur.fetchone()[0]
    cur.close()
    conn.close()
    return {"total": total, "entrou": entrou, "faltam": total - entrou}

@app.route("/dashboard")
def dashboard():
    s = get_stats()
    return render_template("dashboard.html", stats=s)

@app.route("/protocolo", methods=["GET", "POST"])
def protocolo():
    resultados = []
    nome = ""
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()

        conn = get_conn()
        cur = conn.cursor()
        ph = placeholder()

        if is_postgres():
            cur.execute(
                f"SELECT id, nome, mesa, acompanhante, entrou FROM convidados "
                f"WHERE nome ILIKE {ph} ORDER BY nome ASC",
                ('%' + nome + '%',)
            )
        else:
            cur.execute(
                f"SELECT id, nome, mesa, acompanhante, entrou FROM convidados "
                f"WHERE nome LIKE {ph} ORDER BY nome ASC",
                ('%' + nome + '%',)
            )

        resultados = cur.fetchall()
        cur.close()
        conn.close()

    return render_template("protocolo.html", resultados=resultados, nome=nome)

@app.route("/scan/<int:id>")
def scan(id):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"SELECT id, nome, mesa, acompanhante, entrou FROM convidados WHERE id={ph}", (id,))
    c = cur.fetchone()
    cur.close()
    conn.close()
    return render_template("scan.html", convidado=c)

@app.route("/entrar/<int:id>")
def entrar(id):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"UPDATE convidados SET entrou='Sim' WHERE id={ph}", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("protocolo"))

@app.route("/resetar/<int:id>")
def resetar(id):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"UPDATE convidados SET entrou='Não' WHERE id={ph}", (id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("protocolo"))

# ====== ADMIN PAGE ======
MESAS = ["Laranja", "Manga", "Papaia", "Maracuja"]

@app.route("/admin", methods=["GET"])
def admin():
    r = require_admin()
    if r: return r
    return render_template("admin.html", mesas=MESAS)

@app.route("/admin/add", methods=["POST"])
def admin_add():
    r = require_admin()
    if r: return r

    nome = request.form.get("nome", "").strip()
    mesa = request.form.get("mesa", "").strip()
    acompanhante = request.form.get("acompanhante", "Não").strip()

    if not nome or mesa not in MESAS or acompanhante not in ["Sim", "Não"]:
        return "Dados inválidos.", 400

    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute(
            "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (%s, %s, %s, 'Não')",
            (nome, mesa, acompanhante)
        )
    else:
        cur.execute(
            "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (?, ?, ?, 'Não')",
            (nome, mesa, acompanhante)
        )

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("admin"))

@app.route("/admin/import", methods=["POST"])
def admin_import():
    r = require_admin()
    if r: return r

    f = request.files.get("arquivo")
    if not f or not f.filename.lower().endswith(".csv"):
        return "Envia um CSV (.csv).", 400

    # CSV com cabeçalho: nome,mesa,acompanhante
    stream = TextIOWrapper(f.stream, encoding="utf-8", newline="")
    reader = csv.DictReader(stream)

    to_insert = []
    for row in reader:
        nome = (row.get("nome") or "").strip()
        mesa = (row.get("mesa") or "").strip()
        acompanhante = (row.get("acompanhante") or "Não").strip()

        if not nome:
            continue
        if mesa not in MESAS:
            continue
        if acompanhante not in ["Sim", "Não"]:
            acompanhante = "Não"

        to_insert.append((nome, mesa, acompanhante, "Não"))

    if not to_insert:
        return "CSV vazio ou inválido.", 400

    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.executemany(
            "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (%s, %s, %s, %s)",
            to_insert
        )
    else:
        cur.executemany(
            "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (?, ?, ?, ?)",
            to_insert
        )

    conn.commit()
    cur.close()
    conn.close()
    return f"OK ✅ Importados: {len(to_insert)}", 200

@app.route("/seed-demo")
def seed_demo():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM convidados")
    if cur.fetchone()[0] == 0:
        dados = [
            ("Nazimo Nordine", "Laranja", "Sim", "Não"),
            ("Joana Gomes", "Maracuja", "Sim", "Não"),
            ("Yassira Nordine", "Maracuja", "Não", "Não"),
            ("Alysha Nordine", "Manga", "Sim", "Não"),
            ("Ana Nhantumbo", "Papaia", "Sim", "Não"),
        ]
        if is_postgres():
            cur.executemany(
                "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (%s, %s, %s, %s)",
                dados
            )
        else:
            cur.executemany(
                "INSERT INTO convidados (nome, mesa, acompanhante, entrou) VALUES (?, ?, ?, ?)",
                dados
            )
        conn.commit()
    cur.close()
    conn.close()
    return "OK ✅ seed feito (se estava vazio)."
