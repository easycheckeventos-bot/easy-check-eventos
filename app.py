import os
import math
import re
import secrets
import zipfile
from io import BytesIO
from datetime import datetime

from flask import (
    Flask, request, render_template, redirect, url_for,
    session, send_file, flash
)

import qrcode

from db import get_conn, is_postgres, placeholder, ensure_schema


app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")


# =========================
# Config
# =========================
ADMIN_PIN = os.environ.get("ADMIN_PIN", "1234")   # no Render mete variável ADMIN_PIN
PER_PAGE = 40


# =========================
# Helpers
# =========================
def require_admin():
    """Protege rotas admin via session."""
    if session.get("is_admin"):
        return None
    return redirect(url_for("admin_login", next=request.path))


def new_token():
    return secrets.token_urlsafe(16)


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def ensure_guest_token(conn, guest_id: int) -> str:
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"SELECT token FROM convidados WHERE id={ph}", (guest_id,))
    row = cur.fetchone()
    token = row[0] if row else None

    if not token:
        token = new_token()
        cur.execute(f"UPDATE convidados SET token={ph} WHERE id={ph}", (token, guest_id))
        conn.commit()

    cur.close()
    return token


def fetchone_dict(cur):
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    if not row:
        return None
    return dict(zip(cols, row))


def fetchall_dicts(cur):
    cols = [d[0] for d in cur.description]
    rows = cur.fetchall()
    return [dict(zip(cols, r)) for r in rows]


# =========================
# Home
# =========================
@app.route("/")
def home():
    return render_template("home.html")


# =========================
# Admin auth (PIN)
# =========================
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    next_url = request.args.get("next") or url_for("admin")

    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        if pin == ADMIN_PIN:
            session["is_admin"] = True
            return redirect(next_url)
        flash("PIN incorreto.")
        return redirect(url_for("admin_login", next=next_url))

    return render_template("admin_login.html", next_url=next_url)


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("home"))


# =========================
# Admin panel + CSV import
# =========================
@app.route("/admin")
def admin():
    r = require_admin()
    if r:
        return r

    return render_template("admin.html")


@app.route("/admin/import-csv", methods=["POST"])
def admin_import_csv():
    r = require_admin()
    if r:
        return r

    file = request.files.get("file")
    if not file:
        flash("Nenhum ficheiro enviado.")
        return redirect(url_for("admin"))

    raw = file.read().decode("utf-8", errors="ignore")
    lines = [l for l in raw.splitlines() if l.strip()]

    # CSV simples: nome,mesa,acompanhantes
    # Cabeçalho obrigatório (nome, mesa, acompanhantes)
    import csv
    reader = csv.DictReader(lines)

    needed = {"nome", "mesa", "acompanhantes"}
    if not reader.fieldnames or not needed.issubset(set([h.strip().lower() for h in reader.fieldnames])):
        flash("CSV inválido. Precisa de colunas: nome, mesa, acompanhantes")
        return redirect(url_for("admin"))

    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()

    inserted = 0
    updated = 0

    for row in reader:
        nome = normalize_spaces(row.get("nome"))
        mesa = normalize_spaces(row.get("mesa"))
        acompanhantes_raw = (row.get("acompanhantes") or "0").strip()

        if not nome or not mesa:
            continue

        try:
            acompanhantes = int(acompanhantes_raw)
        except:
            acompanhantes = 0

        acompanhantes = max(0, min(10, acompanhantes))

        # Regra: se já existe o mesmo nome, atualiza mesa/acompanhantes (padrão simples)
        if is_postgres():
            cur.execute(
                f"SELECT id FROM convidados WHERE nome={ph} LIMIT 1",
                (nome,)
            )
        else:
            cur.execute(
                f"SELECT id FROM convidados WHERE nome={ph} LIMIT 1",
                (nome,)
            )
        existing = cur.fetchone()

        if existing:
            gid = existing[0]
            cur.execute(
                f"UPDATE convidados SET mesa={ph}, acompanhantes={ph} WHERE id={ph}",
                (mesa, acompanhantes, gid)
            )
            updated += 1
            ensure_guest_token(conn, gid)
        else:
            # inserir novo
            if is_postgres():
                cur.execute(
                    f"INSERT INTO convidados (nome, mesa, acompanhantes, entrou, token) "
                    f"VALUES ({ph},{ph},{ph},'Não',{ph}) RETURNING id",
                    (nome, mesa, acompanhantes, new_token())
                )
                gid = cur.fetchone()[0]
            else:
                cur.execute(
                    f"INSERT INTO convidados (nome, mesa, acompanhantes, entrou, token) "
                    f"VALUES ({ph},{ph},{ph},'Não',{ph})",
                    (nome, mesa, acompanhantes, new_token())
                )
                gid = cur.lastrowid

            inserted += 1

    conn.commit()
    cur.close()
    conn.close()

    flash(f"Importado ✅ {inserted} novos | {updated} atualizados")
    return redirect(url_for("admin"))


@app.route("/admin/reset-entrada", methods=["POST"])
def admin_reset_entrada():
    r = require_admin()
    if r:
        return r

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE convidados SET entrou='Não'")
    conn.commit()
    cur.close()
    conn.close()

    flash("Entradas resetadas ✅")
    return redirect(url_for("admin"))


# =========================
# Dashboard
# =========================
@app.route("/dashboard")
def dashboard():
    conn = get_conn()
    cur = conn.cursor()

    # total convites (convidados principais)
    cur.execute("SELECT COUNT(*) FROM convidados")
    convites = cur.fetchone()[0] or 0

    # total pessoas = convidados + acompanhantes
    if is_postgres():
        cur.execute("SELECT COALESCE(SUM(acompanhantes),0) FROM convidados")
    else:
        cur.execute("SELECT COALESCE(SUM(acompanhantes),0) FROM convidados")
    soma_acomp = cur.fetchone()[0] or 0
    total_pessoas = convites + soma_acomp

    # entraram (pessoas)
    cur.execute("SELECT COUNT(*) FROM convidados WHERE entrou='Sim'")
    convites_entraram = cur.fetchone()[0] or 0

    if is_postgres():
        cur.execute("SELECT COALESCE(SUM(acompanhantes),0) FROM convidados WHERE entrou='Sim'")
    else:
        cur.execute("SELECT COALESCE(SUM(acompanhantes),0) FROM convidados WHERE entrou='Sim'")
    acomp_entraram = cur.fetchone()[0] or 0

    pessoas_entraram = convites_entraram + acomp_entraram
    faltam = max(0, total_pessoas - pessoas_entraram)

    cur.close()
    conn.close()

    stats = {
        "convites": convites,
        "total_pessoas": total_pessoas,
        "entraram": pessoas_entraram,
        "faltam": faltam
    }
    return render_template("dashboard.html", stats=stats)


# =========================
# Protocolo (busca + paginação)
# =========================
@app.route("/protocolo", methods=["GET"])
def protocolo():
    q = normalize_spaces(request.args.get("q"))
    page_raw = request.args.get("page") or "1"
    try:
        page = max(1, int(page_raw))
    except:
        page = 1

    offset = (page - 1) * PER_PAGE
    ph = placeholder()

    conn = get_conn()
    cur = conn.cursor()

    # total
    if q:
        if is_postgres():
            cur.execute(f"SELECT COUNT(*) FROM convidados WHERE nome ILIKE {ph}", (f"%{q}%",))
        else:
            cur.execute(f"SELECT COUNT(*) FROM convidados WHERE nome LIKE {ph}", (f"%{q}%",))
    else:
        cur.execute("SELECT COUNT(*) FROM convidados")

    total = cur.fetchone()[0] or 0
    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page > total_pages:
        page = total_pages
        offset = (page - 1) * PER_PAGE

    # lista
    if q:
        if is_postgres():
            cur.execute(
                f"""SELECT id, nome, mesa, acompanhantes, entrou
                    FROM convidados
                    WHERE nome ILIKE {ph}
                    ORDER BY nome ASC
                    LIMIT {ph} OFFSET {ph}""",
                (f"%{q}%", PER_PAGE, offset),
            )
        else:
            cur.execute(
                f"""SELECT id, nome, mesa, acompanhantes, entrou
                    FROM convidados
                    WHERE nome LIKE {ph}
                    ORDER BY nome ASC
                    LIMIT {ph} OFFSET {ph}""",
                (f"%{q}%", PER_PAGE, offset),
            )
    else:
        cur.execute(
            f"""SELECT id, nome, mesa, acompanhantes, entrou
                FROM convidados
                ORDER BY nome ASC
                LIMIT {ph} OFFSET {ph}""",
            (PER_PAGE, offset),
        )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    convidados = [{
        "id": r[0],
        "nome": r[1],
        "mesa": r[2],
        "acompanhantes": int(r[3] or 0),
        "entrou": r[4],
    } for r in rows]

    return render_template(
        "protocolo.html",
        convidados=convidados,
        q=q,
        page=page,
        total_pages=total_pages,
        total=total
    )


@app.route("/entrar/<int:gid>")
def marcar_entrada(gid):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"UPDATE convidados SET entrou='Sim' WHERE id={ph}", (gid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("protocolo"))


@app.route("/reset/<int:gid>")
def resetar_entrada(gid):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"UPDATE convidados SET entrou='Não' WHERE id={ph}", (gid,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for("protocolo"))


# =========================
# QR (PNG) + Ver QR + ZIP
# =========================
@app.route("/qr/<int:guest_id>.png")
def qr_png(guest_id):
    conn = get_conn()
    token = ensure_guest_token(conn, guest_id)
    conn.close()

    base = request.url_root.rstrip("/")
    link = f"{base}/scan/{token}"

    img = qrcode.make(link)
    bio = BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)

    return send_file(
        bio,
        mimetype="image/png",
        download_name=f"qr_{guest_id}.png"
    )


@app.route("/qr/<int:guest_id>")
def qr_view(guest_id):
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()
    cur.execute(f"SELECT id, nome, mesa, acompanhantes, entrou, token FROM convidados WHERE id={ph}", (guest_id,))
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return "Convidado não encontrado", 404

    # garante token
    token = row[5] or ensure_guest_token(conn, guest_id)
    conn.commit()

    guest = {
        "id": row[0],
        "nome": row[1],
        "mesa": row[2],
        "acompanhantes": int(row[3] or 0),
        "entrou": row[4],
        "token": token
    }
    guest["total"] = 1 + guest["acompanhantes"]

    cur.close()
    conn.close()
    return render_template("qr_view.html", c=guest)


@app.route("/qr/zip")
def qr_zip():
    r = require_admin()
    if r:
        return r

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nome FROM convidados ORDER BY nome ASC")
    rows = cur.fetchall()

    # cria zip em memória
    mem = BytesIO()
    zf = zipfile.ZipFile(mem, mode="w", compression=zipfile.ZIP_DEFLATED)

    base = request.url_root.rstrip("/")
    for (gid, nome) in rows:
        token = ensure_guest_token(conn, gid)
        link = f"{base}/scan/{token}"
        img = qrcode.make(link)

        bio = BytesIO()
        img.save(bio, format="PNG")
        bio.seek(0)

        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", nome.strip())[:60] or f"guest_{gid}"
        zf.writestr(f"{safe_name}_{gid}.png", bio.read())

    zf.close()
    mem.seek(0)

    cur.close()
    conn.close()

    return send_file(
        mem,
        mimetype="application/zip",
        download_name=f"qrcodes_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
        as_attachment=True
    )


# =========================
# Scan (token) -> confirmar -> marcar entrada
# =========================
@app.route("/scan/<token>")
def scan_token(token):
    token = (token or "").strip()
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()

    cur.execute(
        f"SELECT id, nome, mesa, acompanhantes, entrou FROM convidados WHERE token={ph} LIMIT 1",
        (token,)
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    if not row:
        return render_template("scan_invalid.html"), 404

    c = {
        "id": row[0],
        "nome": row[1],
        "mesa": row[2],
        "acompanhantes": int(row[3] or 0),
        "entrou": row[4],
        "total": 1 + int(row[3] or 0),
        "token": token
    }
    return render_template("scan_confirm.html", c=c)


@app.route("/scan/<token>/confirm", methods=["POST"])
def scan_confirm(token):
    token = (token or "").strip()
    conn = get_conn()
    cur = conn.cursor()
    ph = placeholder()

    # se já entrou, não muda (mas retornamos estado)
    cur.execute(
        f"SELECT id, nome, mesa, acompanhantes, entrou FROM convidados WHERE token={ph} LIMIT 1",
        (token,)
    )
    row = cur.fetchone()
    if not row:
        cur.close()
        conn.close()
        return render_template("scan_invalid.html"), 404

    already = (row[4] == "Sim")

    if not already:
        cur.execute(
            f"UPDATE convidados SET entrou='Sim' WHERE token={ph}",
            (token,)
        )
        conn.commit()

    cur.close()
    conn.close()

    c = {
        "id": row[0],
        "nome": row[1],
        "mesa": row[2],
        "acompanhantes": int(row[3] or 0),
        "entrou": "Sim",
        "total": 1 + int(row[3] or 0),
        "token": token
    }
    return render_template("scan_result.html", c=c, already=already)


# =========================
# Startup: garante schema
# =========================
ensure_schema()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
