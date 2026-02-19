import os, re, secrets, io, zipfile
from flask import Flask, request, redirect, url_for, render_template, session, send_file, abort, flash

from db import get_conn, ensure_schema, dict_cursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

MASTER_PIN = os.environ.get("MASTER_PIN", "1234")

def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = re.sub(r"^-+|-+$", "", s)
    return s or "evento"

def require_master():
    if session.get("master_ok"):
        return None
    pin = request.args.get("pin") or request.form.get("pin")
    if pin and pin == MASTER_PIN:
        session["master_ok"] = True
        return None
    return redirect(url_for("master_login", next=request.path))

def get_event_by_slug(slug: str):
    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT * FROM eventos WHERE slug=%s;", (slug,))
    ev = cur.fetchone()
    cur.close(); conn.close()
    return ev

def require_event_admin(ev):
    key = f"admin_ok:{ev['slug']}"
    if session.get(key):
        return None
    pin = request.args.get("pin") or request.form.get("pin")
    if pin and pin == ev["pin_admin"]:
        session[key] = True
        return None
    return redirect(url_for("event_admin_login", slug=ev["slug"], next=request.path))

def gen_token():
    return secrets.token_urlsafe(16)

# --------- BOOT ---------
ensure_schema()

# --------- HOME (empresa) ---------
@app.route("/")
def home():
    return render_template("home.html")

# --------- MASTER LOGIN (painel interno) ---------
@app.route("/login", methods=["GET","POST"])
def master_login():
    if request.method == "POST":
        pin = request.form.get("pin","")
        if pin == MASTER_PIN:
            session["master_ok"] = True
            nxt = request.args.get("next") or url_for("panel")
            return redirect(nxt)
        flash("PIN inválido.")
    return render_template("master_login.html")

# --------- PANEL: criar/listar eventos ---------
@app.route("/panel", methods=["GET","POST"])
def panel():
    r = require_master()
    if r: return r

    if request.method == "POST":
        nome = request.form.get("nome_evento","").strip()
        slug = request.form.get("slug","").strip()
        pin_admin = request.form.get("pin_admin","").strip()

        if not nome:
            flash("Nome do evento é obrigatório.")
            return redirect(url_for("panel"))
        if not slug:
            slug = slugify(nome)
        else:
            slug = slugify(slug)
        if not pin_admin or len(pin_admin) < 4:
            flash("PIN do Admin do evento deve ter pelo menos 4 dígitos.")
            return redirect(url_for("panel"))

        conn = get_conn()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO eventos (nome_evento, slug, pin_admin) VALUES (%s,%s,%s) RETURNING id;",
                        (nome, slug, pin_admin))
            ev_id = cur.fetchone()[0]
            conn.commit()
        except Exception as e:
            conn.rollback()
            flash(f"Erro ao criar evento: {e}")
        finally:
            cur.close(); conn.close()

        return redirect(url_for("panel"))

    conn = get_conn()
    cur = dict_cursor(conn)
    cur.execute("SELECT id, nome_evento, slug, created_at FROM eventos ORDER BY created_at DESC;")
    eventos = cur.fetchall()
    cur.close(); conn.close()

    return render_template("panel.html", eventos=eventos)

# --------- EVENT: redirect base ---------
@app.route("/e/<slug>")
def event_root(slug):
    ev = get_event_by_slug(slug)
    if not ev:
        return "Evento não encontrado.", 404
    return redirect(url_for("protocolo", slug=slug))

# --------- PROTOCOLO ---------
@app.route("/e/<slug>/protocolo", methods=["GET","POST"])
def protocolo(slug):
    ev = get_event_by_slug(slug)
    if not ev:
        return "Evento não encontrado.", 404

    q = (request.form.get("q") if request.method=="POST" else request.args.get("q")) or ""
    q = q.strip()

    page = int(request.args.get("page", 1))
    per_page = 40
    offset = (page-1)*per_page

    conn = get_conn()
    cur = dict_cursor(conn)

    if q:
        cur.execute("""
            SELECT COUNT(*) AS n FROM convidados
            WHERE evento_id=%s AND nome ILIKE %s
        """, (ev["id"], f"%{q}%"))
        total = cur.fetchone()["n"]

        cur.execute("""
            SELECT id, nome, mesa, acompanhantes, entrou
            FROM convidados
            WHERE evento_id=%s AND nome ILIKE %s
            ORDER BY nome ASC
            LIMIT %s OFFSET %s
        """, (ev["id"], f"%{q}%", per_page, offset))
    else:
        cur.execute("SELECT COUNT(*) AS n FROM convidados WHERE evento_id=%s;", (ev["id"],))
        total = cur.fetchone()["n"]
        cur.execute("""
            SELECT id, nome, mesa, acompanhantes, entrou
            FROM convidados
            WHERE evento_id=%s
            ORDER BY nome ASC
            LIMIT %s OFFSET %s
        """, (ev["id"], per_page, offset))

    rows = cur.fetchall()
    cur.close(); conn.close()

    pages = max(1, (total + per_page - 1)//per_page)

    # calcula total pessoas = 1 + acompanhantes
    for r in rows:
        r["total_pessoas"] = 1 + int(r.get("acompanhantes") or 0)

    return render_template("protocolo.html", ev=ev, rows=rows, q=q, page=page, pages=pages, total=total)

# --------- DASHBOARD ---------
@app.route("/e/<slug>/dashboard")
def dashboard(slug):
    ev = get_event_by_slug(slug)
    if not ev:
        return "Evento não encontrado.", 404

    conn = get_conn()
    cur = dict_cursor(conn)

    cur.execute("SELECT COUNT(*) AS n FROM convidados WHERE evento_id=%s;", (ev["id"],))
    convites = cur.fetchone()["n"]

    cur.execute("SELECT COALESCE(SUM(1),0) AS n FROM convidados WHERE evento_id=%s;", (ev["id"],))
    convidados_principais = cur.fetchone()["n"]

    cur.execute("SELECT COALESCE(SUM(1 + acompanhantes),0) AS n FROM convidados WHERE evento_id=%s;", (ev["id"],))
    pessoas_total = cur.fetchone()["n"]

    cur.execute("SELECT COALESCE(SUM(1 + acompanhantes),0) AS n FROM convidados WHERE evento_id=%s AND entrou='Sim';", (ev["id"],))
    pessoas_entraram = cur.fetchone()["n"]

    cur.execute("SELECT COALESCE(SUM(1 + acompanhantes),0) AS n FROM convidados WHERE evento_id=%s AND entrou!='Sim';", (ev["id"],))
    pessoas_faltam = cur.fetchone()["n"]

    cur.close(); conn.close()

    stats = {
        "convites": convites,
        "convidados_principais": convidados_principais,
        "pessoas_total": pessoas_total,
        "pessoas_entraram": pessoas_entraram,
        "pessoas_faltam": pessoas_faltam
    }
    return render_template("dashboard.html", ev=ev, stats=stats)

# --------- EVENT ADMIN LOGIN ---------
@app.route("/e/<slug>/admin-login", methods=["GET","POST"])
def event_admin_login(slug):
    ev = get_event_by_slug(slug)
    if not ev:
        return "Evento não encontrado.", 404

    if request.method == "POST":
        pin = request.form.get("pin","")
        if pin == ev["pin_admin"]:
            session[f"admin_ok:{slug}"] = True
            nxt = request.args.get("next") or url_for("event_admin", slug=slug)
            return redirect(nxt)
        flash("PIN inválido.")

    return render_template("event_admin_login.html", ev=ev)

# --------- EVENT ADMIN (por enquanto simples) ---------
@app.route("/e/<slug>/admin")
def event_admin(slug):
    ev = get_event_by_slug(slug)
    if not ev:
        return "Evento não encontrado.", 404

    r = require_event_admin(ev)
    if r: return r

    return render_template("admin.html", ev=ev)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)