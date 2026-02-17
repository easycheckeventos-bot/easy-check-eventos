from flask import Flask, render_template, request, redirect, url_for, Response
import os
import csv
from io import TextIOWrapper

from db import get_conn, placeholder, init_db, is_postgres

app = Flask(__name__)
init_db()

# =========================
# ADMIN (senha só para admin)
# =========================
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

# =========================
# HOME (Landing Page)
# =========================
@app.route("/")
def home():
    return render_template("home.html")

# =========================
# DASHBOARD (Convites x Pessoas)
# =========================
def get_stats():
    conn = get_conn()
    cur = conn.cursor()

    # Convites (convidados principais)
    cur.execute("SELECT COUNT(*) FROM convidados")
    convites = cur.fetchone()[0] or 0

    # Pessoas totais = soma(1 + acompanhantes)
    cur.execute("SELECT COALESCE(SUM(1 + acompanhantes), 0) FROM convidados")
    total_pessoas = cur.fetchone()[0] or 0

    # Pessoas que entraram
    cur.execute("SELECT COALESCE(SUM(1 + acompanhantes), 0) FROM convidados WHERE entrou='Sim'")
    entraram_pessoas = cur.fetchone()[0] or 0

    cur.close()
    conn.close()

    return {
        "convites": convites,
        "total_pessoas": total_pessoas,
        "entraram_pessoas": entraram_pessoas,
        "faltam_pessoas": total_pessoas - entraram_pessoas
    }

@app.route("/dashboard")
def dashboard():
    s = get_stats()
    return render_template("dashboard.html", stats=s)

# =========================
# PROTOCOLO (busca por nome)
# =========================
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
                f"SELECT id, nome, mesa, acompanhantes, entrou FROM convidados "
                f"WHERE nome ILIKE {ph} ORDER BY nome ASC",
                ('%' + nome + '%',)
            )
        else:
            cur.execute(
                f"SELECT id, nome, mesa, acompanhantes, entrou FROM convidados "
                f"WHERE nome LIKE {ph} ORDER BY nome ASC",
                ('%' + nome + '%',)
            )

        resultados = cur.fetchall()
        cur.close()
        conn.close()

    return render_template("protocolo.html", resultados=resultados, nome=nome)

# =========================
# SCAN (QR)
# =========================
@app.route("/scan/<int:id>")
def scan(id):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()

    cur.execute(
        f"SELECT id, nome, mesa, acompanhantes, entrou FROM convidados WHERE id={ph}",
        (id,)
    )
    c = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("scan.html", convidado=c)

# =========================
# MARCAR ENTRADA / RESETAR
# =========================
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

# =========================
# ADMIN (Adicionar + Importar CSV)
# =========================
@app.route("/admin", methods=["GET"])
def admin():
    r = require_admin()
    if r:
        return r
    return render_template("admin.html")

@app.route("/admin/add", methods=["POST"])
def admin_add():
    r = require_admin()
    if r:
        return r

    nome = request.form.get("nome", "").strip()
    mesa = request.form.get("mesa", "").strip()

    acompanhantes_raw = (request.form.get("acompanhantes") or "0").strip()
    try:
        acompanhantes = int(acompanhantes_raw)
    except:
        acompanhantes = 0

    if acompanhantes < 0:
        acompanhantes = 0
    if acompanhantes > 10:
        acompanhantes = 10

    if not nome or not mesa:
        return "Dados inválidos. Nome e Mesa são obrigatórios.", 400

    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.execute(
            "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (%s, %s, %s, 'Não')",
            (nome, mesa, acompanhantes)
        )
    else:
        cur.execute(
            "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (?, ?, ?, 'Não')",
            (nome, mesa, acompanhantes)
        )

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("admin"))

@app.route("/admin/import", methods=["POST"])
def admin_import():
    r = require_admin()
    if r:
        return r

    f = request.files.get("arquivo")
    if not f or not f.filename.lower().endswith(".csv"):
        return "Envia um CSV (.csv).", 400

    # CSV com cabeçalho: nome,mesa,acompanhantes
    stream = TextIOWrapper(f.stream, encoding="utf-8", newline="")
    reader = csv.DictReader(stream)

    to_insert = []
    for row in reader:
        nome = (row.get("nome") or "").strip()
        mesa = (row.get("mesa") or "").strip()

        acompanhantes_raw = (row.get("acompanhantes") or "0").strip()
        try:
            acompanhantes = int(acompanhantes_raw)
        except:
            acompanhantes = 0

        if acompanhantes < 0:
            acompanhantes = 0
        if acompanhantes > 10:
            acompanhantes = 10

        if not nome or not mesa:
            continue

        to_insert.append((nome, mesa, acompanhantes, "Não"))

    if not to_insert:
        return "CSV vazio ou inválido. Precisa ter: nome, mesa, acompanhantes.", 400

    conn = get_conn()
    cur = conn.cursor()

    if is_postgres():
        cur.executemany(
            "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (%s, %s, %s, %s)",
            to_insert
        )
    else:
        cur.executemany(
            "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (?, ?, ?, ?)",
            to_insert
        )

    conn.commit()
    cur.close()
    conn.close()

    return f"OK ✅ Importados: {len(to_insert)}", 200

# =========================
# SEED DEMO (só testes)
# =========================
@app.route("/seed-demo")
def seed_demo():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM convidados")
    if (cur.fetchone()[0] or 0) == 0:
        dados = [
            ("Nazimo Nordine", "Toyota", 1, "Não"),
            ("Joana Gomes", "BMW", 0, "Não"),
            ("Yassira Nordine", "Mercedes", 2, "Não"),
            ("Alysha Nordine", "Audi", 1, "Não"),
            ("Ana Nhantumbo", "Ford", 0, "Não"),
        ]

        if is_postgres():
            cur.executemany(
                "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (%s, %s, %s, %s)",
                dados
            )
        else:
            cur.executemany(
                "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (?, ?, ?, ?)",
                dados
            )

        conn.commit()

    cur.close()
    conn.close()
    return "OK ✅ seed feito (se estava vazio)."

@app.route("/admin/resetdb")
def resetdb():
    r = require_admin()
    if r:
        return r

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("DELETE FROM convidados")

    conn.commit()
    cur.close()
    conn.close()

    return "DB limpa ✅"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
