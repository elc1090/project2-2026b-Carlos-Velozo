from flask import Flask, render_template, request, jsonify
import sqlite3
import unicodedata

app = Flask(__name__)

def remover_acentos(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()


#  GET: Consulta farmácias onde o medicamento está disponível
@app.route('/api/buscar', methods=['GET'])
def buscar():
    query = request.args.get('medicamento', '').strip()
    if not query:
        return jsonify([])

    query_norm = remover_acentos(query)
    conn = get_db()
    sql = '''
        SELECT DISTINCT f.nome, f.endereco, f.lat, f.lng, f.imagem, m.nome as medicamento
        FROM farmacias f
        JOIN medicamentos m ON LOWER(f.nome) = LOWER(m.farmacia_nome)
        WHERE m.nome_busca LIKE ?
    '''
    rows = conn.execute(sql, (f'%{query_norm}%',)).fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])

#  GET: Retorna lista de sugestões de nomes de remédios para o autocomplete
@app.route('/api/sugestoes', methods=['GET'])
def sugestoes():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    query_norm = remover_acentos(query)
    conn = get_db()
    rows = conn.execute('''
        SELECT DISTINCT nome FROM medicamentos 
        WHERE nome_busca LIKE ? LIMIT 8
    ''', (f'%{query_norm}%',)).fetchall()
    conn.close()

    return jsonify([r['nome'] for r in rows])

def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return render_template('index.html')

# POST: Salva a pesquisa do usuário para persistência
@app.route('/api/historico', methods=['POST'])
def salvar_historico():
    data = request.get_json() or {}
    termo = data.get('termo', '').strip()
    lat = data.get('lat')
    lng = data.get('lng')

    if not termo:
        return jsonify({'error': 'Termo de busca vazio'}), 400

    conn = get_db()
    conn.execute('''
        INSERT INTO historico_buscas (termo_busca, lat_usuario, lng_usuario)
        VALUES (?, ?, ?)
    ''', (termo, lat, lng))
    conn.commit()
    conn.close()

    return jsonify({'status': 'sucesso', 'mensagem': 'Busca registrada no histórico'})

#  GET: Retorna o histórico recente de pesquisas
@app.route('/api/historico', methods=['GET'])
def obter_historico():
    conn = get_db()
    rows = conn.execute('''
        SELECT termo_busca, data_hora FROM historico_buscas
        ORDER BY id DESC LIMIT 5
    ''').fetchall()
    conn.close()

    return jsonify([dict(r) for r in rows])

if __name__ == '__main__':
    app.run(debug=True, port=5000)