from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

DB_NAME = "easycheck.db"

def conectar():
    return sqlite3.connect(DB_NAME)

def stats():
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM convidados")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM convidados WHERE entrou='Sim'")
    entrou = cur.fetchone()[0]
    conn.close()
    return {"total": total, "entrou": entrou, "faltam": total - entrou}

@app.route("/")
def home():
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
def dashboard():
    s = stats()
    return render_template("dashboard.html", stats=s)

@app.route("/protocolo", methods=["GET", "POST"])
def protocolo():
    resultados = []
    nome = ""
    if request.method == "POST":
        nome = request.form.get("nome", "").strip()
        conn = conectar()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nome, mesa, acompanhante, entrou FROM convidados "
            "WHERE nome LIKE ? ORDER BY nome ASC",
            ('%' + nome + '%',)
        )
        resultados = cur.fetchall()
        conn.close()

    return render_template("protocolo.html", resultados=resultados, nome=nome)

@app.route("/scan/<int:id>")
def scan(id):
    # Tela VIP: verde/vermelha + dados
    conn = conectar()
    cur = conn.cursor()
    cur.execute("SELECT id, nome, mesa, acompanhante, entrou FROM convidados WHERE id=?", (id,))
    c = cur.fetchone()
    conn.close()
    return render_template("scan.html", convidado=c)

@app.route("/entrar/<int:id>")
def entrar(id):
    # marca entrada (se já entrou, mantém)
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE convidados SET entrou='Sim' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("protocolo"))

@app.route("/resetar/<int:id>")
def resetar(id):
    # caso precise desfazer
    conn = conectar()
    cur = conn.cursor()
    cur.execute("UPDATE convidados SET entrou='Não' WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("protocolo"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
