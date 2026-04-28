# IMPORTAÇÕES DAS BIBLIOTECAS
from flask import Flask, request, jsonify  # Flask (API), request (dados recebidos), jsonify (respostas em JSON)
from flask_cors import CORS                # Libera acesso do front-end (CORS)
import pymysql                             # Conexão com MySQL
from pymysql import Error                  # Tratamento de erros do banco
from datetime import datetime, timezone, timedelta  # Manipulação de datas
import os                                  # Variáveis de ambiente (deploy)

# CRIAÇÃO DO APP FLASK
app = Flask(__name__)
CORS(app)  # Permite requisições de outros domínios (ex: HTML separado)

# CONFIGURAÇÃO DO BANCO DE DADOS (via variáveis de ambiente)
DB_CONFIG = {
    "host":     os.environ.get("MYSQLHOST"),       # Host do banco
    "user":     os.environ.get("MYSQLUSER"),       # Usuário
    "password": os.environ.get("MYSQLPASSWORD"),   # Senha
    "database": os.environ.get("MYSQLDATABASE"),   # Nome do banco
    "port":     int(os.environ.get("MYSQLPORT", 3306))  # Porta padrão 3306
}

# FUNÇÃO PARA CONECTAR NO BANCO
def get_conn():
    return pymysql.connect(**DB_CONFIG)

# FUNÇÃO PARA CRIAR A TABELA (SE NÃO EXISTIR)
def init_db():
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Cria a tabela denuncias
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS denuncias (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                tipo       ENUM('buraco','lixo','iluminacao','outro') NOT NULL,
                endereco   VARCHAR(255) NOT NULL,
                descricao  TEXT NOT NULL,
                status     ENUM('pendente','andamento','resolvido') DEFAULT 'pendente',
                criado_em  DATETIME DEFAULT CURRENT_TIMESTAMP,
                criado_por VARCHAR(100) DEFAULT 'anonimo'
            )
        """)

        # Tenta adicionar a coluna criado_por caso não exista (para bancos antigos)
        try:
            cursor.execute("ALTER TABLE denuncias ADD COLUMN criado_por VARCHAR(100) DEFAULT 'anonimo'")
        except Error:
            pass  # Se já existir, ignora

        conn.commit()
        cursor.close()
        conn.close()
        print("Banco conectado e tabela pronta!")

    except Error as e:
        print(f"Erro ao conectar no banco: {e}")

# ROTA GET → LISTAR TODAS AS DENÚNCIAS
@app.route("/denuncias", methods=["GET"])
def listar():
    try:
        conn = get_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)  # Retorna como dicionário

        # Busca todas as denúncias ordenadas pela mais recente
        cursor.execute("SELECT * FROM denuncias ORDER BY criado_em DESC")
        rows = cursor.fetchall()

        cursor.close()
        conn.close()

        # Ajusta dados antes de enviar pro front
        for r in rows:
            # Converte data para horário do Brasil
            if isinstance(r["criado_em"], datetime):
               fuso_brasil = timezone(timedelta(hours=-3))
               r["criado_em"] = r["criado_em"].replace(tzinfo=timezone.utc).astimezone(fuso_brasil).strftime("%d/%m/%Y %H:%M")

            # Garante que criado_por nunca seja vazio
            if not r.get("criado_por"):
                r["criado_por"] = "anonimo"

        return jsonify(rows), 200

    except Error as e:
        return jsonify({"erro": str(e)}), 500

# ROTA POST → CRIAR NOVA DENÚNCIA
@app.route("/denuncias", methods=["POST"])
def criar():
    data = request.get_json()  # Pega JSON enviado pelo front

    # Pega os dados e limpa espaços
    tipo       = data.get("tipo", "").strip()
    endereco   = data.get("endereco", "").strip()
    descricao  = data.get("descricao", "").strip()
    status     = data.get("status", "pendente").strip()
    criado_por = data.get("criado_por", "anonimo").strip() or "anonimo"

    # Validação de campos obrigatórios
    if not tipo or not endereco or not descricao:
        return jsonify({"erro": "Campos tipo, endereco e descricao são obrigatórios"}), 400

    # Valores permitidos
    tipos_validos  = ["buraco", "lixo", "iluminacao", "outro"]
    status_validos = ["pendente", "andamento", "resolvido"]

    # Validação de dados
    if tipo not in tipos_validos:
        return jsonify({"erro": "Tipo inválido"}), 400
    if status not in status_validos:
        return jsonify({"erro": "Status inválido"}), 400

    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Insere no banco
        cursor.execute(
            "INSERT INTO denuncias (tipo, endereco, descricao, status, criado_por) VALUES (%s, %s, %s, %s, %s)",
            (tipo, endereco, descricao, status, criado_por)
        )

        conn.commit()
        novo_id = cursor.lastrowid  # ID gerado

        cursor.close()
        conn.close()

        return jsonify({"id": novo_id, "mensagem": "Denúncia criada com sucesso"}), 201

    except Error as e:
        return jsonify({"erro": str(e)}), 500

# ROTA DELETE → EXCLUIR DENÚNCIA
@app.route("/denuncias/<int:id>", methods=["DELETE"])
def excluir(id):
    try:
        conn = get_conn()
        cursor = conn.cursor()

        # Deleta pelo ID
        cursor.execute("DELETE FROM denuncias WHERE id = %s", (id,))
        conn.commit()

        afetados = cursor.rowcount  # Quantas linhas foram afetadas

        cursor.close()
        conn.close()

        # Se não encontrou o ID
        if afetados == 0:
            return jsonify({"erro": "Denúncia não encontrada"}), 404

        return "", 204  # Sucesso sem conteúdo

    except Error as e:
        return jsonify({"erro": str(e)}), 500

# ROTA GET → ESTATÍSTICAS
@app.route("/stats", methods=["GET"])
def stats():
    try:
        conn = get_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Conta total e por status
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

        # Retorna os números (garantindo que não seja None)
        return jsonify({
            "total":     int(row["total"]     or 0),
            "pendente":  int(row["pendente"]  or 0),
            "andamento": int(row["andamento"] or 0),
            "resolvido": int(row["resolvido"] or 0),
        }), 200

    except Error as e:
        return jsonify({"erro": str(e)}), 500

# INÍCIO DO SERVIDOR
if __name__ == "__main__":
    init_db()  # Garante que o banco/tabela existam
    app.run(debug=True, port=5000)  # Roda o servidor na porta 5000