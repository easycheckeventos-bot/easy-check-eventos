import os
import sqlite3
import qrcode

from PIL import Image, ImageDraw, ImageFont

DB_NAME = "easycheck.db"

# 🔥 LINK ONLINE (Render)
BASE_URL = "https://easy-check-eventos.onrender.com"

OUT_DIR = "static/qrcodes"
os.makedirs(OUT_DIR, exist_ok=True)

def carregar_fonte(size=22):
    caminhos = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in caminhos:
        try:
            return ImageFont.truetype(p, size=size)
        except:
            pass
    return ImageFont.load_default()

def criar_qr_nome(link, nome, out_path):

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3
    )
    qr.add_data(link)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    font = carregar_fonte(24)

    padding = 20
    base_w = qr_img.size[0] + padding*2
    base_h = qr_img.size[1] + 90

    base = Image.new("RGB", (base_w, base_h), "white")
    draw = ImageDraw.Draw(base)

    # cola QR
    qr_x = (base_w - qr_img.size[0]) // 2
    base.paste(qr_img, (qr_x, 10))

    # escreve nome
    w = draw.textlength(nome, font=font)
    draw.text(((base_w - w)/2, qr_img.size[1] + 30),
              nome,
              fill="black",
              font=font)

    base.save(out_path, "PNG")

def main():

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute("SELECT id, nome FROM convidados ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    for cid, nome in rows:

        link = f"{BASE_URL}/scan/{cid}"
        out = os.path.join(OUT_DIR, f"convidado_{cid}.png")

        criar_qr_nome(link, nome, out)

        print("QR criado:", out)

    print("✅ TODOS GERADOS")

if __name__ == "__main__":
    main()
