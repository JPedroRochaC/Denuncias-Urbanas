from flask import Flask, request, jsonify
from flask_cors import CORS
import pymysql
from pymysql import Error
from datetime import datetime

app = Flask(__name__)
CORS(app)

import os

DB_CONFIG = {
    "host":     os.environ.get("MYSQLHOST"),
    "user":     os.environ.get("MYSQLUSER"),
    "password": os.environ.get("MYSQLPASSWORD"),
    "database": os.environ.get("MYSQLDATABASE"),
    "port":     int(os.environ.get("MYSQLPORT", 3306))
}

def get_conn():
    return pymysql.connect(**DB_CONFIG)

def init_db():
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denuncias (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                tipo       ENUM('buraco','lixo','iluminacao','outro') NOT NULL,
                endereco   VARCHAR(255) NOT NULL,
                descricao  TEXT NOT NULL,
                status     ENUM('pendente','andamento','resolvido') DEFAULT 'pendente',
                criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Banco conectado e tabela pronta!")
    except Error as e:
        print(f"❌ Erro ao conectar no banco: {e}")

@app.route("/denuncias", methods=["GET"])
def listar():
    try:
        conn = get_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM denuncias ORDER BY criado_em DESC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        for r in rows:
            if isinstance(r["criado_em"], datetime):
                r["criado_em"] = r["criado_em"].strftime("%d/%m/%Y %H:%M")

        return jsonify(rows), 200
    except Error as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/denuncias", methods=["POST"])
def criar():
    data = request.get_json()

    tipo      = data.get("tipo", "").strip()
    endereco  = data.get("endereco", "").strip()
    descricao = data.get("descricao", "").strip()
    status    = data.get("status", "pendente").strip()

    if not tipo or not endereco or not descricao:
        return jsonify({"erro": "Campos tipo, endereco e descricao são obrigatórios"}), 400

    tipos_validos  = ["buraco", "lixo", "iluminacao", "outro"]
    status_validos = ["pendente", "andamento", "resolvido"]

    if tipo not in tipos_validos:
        return jsonify({"erro": "Tipo inválido"}), 400
    if status not in status_validos:
        return jsonify({"erro": "Status inválido"}), 400

    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO denuncias (tipo, endereco, descricao, status) VALUES (%s, %s, %s, %s)",
            (tipo, endereco, descricao, status)
        )
        conn.commit()
        novo_id = cursor.lastrowid
        cursor.close()
        conn.close()
        return jsonify({"id": novo_id, "mensagem": "Denúncia criada com sucesso"}), 201
    except Error as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/denuncias/<int:id>", methods=["DELETE"])
def excluir(id):
    try:
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM denuncias WHERE id = %s", (id,))
        conn.commit()
        afetados = cursor.rowcount
        cursor.close()
        conn.close()

        if afetados == 0:
            return jsonify({"erro": "Denúncia não encontrada"}), 404

        return "", 204
    except Error as e:
        return jsonify({"erro": str(e)}), 500

@app.route("/stats", methods=["GET"])
def stats():
    try:
        conn = get_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(status = 'pendente')  AS pendente,
                SUM(status = 'andamento') AS andamento,
                SUM(status = 'resolvido') AS resolvido
            FROM denuncias
        """)
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        return jsonify({
            "total":     int(row["total"]     or 0),
            "pendente":  int(row["pendente"]  or 0),
            "andamento": int(row["andamento"] or 0),
            "resolvido": int(row["resolvido"] or 0),
        }), 200
    except Error as e:
        return jsonify({"erro": str(e)}), 500

if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)