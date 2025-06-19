from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, abort, make_response
from models.db import crear_usuario, obtener_usuario_por_matricula, obtener_registros_filtrados, obtener_ultimo_registro, obtener_registros_filtrados, crear_registro, actualizar_salida, calcular_duracion, obtener_todos_miembros, eliminar_miembro_db, actualizar_miembro_db, obtener_registros_abiertos, contar_registros
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta
from math import ceil

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clave secreta para sesiones

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        matricula = request.form['matricula'].lower()
        nombre = request.form['nombre']
        password = request.form['password']

        # Validación en backend, excepción para 'karla'
        if matricula != "karla" and (not matricula.isdigit() or len(matricula) != 8):
            flash('Matrícula inválida. Debe tener 8 dígitos numéricos.', 'danger')
            return redirect(url_for('signup'))

        hash_pass = generate_password_hash(password)
        if crear_usuario(matricula, nombre, hash_pass):
            flash('Registro exitoso. Inicia sesión.', 'success')
            return redirect(url_for('login'))
        else:
            flash('La matrícula ya existe.', 'danger')
            return redirect(url_for('signup'))

    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        matricula = request.form['matricula'].lower()
        password = request.form['password']

        # Validación backend, excepción para 'karla'
        if matricula != "karla" and (not matricula.isdigit() or len(matricula) != 8):
            flash('Matrícula inválida.', 'danger')
            return redirect(url_for('login'))

        usuario = obtener_usuario_por_matricula(matricula)
        if usuario and check_password_hash(usuario['password'], password):
            session['usuario'] = usuario['matricula']
            session['es_admin'] = True if usuario['matricula'].lower() == 'karla' else False
            return redirect(url_for('dashboard'))

        flash('Credenciales incorrectas.', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # Si es administrador, redirigir al panel admin
    if session.get('es_admin', False):
        return redirect(url_for('admin_panel'))

    matricula = session['usuario']
    ultimo = obtener_ultimo_registro(matricula)

    # --- Aquí insertas el cierre automático ---
    if ultimo and ultimo['hora_entrada'] and ultimo['hora_salida'] is None:
        hora_entrada = datetime.fromisoformat(ultimo['hora_entrada'])
        ahora = datetime.now()
        if ahora - hora_entrada > timedelta(hours=3):
            actualizar_salida(ultimo['id'])
            # Actualiza el registro para reflejar la salida
            ultimo = obtener_ultimo_registro(matricula)
            flash('Tu sesión anterior fue cerrada automáticamente después de 3 horas.', 'info')
    # ------------------------------------------

    mensaje = ""
    puede_entrar = False
    puede_salir = False

    # Si no hay registro o el último registro ya tiene salida, puede checar entrada
    if not ultimo or ultimo['hora_salida'] is not None:
        puede_entrar = True
    # Si hay entrada pero no salida, puede checar salida
    elif ultimo['hora_entrada'] and ultimo['hora_salida'] is None:
        puede_salir = True

    if request.method == 'POST':
        accion = request.form['accion']

        if accion == 'entrada' and puede_entrar:
            crear_registro(matricula)
            mensaje = "Entrada registrada correctamente."
        elif accion == 'salida' and puede_salir:
            actualizar_salida(ultimo['id'])
            mensaje = "Salida registrada correctamente."
        else:
            mensaje = "Acción no válida."

        return redirect(url_for('dashboard'))

    return render_template('dashboard.html', 
                           matricula=matricula,
                           puede_entrar=puede_entrar,
                           puede_salir=puede_salir,
                           mensaje=mensaje)

@app.route('/admin')
def admin_panel():
    if 'usuario' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))

    cerrar_sesiones_abiertas_3_horas()

    matricula_filter = request.args.get('matricula')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    pagina = request.args.get('page', 1, type=int)
    registros_por_pagina = 20

    total_registros = contar_registros(matricula_filter, fecha_inicio, fecha_fin)
    registros = obtener_registros_filtrados(matricula_filter, fecha_inicio, fecha_fin, pagina, registros_por_pagina)

    registros_con_duracion = []
    for r in registros:
        duracion = calcular_duracion(r['hora_entrada'], r['hora_salida'])
        r_dict = dict(r)
        r_dict['duracion'] = duracion
        registros_con_duracion.append(r_dict)

    total_paginas = ceil(total_registros / registros_por_pagina)

    return render_template("admin.html",
                           registros=registros_con_duracion,
                           pagina=pagina,
                           total_paginas=total_paginas,
                           matricula_filter=matricula_filter or '',
                           fecha_inicio=fecha_inicio or '',
                           fecha_fin=fecha_fin or '')

@app.route('/exportar_excel')
def exportar_excel():
    if 'usuario' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))

    matricula_filter = request.args.get('matricula', '')
    fecha_inicio = request.args.get('fecha_inicio', '')
    fecha_fin = request.args.get('fecha_fin', '')

    registros = obtener_registros_filtrados(matricula_filter, fecha_inicio, fecha_fin)

    if not registros:
        return "No hay registros para exportar."

    df = pd.DataFrame(registros)

    if 'hora_entrada' in df.columns and 'hora_salida' in df.columns:
        df['hora_entrada'] = pd.to_datetime(df['hora_entrada'])
        df['hora_salida'] = pd.to_datetime(df['hora_salida'])
        df['duracion (hrs)'] = (df['hora_salida'] - df['hora_entrada']).dt.total_seconds() / 3600

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Registros')
    output.seek(0)

    return send_file(output, download_name="registros_vex.xlsx", as_attachment=True)


@app.route('/admin/miembros')
def listar_miembros():
    if 'usuario' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))
    usuarios = obtener_todos_miembros()  # Lo definimos en db.py
    return render_template('miembros.html', usuarios=usuarios)

# Ruta para crear miembro (GET muestra formulario, POST procesa)
@app.route('/admin/miembros/nuevo', methods=['GET', 'POST'])
def nuevo_miembro():
    if 'usuario' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))

    if request.method == 'POST':
        matricula = request.form['matricula']
        nombre = request.form['nombre']
        password = request.form['password']
        hash_pass = generate_password_hash(password)
        if crear_usuario(matricula, nombre, hash_pass):
            flash('Miembro creado con éxito', 'success')
            return redirect(url_for('listar_miembros'))
        else:
            flash('Matrícula ya existe', 'danger')

    return render_template('nuevo_miembro.html')

@app.route('/editar_miembro/<matricula>', methods=['GET', 'POST'])
def editar_miembro(matricula):
    if 'usuario' not in session or not session.get('es_admin'):
        return redirect(url_for('login'))

    # Para mostrar los datos actuales
    usuario = obtener_usuario_por_matricula(matricula)
    if not usuario:
        flash('Miembro no encontrado', 'danger')
        return redirect(url_for('listar_miembros'))

    if request.method == 'POST':
        nombre = request.form['nombre']
        password = request.form['password'].strip()
        password = password if password else None

        actualizar_miembro_db(matricula, nombre, password)
        flash('Miembro actualizado correctamente', 'success')
        return redirect(url_for('listar_miembros'))

    return render_template('editar_miembro.html', usuario=usuario)

# Ruta para eliminar miembro
@app.route('/eliminar_miembro/<matricula>', methods=['POST'])
def eliminar_miembro(matricula):
    eliminar_miembro_db(matricula)  # Llama a la función de la capa de datos
    flash("Miembro eliminado correctamente", "success")
    return redirect(url_for('listar_miembros'))

def cerrar_sesiones_abiertas_3_horas():
    registros_abiertos = obtener_registros_abiertos()
    ahora = datetime.now()

    for registro in registros_abiertos:
        hora_entrada = registro['hora_entrada']

        # Convertir string a datetime de forma segura
        if isinstance(hora_entrada, str):
            try:
                hora_entrada = datetime.fromisoformat(hora_entrada)
            except ValueError:
                flash(f"Error al convertir hora: {hora_entrada}", "danger")
                continue

        # Si han pasado más de 3 horas, se cierra la sesión
        if ahora - hora_entrada > timedelta(hours=3):
            actualizar_salida(registro['id'])






@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)


