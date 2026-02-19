import sqlite3

conn = sqlite3.connect("easycheck.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS convidados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT,
    mesa TEXT,
    acompanhante TEXT,
    entrou TEXT
)
""")

cursor.execute("DELETE FROM convidados")

dados = [
    ("Nazimo Nordine", "Laranja", "Sim", "Não"),
    ("Joana Gomes", "Maracuja", "Sim", "Não"),
    ("Yassira Nordine", "Maracuja", "Não", "Não"),
    ("Alysha Nordine", "Manga", "Sim", "Não"),
    ("Ana Nhantumbo", "Papaia", "Sim", "Não"),
]

cursor.executemany(
    "INSERT INTO convidados (nome, mesa, acompanhantes, entrou) VALUES (?, ?, ?, ?)",
    dados
)

conn.commit()
conn.close()

print("Base criada ✅")
