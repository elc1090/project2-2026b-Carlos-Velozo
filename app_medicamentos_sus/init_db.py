import sqlite3
import json
import csv
import os
import unicodedata

def remover_acentos(texto):
    if not texto:
        return ""
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().strip()

def init_database():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Recria as tabelas
    cursor.execute('DROP TABLE IF EXISTS medicamentos')
    cursor.execute('DROP TABLE IF EXISTS farmacias')
    
    cursor.execute('''
        CREATE TABLE farmacias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            endereco TEXT NOT NULL,
            lat REAL NOT NULL,
            lng REAL NOT NULL,
            imagem TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE medicamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            nome_busca TEXT NOT NULL,
            farmacia_nome TEXT NOT NULL,
            FOREIGN KEY (farmacia_nome) REFERENCES farmacias (nome),
            UNIQUE(nome, farmacia_nome)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS historico_buscas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            termo_busca TEXT NOT NULL,
            data_hora DATETIME DEFAULT CURRENT_TIMESTAMP,
            lat_usuario REAL,
            lng_usuario REAL
        )
    ''')

    # Popula Farmácias a partir do JSON
    farmacias_json = []
    if os.path.exists('enderecos.json'):
        with open('enderecos.json', 'r', encoding='utf-8') as f:
            enderecos = json.load(f)
            for nome_farmacia, info in enderecos.items():
                nome_limpo = nome_farmacia.strip()
                farmacias_json.append(nome_limpo)
                cursor.execute('''
                    INSERT INTO farmacias (nome, endereco, lat, lng, imagem)
                    VALUES (?, ?, ?, ?, ?)
                ''', (
                    nome_limpo,
                    info['endereco'].strip(),
                    info['marker'][0],
                    info['marker'][1],
                    info.get('imagem', '')
                ))

    # Categorização dinâmica das farmácias lidas do JSON
    farmacias_distritais = [nome for nome in farmacias_json if 'distrital' in remover_acentos(nome)]
    farmacias_municipais = [nome for nome in farmacias_json if 'municipal' in remover_acentos(nome) or 'central' in remover_acentos(nome)]
    farmacias_especiais = [nome for nome in farmacias_json if 'especia' in remover_acentos(nome)]

    # Popula Medicamentos a partir do CSV cruzando com as farmácias do JSON
    if os.path.exists('Medicamentos - unificado.csv'):
        with open('Medicamentos - unificado.csv', 'r', encoding='utf-8-sig') as f:
            sample = f.read(2048)
            f.seek(0)
            delimiter = ';' if ';' in sample else ','
            reader = csv.DictReader(f, delimiter=delimiter)
            
            count = 0
            for row in reader:
                med = row.get('MEDICAMENTO', '').strip()
                if not med:
                    continue

                item = row.get('ITEM', '').strip()
                local_disp = row.get('LOCAL_DE_DISPENSACAO', '').strip()

                # Medicamentos Especiais (linhas sem ITEM e sem LOCAL_DE_DISPENSACAO)
                if not item and not local_disp:
                    for farm_nome in farmacias_especiais:
                        cursor.execute('INSERT OR IGNORE INTO medicamentos (nome, nome_busca, farmacia_nome) VALUES (?, ?, ?)',
                                       (med, remover_acentos(med), farm_nome))
                        if cursor.rowcount > 0:
                            count += 1
                else:
                    # Farmácia Municipal
                    if row.get('MUNICIPAL') in ['1', '1.0']:
                        for farm_nome in farmacias_municipais:
                            cursor.execute('INSERT OR IGNORE INTO medicamentos (nome, nome_busca, farmacia_nome) VALUES (?, ?, ?)',
                                           (med, remover_acentos(med), farm_nome))
                            if cursor.rowcount > 0:
                                count += 1

                    # Farmácias Distritais gerais
                    if row.get('DISTRITAIS') in ['1', '1.0'] or row.get('FARMÁCIAS DISTRITAIS') in ['1', '1.0']:
                        for farm_nome in farmacias_distritais:
                            cursor.execute('INSERT OR IGNORE INTO medicamentos (nome, nome_busca, farmacia_nome) VALUES (?, ?, ?)',
                                           (med, remover_acentos(med), farm_nome))
                            if cursor.rowcount > 0:
                                count += 1
                    else:
                        # Busca por colunas específicas
                        for col_name, val in row.items():
                            if val in ['1', '1.0'] and col_name not in ['ITEM', 'DISTRITAIS', 'FARMÁCIAS DISTRITAIS', 'MUNICIPAL', 'POPULAR', 'UBS']:
                                col_norm = remover_acentos(col_name)
                                for farm_nome in farmacias_json:
                                    if col_norm in remover_acentos(farm_nome):
                                        cursor.execute('INSERT OR IGNORE INTO medicamentos (nome, nome_busca, farmacia_nome) VALUES (?, ?, ?)',
                                                       (med, remover_acentos(med), farm_nome))
                                        if cursor.rowcount > 0:
                                            count += 1

    conn.commit()
    conn.close()
    print(f"Sucesso! {count} relações de medicamentos cadastrados dinamicamente.")

if __name__ == '__main__':
    init_database()