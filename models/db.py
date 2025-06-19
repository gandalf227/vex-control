import sqlite3
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database.db')

def conectar():
    return sqlite3.connect(DB_PATH)

def crear_tablas():
    with conectar() as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS miembros (
                matricula TEXT PRIMARY KEY,
                nombre TEXT,
                password TEXT
            )
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                matricula TEXT,
                hora_entrada DATETIME,
                hora_salida DATETIME
            )
        ''')
        conn.commit()


def crear_usuario(matricula, nombre, password_hash):
    try:
        with conectar() as conn:
            c = conn.cursor()
            c.execute("INSERT INTO miembros (matricula, nombre, password) VALUES (?, ?, ?)",
                      (matricula, nombre, password_hash))
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False

def obtener_usuario_por_matricula(matricula):
    with conectar() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM miembros WHERE matricula = ?", (matricula,))
        return c.fetchone()
    


def obtener_ultimo_registro(matricula):
    with conectar() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('''
            SELECT * FROM registros 
            WHERE matricula = ? 
            ORDER BY id DESC LIMIT 1
        ''', (matricula,))
        return c.fetchone()




def obtener_registros_filtrados(matricula=None, fecha_inicio=None, fecha_fin=None, pagina=1, registros_por_pagina=20):
    query = "SELECT * FROM registros WHERE 1=1"
    params = []

    if matricula:
        query += " AND matricula = ?"
        params.append(matricula)

    if fecha_inicio:
        query += " AND hora_entrada >= ?"
        params.append(fecha_inicio)

    if fecha_fin:
        query += " AND hora_salida <= ?"
        params.append(fecha_fin)

    query += " ORDER BY hora_entrada DESC"

    offset = (pagina - 1) * registros_por_pagina
    query += " LIMIT ? OFFSET ?"
    params.extend([registros_por_pagina, offset])

    with conectar() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, params)
        return c.fetchall()

def contar_registros(matricula=None, fecha_inicio=None, fecha_fin=None):
    query = "SELECT COUNT(*) FROM registros WHERE 1=1"
    params = []

    if matricula:
        query += " AND matricula = ?"
        params.append(matricula)

    if fecha_inicio:
        query += " AND hora_entrada >= ?"
        params.append(fecha_inicio)

    if fecha_fin:
        query += " AND hora_salida <= ?"
        params.append(fecha_fin)

    with conectar() as conn:
        c = conn.cursor()
        c.execute(query, params)
        total = c.fetchone()[0]
    return total


    
def obtener_ultimo_registro(matricula):
    query = '''
    SELECT * FROM registros 
    WHERE matricula = ? 
    ORDER BY id DESC 
    LIMIT 1
    '''
    with conectar() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(query, (matricula,))
        return c.fetchone()
        
def crear_registro(matricula):
    with conectar() as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO registros (matricula, hora_entrada, hora_salida)
            VALUES (?, ?, NULL)
        ''', (matricula, datetime.now()))
        conn.commit()

def crear_registro(matricula):
    with conectar() as conn:
        c = conn.cursor()
        c.execute('INSERT INTO registros (matricula, hora_entrada) VALUES (?, ?)', 
                  (matricula, datetime.now()))
        conn.commit()

def actualizar_salida(registro_id):
    with conectar() as conn:
        c = conn.cursor()
        c.execute('''
            UPDATE registros SET hora_salida = ?
            WHERE id = ?
        ''', (datetime.now(), registro_id))
        conn.commit()

def actualizar_salida(registro_id):
    with conectar() as conn:
        c = conn.cursor()
        c.execute('UPDATE registros SET hora_salida = ? WHERE id = ?', 
                (datetime.now(), registro_id))
        conn.commit()

def calcular_duracion(entrada, salida):
    if entrada and salida:
        e = datetime.fromisoformat(entrada)
        s = datetime.fromisoformat(salida)
        duracion = s - e
        # Retornar solo horas con dos decimales
        return round(duracion.total_seconds() / 3600, 2)
    return 0

def obtener_todos_miembros():
    with conectar() as conn:
        c = conn.cursor()
        c.execute("SELECT matricula, nombre FROM miembros")
        miembros = c.fetchall()
    return miembros

def actualizar_miembro_db(matricula, nombre, password=None):
    with conectar() as conn:
        c = conn.cursor()
        if password:
            hash_pass = generate_password_hash(password)
            c.execute("UPDATE miembros SET nombre = ?, password = ? WHERE matricula = ?", 
                      (nombre, hash_pass, matricula))
        else:
            c.execute("UPDATE miembros SET nombre = ? WHERE matricula = ?", 
                      (nombre, matricula))
        conn.commit()

def eliminar_miembro_db(matricula):
    with conectar() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM miembros WHERE matricula = ?", (matricula,))
        conn.commit()

def obtener_registros_abiertos():
    with conectar() as conn:
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute("SELECT * FROM registros WHERE hora_salida IS NULL")
        resultados = c.fetchall()
    return resultados
