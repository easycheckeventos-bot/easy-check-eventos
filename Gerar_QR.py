import os
import sqlite3
import qrcode

from PIL import Image, ImageDraw, ImageFont

DB_NAME = "easycheck.db"

# ✅ Troca pelo teu IP do PC
PC_IP = "192.168.1.23"
PORTA = 5000
BASE_URL = f"http://{PC_IP}:{PORTA}"

OUT_DIR = "static/qrcodes"
os.makedirs(OUT_DIR, exist_ok=True)

def carregar_fonte(size=22):
    # tenta fontes comuns do Windows; se falhar, usa fonte padrão do Pillow
    caminhos = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
    ]
    for p in caminhos:
        try:
            return ImageFont.truetype(p, size=size)
        except Exception:
            pass
    return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    # quebra linha para caber no max_width
    words = text.split()
    lines, line = [], ""
    for w in words:
        test = (line + " " + w).strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines

def criar_qr_com_legenda(link, legenda_topo, legenda_baixo, out_path):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=3
    )
    qr.add_data(link)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # base branca com espaço para texto
    padding = 22
    font_top = carregar_fonte(22)
    font_bottom = carregar_fonte(20)

    draw_tmp = ImageDraw.Draw(Image.new("RGB", (1, 1), "white"))
    max_w = qr_img.size[0] + padding * 2

    topo_lines = wrap_text(draw_tmp, legenda_topo, font_top, max_w - 20)
    baixo_lines = wrap_text(draw_tmp, legenda_baixo, font_bottom, max_w - 20)

    # calcula altura do texto
    line_h_top = int(font_top.size * 1.35)
    line_h_bottom = int(font_bottom.size * 1.35)

    text_h = (len(topo_lines) * line_h_top) + (len(baixo_lines) * line_h_bottom) + 18
    base_w = max_w
    base_h = qr_img.size[1] + padding * 2 + text_h

    base = Image.new("RGB", (base_w, base_h), "white")
    draw = ImageDraw.Draw(base)

    # cola QR no centro
    qr_x = (base_w - qr_img.size[0]) // 2
    qr_y = padding
    base.paste(qr_img, (qr_x, qr_y))

    # escreve texto centrado abaixo do QR
    y = qr_y + qr_img.size[1] + 14

    for line in topo_lines:
        w = draw.textlength(line, font=font_top)
        draw.text(((base_w - w) / 2, y), line, fill="black", font=font_top)
        y += line_h_top

    y += 4

    for line in baixo_lines:
        w = draw.textlength(line, font=font_bottom)
        draw.text(((base_w - w) / 2, y), line, fill="black", font=font_bottom)
        y += line_h_bottom

    base.save(out_path, "PNG")

def main():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT id, nome, mesa FROM convidados ORDER BY id ASC")
    rows = cur.fetchall()
    conn.close()

    for cid, nome, mesa in rows:
        link = f"{BASE_URL}/scan/{cid}"
        # topo e baixo (tu podes ajustar o texto)
        topo = nome
        baixo = f"Mesa: {mesa}"
        out = os.path.join(OUT_DIR, f"convidado_{cid}.png")

        criar_qr_com_legenda(link, topo, baixo, out)
        print("✅ QR:", out, "->", link)

    print(f"✅ Tudo pronto. PNGs em: {OUT_DIR}")

if __name__ == "__main__":
    main()
