from flask import Flask, render_template, request, redirect, url_for
from db import get_conn, placeholder, init_db, is_postgres

app = Flask(__name__)
init_db()

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
        cur.execute(
            f"SELECT id, nome, mesa, acompanhante, entrou FROM convidados "
            f"WHERE nome ILIKE {ph} ORDER BY nome ASC" if is_postgres() else
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
