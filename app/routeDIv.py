from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, jsonify, send_from_directory, session
from app import app  # Asegúrate de que 'app' se importa correctamente
import pyodbc
from datetime import datetime
from app.Python.json_handler import conectar_db, obtener_nombres_json, subir_json, obtener_id_usuario_por_correo  # "."
from app.Python.validations import validar_excel_con_cerberus  # "."
from app.Python.json_handler import obtener_fechas_json  # "."
import shutil
import os
from ldap3 import Server, Connection, ALL
import smtplib
from app.Python.config import Config  # "."
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd, json, time, os, re
import traceback
from app.Python.json_routes import json_routes  # Cambiado a importación absoluta
from app import routeDIv  #  Importa routeDIv.py
import json
import glob
from flask_sqlalchemy import SQLAlchemy





# Determina la ruta base (la carpeta donde se encuentra este archivo)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Define las carpetas relativas para guardar archivos
UPLOAD_FOLDER = os.path.join(BASE_DIR, "Plantillas", "Entrada")
VALIDATED_FOLDER = os.path.join(BASE_DIR, "Plantillas", "Validados")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "Plantillas", "Salida")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(VALIDATED_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configuración de carpetas
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['VALIDATED_FOLDER'] = VALIDATED_FOLDER


# Registrar blueprint
app.register_blueprint(json_routes)

app.config['SQLALCHEMY_DATABASE_URI'] = Config.get_sqlalchemy_uri()
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class ExpresionRegular(db.Model):
    __tablename__ = 'ExpresionesRegulares'
    id_ExpresionRegular = db.Column(db.Integer, primary_key=True)
    nombre_ExpresionRegular = db.Column(db.String(100), nullable=False)
    descripcion_ExpresionRegular = db.Column(db.String(255))
    expresion_Regular = db.Column(db.String(255), nullable=False)
    estado_ExpresionRegular = db.Column(db.String(10), default='Activo')
    tipoDato = db.Column(db.String(20))

# Función para enviar reportes de errores por correo
def enviar_reporte_errores(errores, destinatario, asunto="Reporte de Errores en Validación de Excel"):
    smtp_server = "smtp.office365.com"
    smtp_port = 587
    smtp_user = "notificacionessii@urosario.edu.co"
    smtp_password = "30dQ0dIQDJ4L3rzpACBO*"  # En producción, usar variables de entorno

    msg = MIMEMultipart()
    msg["From"] = smtp_user
    msg["To"] = ",".join(destinatario)
    msg["Subject"] = asunto

    html = [
        "<html>",
        "<body style='font-size:12px;'>",  # Cambia el tamaño de la letra aquí
        "<div style='text-align: center;'>",  # Centrar todo el contenido
        f"<h2>{asunto}</h2>",
        "<img src='https://urosario.edu.co/sites/default/files/2025-04/logo_vertical_ur_rojo.png' alt='Universidad del Rosario' style='height: 80px; margin-bottom: 10px;'>",
        "<table border='1' style='border-collapse: collapse; margin: 0 auto;'>",
        "<tr><th>hoja</th><th>fila</th><th>Error</th></tr>"
    ]
    for error in errores:
        hoja = error.get('hoja', 'N/A')
        fila = error.get('fila', 'N/A')
        error_desc = error.get('errores', 'N/A')
        html.append(f"<tr><td>{hoja}</td><td>{fila}</td><td>{error_desc}</td></tr>")

    html.extend(["</table>", "</div>", "</body>", "</html>"])  # Cerrar el div de centrado
    html_content = "".join(html)
    msg.attach(MIMEText(html_content, "html", "utf-8")) # Especificar utf-8

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.sendmail(smtp_user, destinatario, msg.as_string())
        server.quit()
        print("Correo enviado exitosamente")
    except Exception as e:
        print(f"Error al enviar el correo: {str(e)}")

# Función para obtener parámetros de la BD
def get_db_parameters():
    try:
        conn = conectar_db()
        if not conn:
            print("Error: No se pudo establecer conexión con la base de datos.")
            return None

        cursor = conn.cursor()
        cursor.execute("SELECT nombreParametro, valorParametro FROM dbo.Parametros")
        params = {row.nombreParametro: row.valorParametro for row in cursor.fetchall()}
        conn.close()
        print("Parámetros obtenidos de la base de datos:", params)
        return params
    except Exception as e:
        print(f"Error al obtener parámetros de la base de datos: {e}")
        return None

# Función para autenticar con LDAP
def ldap_authenticate(email, password):
    # Obtiene los parámetros desde la base de datos
    params = get_db_parameters()
    if not params:
        print("Error: No se pudieron obtener los parámetros de la base de datos.")
        return False

    # Extrae los parámetros necesarios
    server_address = params.get("server_address")
    admin_user = params.get("admin_user")
    admin_pass = params.get("admin_pass")
    search_base = params.get("search_base")

    # Verifica que todos los parámetros estén presentes
    if not all([server_address, admin_user, admin_pass, search_base]):
        print("Error: Faltan parámetros en la base de datos.")
        return False

    try:
        # Conexión al servidor LDAP
        print(f"Conectando al servidor LDAP: {server_address}")
        server = Server(server_address, port=389, get_info=ALL)
        conn = Connection(server, user=email, password=password, auto_bind=True)  # Autenticación del usuario
        print(f"Autenticación exitosa para el usuario: {email}")

        username = email.split("@")[0]
        conn_admin = Connection(server, user=admin_user, password=admin_pass, auto_bind=True)
        print(f"Conexión como administrador exitosa: {admin_user}")

        search_filter = f"(&(objectClass=user)(sAMAccountName={username}))"
        attributes = ["ou", "sn", "givenname", "mail", "extensionattribute8", "postofficebox",
                      "extensionattribute4", "info", "title", "department"]

        # Realiza la búsqueda en el directorio activo
        conn_admin.search(search_base, search_filter, attributes=attributes)
        print(f"Búsqueda LDAP realizada con éxito para el usuario: {username}")

        # Devuelve True si se encontraron entradas, False en caso contrario
        return bool(conn_admin.entries)

    except Exception as e:
        print(f"Error en autenticación LDAP: {e}")
        return False

# Rutas de la aplicación
@app.route('/paginaInicial')
def index_page():
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def inicio_sesion():
    print(f"Request method: {request.method}")  # Depuración
    if request.method == 'GET':
        session.pop('_flashes', None)  # Limpia mensajes flash antiguos
        return render_template('inicioSesion.html')


    if request.method == 'POST':
        # Obtiene las credenciales del formulario
        email = request.form.get('email')
        password = request.form.get('password')

        # Verifica las credenciales con LDAP
        if ldap_authenticate(email, password):
            session['user'] = email
            rol = obtener_rol_usuario(email)
            session['rol'] = rol

            return redirect(url_for('index_page'))  # SIEMPRE redirige al index


        else:
               flash("Usuario y/o Contraseña incorrecta.", "error")
               return redirect(url_for('inicio_sesion'))

    # Si por alguna razón no se ejecuta ninguno de los bloques anteriores
    return redirect(url_for('inicio_sesion'))

@app.route("/historicos", methods=["GET"])
def ver_historicos():
    tipo_archivo = request.args.get("tipo_archivo", "excel").lower()
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plantillas", "historicos"))
    if tipo_archivo == "excel":
        carpeta = os.path.join(base_dir, "Excel")
        extensiones = (".xlsx", ".xls")
    else:
        carpeta = os.path.join(base_dir, "Json")
        extensiones = (".json",)
    os.makedirs(carpeta, exist_ok=True)
    archivos = [f for f in os.listdir(carpeta) if f.lower().endswith(extensiones)]
    return render_template("historicos.html", archivos=archivos, tipo_archivo=tipo_archivo)


@app.route("/restaurar_historico", methods=["POST"])
def restaurar_historico():
    archivo = request.form.get("archivo")
    tipo_archivo = request.form.get("tipo_archivo", "excel").lower()
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plantillas", "historicos"))
    if tipo_archivo == "excel":
        origen = os.path.join(base_dir, "Excel", archivo)
        destino = os.path.join(BASE_DIR, "Plantillas", "Validados", archivo)
    else:
        origen = os.path.join(base_dir, "Json", archivo)
        destino = os.path.join(BASE_DIR, "Plantillas", "Salida", archivo)
    # ... resto del código para mover el archivo ...

@app.route('/cerrar_sesion')
def cerrar_sesion():
    # Elimina la sesión del usuario
    session.pop('user', None)
    flash("Sesión cerrada exitosamente.", "success")
    return redirect(url_for('inicio_sesion'))

@app.route('/dashboard', methods=['GET'])
def dashboard():
    if 'user' not in session:
        flash("Debe iniciar sesión para acceder al dashboard.", "error")
        return redirect(url_for('inicio_sesion'))
    return render_template('validador.html')
    
@app.route('/validador', methods=['GET', 'POST'])
def validador():
    if request.method == 'GET':
        conn = conectar_db()
        if not conn:
            flash("Error al conectar a la base de datos.", "error")
            return render_template('validador.html', json_files=[], procesos=[])

        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT NombrePlantilla FROM [dbo].[PlantillasValidacion] 
                WHERE EstadoPlantilla = 'Activo'
            """)
            json_files = [row.NombrePlantilla for row in cursor.fetchall()]

            cursor.execute("""
                SELECT idProcesoAdmin, nombreProcesoAdmin 
                FROM [dbo].[ProcesosAdministrativos] 
                WHERE estadoProcesoAdmin IN ('Activo', 'Inactivo')
            """)
            procesos = cursor.fetchall()
        except pyodbc.Error as e:
            flash(f"Error al obtener datos: {str(e)}", "error")
            json_files, procesos = [], []
        finally:
            cursor.close()
            conn.close()

        return render_template('validador.html', json_files=json_files, procesos=procesos)

     # POST: Validación
    file_excel = request.files.get('file_excel')
    json_select = request.form.get('jsonSelect')
    process_id = request.form.get('processSelect')
    file_date = request.form.get('file_date')

    if not file_excel or not json_select or not process_id or not file_date:
        flash("Debe completar todos los campos del formulario.", "error")
        return redirect(url_for("validador"))

    if file_excel.filename == '':
        flash("Debe seleccionar un archivo Excel válido.", "error")
        return redirect(url_for("validador"))

    try:
        process_id = int(process_id)
    except ValueError:
        flash("El proceso seleccionado no es válido.", "error")
        return redirect(url_for("validador"))

    # Obtener el correo electrónico del usuario de la sesión
    usuario_correo = session.get('user')
    if not usuario_correo:
        flash("Error: Sesión de usuario no encontrada. Por favor, inicie sesión de nuevo.", "error")
        return redirect(url_for('inicio_sesion'))

    # Obtener el idUsuario usando la nueva función
    id_usuario = obtener_id_usuario_por_correo(usuario_correo)
    if id_usuario is None:
        flash(f"Error: No se pudo encontrar el ID para el usuario '{usuario_correo}'.", "error")
        return redirect(url_for('inicio_sesion'))

    # Guardar archivo Excel temporalmente
    excel_path = os.path.join(app.config['VALIDATED_FOLDER'], file_excel.filename)
    if os.path.exists(excel_path):
        historico_dir = os.path.join(BASE_DIR, "Plantillas", "historicos", "Excel")
        os.makedirs(historico_dir, exist_ok=True)
        nombre, ext = os.path.splitext(file_excel.filename)
        # Busca copias existentes
        patron = os.path.join(historico_dir, f"{nombre}_*{ext}")
        existentes = glob.glob(patron)
        # Calcula el siguiente sufijo
        siguiente = 1
        while True:
            nuevo_nombre = f"{nombre}_{siguiente}{ext}"
            if not os.path.exists(os.path.join(historico_dir, nuevo_nombre)):
                break
            siguiente += 1
        shutil.move(excel_path, os.path.join(historico_dir, nuevo_nombre))
    file_excel.save(excel_path)
    
    # Obtener plantillaF
    conn = conectar_db()
    if not conn:
        flash("Error al conectar a la base de datos para obtener la plantilla.", "error")
        return redirect(url_for("validador"))

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT idPlantillasValidacion, RutaJSON 
            FROM dbo.PlantillasValidacion 
            WHERE NombrePlantilla = ?
        """, json_select)
        row = cursor.fetchone()

        if not row:
            flash("No se encontró la plantilla seleccionada.", "error")
            return redirect(url_for("validador"))

        id_plantilla, ruta_json = row
    except pyodbc.Error as e:
        flash(f"Error al obtener plantilla: {str(e)}", "error")
        return redirect(url_for("validador"))
    finally:
        cursor.close()
        conn.close()

    # Validar con Cerberus
    resultado = validar_excel_con_cerberus(excel_path, ruta_json)

    estadoValidacion = 2  # Por defecto: con error
    validated_excel_path = os.path.join(app.config['VALIDATED_FOLDER'], file_excel.filename)
    destinatario = ["hectord.godoy@urosario.edu.co", "juanse.barrios@urosario.edu.co"]

    if resultado['status'] == 'success':
        estadoValidacion = 1
        reporte_texto = f"Validación exitosa. Archivo procesado: {file_excel.filename}"
        reporte_html = f"""
        <div style='text-align:center;'>
            <img src='/static/logoBlanco.png' alt='Universidad del Rosario' style='height:80px; margin-bottom:10px;'><br>
            <strong>Universidad del Rosario</strong><br>
            {reporte_texto}
        </div>
        """
        shutil.copy(excel_path, validated_excel_path)
        limpiar_validados_y_mover_a_historicos()  # <-- AGREGA ESTA LÍNEA AQUÍ

        enviar_reporte_errores(
            errores=[{
                "hoja": "N/A",
                "fila": "N/A",
                "errores": reporte_texto
            }],
            destinatario=destinatario,
            asunto="Validación Exitosa de Archivo Excel"
        )

        flash(reporte_html, "success")

    else:
        errores = resultado.get("errores", [])
        reporte_texto = "\n".join([
            f"Hoja: {e.get('hoja', 'N/A')}, Fila: {e.get('fila', 'N/A')}, Error: {e.get('errores', 'N/A')}"
            for e in errores
        ])

        reporte_html = "<div style='text-align:center;'>" \
                       "<img src='/static/logoBlanco.png' alt='Universidad del Rosario' style='height:80px; margin-bottom:10px;'><br>" \
                       "<strong>Universidad del Rosario</strong><br>" \
                       "Errores detectados:<br>" + "<br>".join([
            f"Hoja: {e.get('hoja', 'N/A')}, Fila: {e.get('fila', 'N/A')}, Error: {e.get('errores', 'N/A')}"
            for e in errores
        ]) + "</div>"

        enviar_reporte_errores(errores, destinatario, asunto="Reporte de Errores en Validación de Excel")

        flash(reporte_html, "error")

    # Guardar validación en la base de datos (incluyendo contenido del Excel)
    conn = conectar_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dbo.Validaciones (
                    idProcesoAdmin, idUsuario, FechaValidacion, idEstado,
                    idPlantillasValidacion, nombreArchivo, reporte,
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                process_id, id_usuario, datetime.now(), estadoValidacion,
                id_plantilla, file_excel.filename[:50], reporte_texto, 
            ))

            conn.commit()
        except pyodbc.Error as e:
            flash(f"Error al guardar validación: {str(e)}", "error")
        finally:
            cursor.close()
            conn.close()
    else:
        flash("Error al conectar a la base de datos para guardar la validación.", "error")

    return redirect(url_for("validador"))



# Ruta para AJAX/API sin recarga
@app.route('/api/validar', methods=['POST'])
def api_validar():
    file_excel = request.files.get("file_excel")
    json_select = request.form.get("jsonSelect")
    file_date_from_form = request.form.get("file_date")
    process_id = request.form.get("processSelect")

    # Cambiado para coincidir con el HTML
    fecha_inicio_datos_form = request.form.get('fecha_inicio')
    fecha_fin_datos_form = request.form.get('fecha_fin')

    if not all([file_excel, json_select, file_date_from_form, process_id]):
        return jsonify({"status": "error", "message": "Faltan campos requeridos.", "errores": []})

    usuario_correo = session.get('user')
    if not usuario_correo:
        return jsonify({"status": "error", "message": "Sesión de usuario no encontrada. Por favor, inicie sesión de nuevo.", "errores": []})

    id_usuario = obtener_id_usuario_por_correo(usuario_correo)
    if id_usuario is None:
        return jsonify({"status": "error", "message": f"No se pudo encontrar el ID para el usuario '{usuario_correo}'.", "errores": []})

    excel_path = os.path.join(app.config['UPLOAD_FOLDER'], file_excel.filename)
    file_excel.save(excel_path)

    conn = conectar_db()
    if not conn:
        return jsonify({"status": "error", "message": "Error de conexión a BD.", "errores": []})

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT idPlantillasValidacion, RutaJSON 
            FROM dbo.PlantillasValidacion 
            WHERE NombrePlantilla = ?
        """, json_select)
        row = cursor.fetchone()
        if not row:
            return jsonify({"status": "error", "message": "Plantilla no encontrada.", "errores": []})
        id_plantilla, ruta_json = row
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

    # ✅ LLAMAR a validar_excel_con_cerberus y obtener las fechas extraídas
    resultado_validacion = validar_excel_con_cerberus(excel_path, ruta_json)
    
    # ✅ Obtener las fechas extraídas del Excel
    fecha_inicio_datos_excel = resultado_validacion.get('fecha_inicio_datos')
    fecha_fin_datos_excel = resultado_validacion.get('fecha_fin_datos')

    final_fecha_inicio_datos = (
    parse_fecha_datetime_local(fecha_inicio_datos_form)
    if fecha_inicio_datos_form
    else (fecha_inicio_datos_excel if fecha_inicio_datos_excel else None)
)
    final_fecha_fin_datos = (
        parse_fecha_datetime_local(fecha_fin_datos_form)
        if fecha_fin_datos_form
        else (fecha_fin_datos_excel if fecha_fin_datos_excel else None)
    )

    estadoValidacion = 2  # Por defecto error
    reporte = ""
    validated_excel_path = os.path.join(app.config['VALIDATED_FOLDER'], file_excel.filename)
    destinatario = ["hectord.godoy@urosario.edu.co", "juanse.barrios@urosario.edu.co"]

    if resultado_validacion['status'] == 'success':
        estadoValidacion = 1
        reporte = f"Validación exitosa. Archivo procesado: {file_excel.filename}"
        shutil.copy(excel_path, validated_excel_path)
        limpiar_validados_y_mover_a_historicos()
        enviar_reporte_errores(
            errores=[{
                "hoja": "N/A",
                "fila": "N/A",
                "errores": reporte
            }],
            destinatario=destinatario,
            asunto="Validación Exitosa de Archivo Excel"
        )
    else:
        errores = resultado_validacion.get("errores", [])
        reporte = "\n".join([
            f"Hoja: {e.get('hoja', 'N/A')}, Fila: {e.get('fila', 'N/A')}, Error: {e.get('errores', 'N/A')}"
            for e in errores
        ])
        enviar_reporte_errores(errores, destinatario, asunto="Reporte de Errores en Validación de Excel")

    # ✅ Guardar en la base de datos (AHORA incluyendo las nuevas fechas)
    conn = conectar_db()
    if conn:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO dbo.Validaciones (
                    idProcesoAdmin, idUsuario, FechaValidacion, idEstado, idPlantillasValidacion, 
                    nombreArchivo, reporte, FechaInicioDeDatos, FechaFinDeDatos
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                int(process_id),
                id_usuario,
                datetime.now(), # Esta es la fecha y hora de la validación actual
                estadoValidacion,
                id_plantilla,
                file_excel.filename[:50],
                reporte,
                final_fecha_inicio_datos, # ✅ Insertar la fecha de inicio de datos
                final_fecha_fin_datos    # ✅ Insertar la fecha de fin de datos
            ))
            conn.commit()
        except pyodbc.Error as e:
            # Aquí podrías querer registrar el error y devolver un mensaje más específico
            print(f"Error al guardar validación en BD: {e}")
            return jsonify({"status": "error", "message": f"Error al guardar validación en BD: {str(e)}", "errores": []})
        finally:
            if cursor: cursor.close()
            if conn: conn.close()
    else:
        return jsonify({"status": "error", "message": "Error al conectar a la base de datos para guardar la validación.", "errores": []})

    return jsonify(resultado_validacion) # Devolver el resultado de la validación al frontend
@app.route('/generar_informe', methods=['GET'])
def generar_informe():
    if 'user' not in session:
        flash("Debe iniciar sesión para generar el informe.", "error")
        return redirect(url_for('inicio_sesion'))

    filtros = session.get('informe_filtros', {})
    usuario = filtros.get('usuario')
    fecha_inicio = filtros.get('fecha_inicio')
    fecha_fin = filtros.get('fecha_fin')

    try:
        conn = conectar_db()
        cursor = conn.cursor()

        query = """
        SELECT 
            v.FechaValidacion,
            u.nombreUsuario,
            v.nombreArchivo,
            p.NombrePlantilla,
            pa.nombreProcesoAdmin,
            ev.nombreEstado,
            v.reporte
        FROM dbo.Validaciones v
        JOIN dbo.usuariosValidador u ON v.idUsuario = u.idUsuario
        JOIN dbo.PlantillasValidacion p ON v.idPlantillasValidacion = p.idPlantillasValidacion
        JOIN dbo.ProcesosAdministrativos pa ON v.idProcesoAdmin = pa.idProcesoAdmin
        JOIN dbo.estadoValidacion ev ON v.idEstado = ev.idEstado
        WHERE 1=1
        """

        params = []
        if usuario:
            query += " AND u.nombreUsuario = ?"
            params.append(usuario)
        if fecha_inicio:
            query += " AND v.FechaValidacion >= ?"
            params.append(fecha_inicio)
        if fecha_fin:
            query += " AND v.FechaValidacion <= ?"
            params.append(fecha_fin)

        cursor.execute(query + " ORDER BY v.FechaValidacion DESC", params)
        rows = cursor.fetchall()
        headers = [col[0] for col in cursor.description]

        df = pd.DataFrame(rows, columns=headers)
        filename = f"informe_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path = os.path.join(OUTPUT_FOLDER, filename)
        df.to_excel(path, index=False)

        return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

    except Exception as e:
        flash(f"Error al generar informe: {str(e)}", "error")
        return redirect(url_for('filtro_informe'))

    finally:
        cursor.close()
        conn.close()


@app.route('/filtro_informe', methods=['GET', 'POST'])
def filtro_informe():
    if 'user' not in session:
        flash("Debe iniciar sesión para acceder al informe.", "error")
        return redirect(url_for('inicio_sesion'))

    conn = conectar_db()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT nombreUsuario FROM dbo.usuariosValidador")
    usuarios = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template('filtro_informe.html', usuarios=usuarios)

@app.route('/ver_resultados', methods=['GET'])
def ver_resultados():
    if 'user' not in session:
        flash("Debe iniciar sesión para ver los resultados.", "error")
        return redirect(url_for('inicio_sesion'))

    usuario = request.args.get('usuario')
    fecha_inicio_validacion = request.args.get('fecha_inicio')
    fecha_fin_validacion = request.args.get('fecha_fin')
    archivo = request.args.get('archivo')
    proceso = request.args.get('proceso')
    fecha_inicio_datos = request.args.get('fecha_datos_inicio')
    fecha_fin_datos = request.args.get('fecha_datos_fin')

    conn = None
    cursor = None

    try:
        conn = conectar_db()
        cursor = conn.cursor()

        # 1. Consulta para la tabla filtrada
        query = """
        SELECT
            v.idValidaciones,
            v.idProcesoAdmin,
            v.idUsuario,
            v.FechaValidacion,
            v.idEstado,
            v.idPlantillasValidacion,
            v.nombreArchivo,
            v.reporte,
            v.FechaInicioDeDatos,
            v.FechaFinDeDatos
        FROM dbo.Validaciones v
        JOIN dbo.usuariosValidador u ON v.idUsuario = u.idUsuario
        WHERE 1=1
        """

        params = []
        if usuario:
            query += " AND u.nombreUsuario = ?"
            params.append(usuario)
        if fecha_inicio_validacion:
            query += " AND v.FechaValidacion >= ?"
            params.append(fecha_inicio_validacion)
        if fecha_fin_validacion:
            query += " AND v.FechaValidacion <= ?"
            params.append(fecha_fin_validacion)
        if archivo:
            query += " AND v.nombreArchivo LIKE ?"
            params.append(f"%{archivo}%")
        if proceso:
            query += " AND v.idProcesoAdmin = ?"
            params.append(proceso)
        if fecha_inicio_datos:
            query += " AND v.FechaInicioDeDatos >= ?"
            params.append(fecha_inicio_datos)
        if fecha_fin_datos:
            query += " AND v.FechaFinDeDatos <= ?"
            params.append(fecha_fin_datos)

        query += " ORDER BY v.FechaValidacion DESC"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        headers = [column[0] for column in cursor.description]

        processed_rows = []
        for row in rows:
            new_row = list(row)
            for i, value in enumerate(new_row):
                if isinstance(value, datetime):
                    new_row[i] = value.strftime('%Y-%m-%d')
            processed_rows.append(new_row)

        # 2. Consulta SIN FILTROS para llenar los selects
        cursor.execute("""
            SELECT DISTINCT nombreArchivo FROM dbo.Validaciones
            WHERE nombreArchivo IS NOT NULL AND nombreArchivo <> ''
        """)
        archivos_unicos = sorted([row[0] for row in cursor.fetchall()])

        cursor.execute("""
            SELECT DISTINCT idProcesoAdmin FROM dbo.Validaciones
            WHERE idProcesoAdmin IS NOT NULL
        """)
        procesos_unicos = sorted([row[0] for row in cursor.fetchall()])

        # Guardar filtros activos para Excel (actualizar con nuevos filtros)
        session['informe_filtros'] = {
            'usuario': usuario,
            'fecha_inicio': fecha_inicio_validacion,
            'fecha_fin': fecha_fin_validacion,
            'archivo': archivo,
            'proceso': proceso,
            'fecha_datos_inicio': fecha_inicio_datos,
            'fecha_datos_fin': fecha_fin_datos
        }

        return render_template(
            'tabla_resultados.html',
            headers=headers,
            rows=processed_rows,
            archivos=archivos_unicos,
            archivo_actual=archivo,
            procesos=procesos_unicos,
            proceso_actual=proceso,
            fecha_inicio_validacion_actual=fecha_inicio_validacion,
            fecha_fin_validacion_actual=fecha_fin_validacion,
            fecha_datos_inicio_actual=fecha_inicio_datos,
            fecha_datos_fin_actual=fecha_fin_datos
        )

    except Exception as e:
        import traceback
        print("ERROR EN ver_resultados:", str(e))
        traceback.print_exc()
        flash(f"Error al obtener resultados: {str(e)}", "error")
        return redirect(url_for('filtro_informe'))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# Ruta para cargar y guardar JSON
@app.route('/cargar_plantilla', methods=['GET', 'POST'])
def cargar_plantilla():
    conn = conectar_db()
    if not conn:
        flash("Error al conectar a la base de datos.", "error")
        return render_template('plantillas.html', procesos=[])
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT idProcesoAdmin, nombreProcesoAdmin FROM [dbo].[ProcesosAdministrativos] WHERE estadoProcesoAdmin IN ('Activo', 'Inactivo')")
        procesos = cursor.fetchall()
    except pyodbc.Error as e:
        flash(f"Error al obtener los archivos JSON o procesos: {str(e)}", "error")
        procesos = []
    finally:
        cursor.close()
        conn.close()

    if request.method == 'POST':
        # Verifica si se envió un archivo JSON
        if 'file_json' not in request.files:
            flash('No se seleccionó ningún archivo JSON.', "error")
            return redirect(url_for('cargar_plantilla'))
        
        file_json = request.files['file_json']
        
        # Verifica si el archivo tiene un nombre
        if file_json.filename == '':
            flash('Por favor seleccione un archivo JSON.', "error")
            return redirect(url_for('cargar_plantilla'))
        
        if 'processSelect' not in request.form:
            flash('Por favor seleccione un proceso administrativo.', "error")
            return redirect(url_for('cargar_plantilla'))
        idProcesoAdmin = request.form['processSelect']
        if file_json:
            # Guarda el archivo JSON subido
            json_path = os.path.join(app.config['UPLOAD_FOLDER'], file_json.filename)
            file_json.save(json_path)
            
            # Guardar el archivo JSON en la base de datos
            mensaje = subir_json(json_path, idProcesoAdmin)
            flash(mensaje)
            return redirect(url_for('cargar_plantilla'))
    
    # Renderiza la plantilla
    return render_template('plantillas.html', procesos=procesos)

@app.route('/api/json_files', methods=['GET'])
def get_json_files():
    proceso_id = request.args.get('proceso_id')
    if not proceso_id:
        return jsonify({"status": "error", "message": "ID del proceso no proporcionado"}), 400

    try:
        proceso_id = int(proceso_id)
    except ValueError:
        return jsonify({"status": "error", "message": "ID del proceso no es válido"}), 400

    conn = conectar_db()
    if not conn:
        return jsonify({"status": "error", "message": "Error al conectar a la base de datos"}), 500

    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT NombrePlantilla 
            FROM dbo.PlantillasValidacion 
            WHERE idProcesoAdmin = ? AND EstadoPlantilla = 'Activo'
        """, (proceso_id,))
        rows = cursor.fetchall()

        json_files = [{"NombrePlantilla": row.NombrePlantilla} for row in rows]

        return jsonify({
            "status": "success",
            "message": "Plantillas encontradas" if json_files else "No hay plantillas disponibles",
            "plantillas": json_files
        })

    except pyodbc.Error as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cursor.close()
        conn.close()

@app.route('/obtener_fechas_json', methods=['GET'])
def obtener_fechas_json_route():
    nombre_plantilla = request.args.get('nombre_plantilla')
    if not nombre_plantilla:
        return jsonify({"error": "Nombre de plantilla no proporcionado"}), 400

    fechas = obtener_fechas_json(nombre_plantilla)
    return jsonify({"fechas": fechas})

# Ruta para elegir el archivo Excel (modal)
@app.route('/crear_plantilla')
def index():
    return render_template('CrearPlantilla.html')

@app.route("/subir_excel", methods=["GET"])
def subir_excel():
    return render_template("CrearPlantilla.html")

uploaded_excel = None  # Esta variable global no es necesaria con el manejo de sesión


@app.route('/upload_excel', methods=["POST"])
def upload_excel():
    
    """
    Función para manejar la subida de archivos Excel.
    Guarda el archivo y lo registra en la sesión.
    """
    try:
        if "file" not in request.files:
            flash("No se envió ningún archivo", "error")
            return redirect(url_for('index'))
        file = request.files["file"]
        if file.filename == "":
            flash("Nombre de archivo vacío", "error")
            return redirect(url_for('index'))

        # Asegurar que el nombre del archivo es seguro (esto es importante para la seguridad)
        filename = os.path.basename(file.filename)  # Obtiene solo el nombre del archivo, sin la ruta
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        print("Intento guardar el archivo en:", filepath)
        file.save(filepath)
        print("Archivo guardado exitosamente en:", filepath)
        session["uploaded_excel"] = filepath  # Usar la ruta segura
        print("Antes de redireccionar, la ruta en sesion es:", session.get("uploaded_excel"))
        print("Redireccionando a /mostrar_tabla")
        return redirect(url_for('mostrar_tabla'))  # Redirige a la ruta correcta
    except Exception as e:
        print(f"Error al subir el archivo: {str(e)}")
        flash(f"Error al subir el archivo: {str(e)}", "error")
        return redirect(url_for('index'))  # Redirige a una página de error o a la página principal


@app.route('/mostrar_tabla')
def mostrar_tabla():
    try:
        uploaded_excel = session.get("uploaded_excel")

        if not uploaded_excel or not os.path.exists(uploaded_excel):
            flash("No se ha subido ningún archivo Excel o no existe.", "error")
            return redirect(url_for('index'))

        # Cargar el Excel y obtener lista de hojas
        xls = pd.ExcelFile(uploaded_excel)
        hojas = xls.sheet_names

        # Verifica si ya se seleccionó una hoja
        hoja_seleccionada = request.args.get("hoja")
        if not hoja_seleccionada:
            return render_template("SeleccionarHoja.html", hojas=hojas)

        session["hoja_seleccionada"] = hoja_seleccionada  # Guardar hoja en sesión

        # Cargar DataFrame de la hoja seleccionada
        df = pd.read_excel(xls, sheet_name=hoja_seleccionada)

        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                df[col] = df[col].dt.strftime('%d/%m/%Y')

        df_transpuesto = df.T
        df_campos = pd.DataFrame(df_transpuesto.index, columns=["Nombre"])
        df_campos["Type"] = ""
        df_campos["Required"] = ""
        df_campos["Regex"] = ""
        rows = df_campos.to_dict(orient='records')
        original_json = json.dumps(rows, ensure_ascii=False) if rows else "[]"

        now = datetime.now()
        fecha_actual = now.strftime("%d/%m/%Y")
        hora_actual = now.strftime("%H:%M:%S")
        nombre_usuario = session.get('user', 'Usuario no identificado')

        conn = conectar_db()
        if conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT er.nombre_ExpresionRegular, td.NombreTipoDato
                FROM dbo.ExpresionesRegulares er
                JOIN dbo.TipoDato td ON er.tipoDato = td.NombreTipoDato
                WHERE er.estado_ExpresionRegular = 'activo'
            """)
            regex_options_by_type = {}
            for nombre, tipo in cursor.fetchall():
                regex_options_by_type.setdefault(tipo, []).append(nombre)
            conn.close()
        else:
            regex_options_by_type = {}

        return render_template(
            'EditarPlantilla.html',
            rows=rows,
            original_json=json.dumps(original_json),
            uploaded_excel=json.dumps(uploaded_excel),
            regex_options_by_type=json.dumps(regex_options_by_type),
            regex_options_dict=regex_options_by_type,
            fecha_actual=fecha_actual,
            hora_actual=hora_actual,
            nombre_usuario=nombre_usuario
        )

    except Exception as e_excel:
        print(f"Error al procesar el archivo Excel: {e_excel}\n{traceback.format_exc()}")
        flash(f"Error al procesar el archivo Excel: {e_excel}", "error")
        return redirect(url_for('index'))



@app.route('/expresiones')
def expresiones_index():
    expresiones = ExpresionRegular.query.all()
    return render_template('ExpresionIndex.html', expresiones=expresiones)

@app.route('/expresiones/crear', methods=['GET', 'POST'])
def expresiones_crear():
    if request.method == 'POST':
        nueva = ExpresionRegular(
            nombre_ExpresionRegular=request.form['nombre'],
            descripcion_ExpresionRegular=request.form['descripcion'],
            expresion_Regular=request.form['expresion'],
            estado_ExpresionRegular=request.form.get('estado', 'Activo'),
            tipoDato=request.form['tipoDato']
        )
        db.session.add(nueva)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('ExpresionFrom.html', modo='Crear', expresion=None)

@app.route('/expresiones/editar/<int:id>', methods=['GET', 'POST'])
def expresiones_editar(id):
    expresion = ExpresionRegular.query.get_or_404(id)
    if request.method == 'POST':
        expresion.nombre_ExpresionRegular = request.form['nombre']
        expresion.descripcion_ExpresionRegular = request.form['descripcion']
        expresion.expresion_Regular = request.form['expresion']
        expresion.estado_ExpresionRegular = request.form.get('estado', 'Activo')
        expresion.tipoDato = request.form['tipoDato']
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('ExpresionFrom.html', modo='Editar', expresion=expresion)

@app.route('/expresiones/eliminar/<int:id>')
def expresiones_eliminar(id):
    expresion = ExpresionRegular.query.get_or_404(id)
    db.session.delete(expresion)
    db.session.commit()
    return redirect(url_for('expresiones_index'))

@app.route('/guardar_plantilla', methods=["POST"])
def guardar_plantilla():
    conn = None
    try:
        print("Inicio de guardar_plantilla")
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No se recibieron datos"}), 400
        
        print("Datos recibidos:", data)

        editado = data.get("editado")
        if not editado:
            return jsonify({"success": False, "error": "No se proporcionaron datos editados"}), 400

        uploaded_excel = data.get("uploaded_excel") or session.get("uploaded_excel")
        if not uploaded_excel or not os.path.exists(uploaded_excel):
            return jsonify({"success": False, "error": "Archivo Excel no encontrado"}), 400

        # Extraer nombre base del archivo sin extensión
        nombre_base = os.path.splitext(os.path.basename(uploaded_excel))[0]

        conn = conectar_db()
        cursor = conn.cursor()

        # Manejo seguro de idProcesoAdmin
        id_proceso_str = data.get("idProcesoAdmin", "").strip()
        try:
            id_proceso = int(id_proceso_str) if id_proceso_str else 1
        except ValueError:
            id_proceso = 1

        print(f"Buscando proceso administrativo con ID: {id_proceso}")
        cursor.execute("""
            SELECT Abreviatura, fechaCreacionProcesoAdmin
            FROM dbo.ProcesosAdministrativos 
            WHERE idProcesoAdmin = ?
        """, (id_proceso,))
        resultado = cursor.fetchone()

        # Asignar abreviatura y fecha si existe el proceso
        if resultado:
            abreviatura, fecha_raw = resultado
            fecha_creacion = fecha_raw.strftime("%Y-%m-%d") if not isinstance(fecha_raw, str) else fecha_raw
        else:
            abreviatura = "DEFAULT"
            fecha_creacion = datetime.now().strftime("%Y-%m-%d")

        # Construir plantilla final
        plantilla_final = {
            "nombre_excel": os.path.basename(uploaded_excel),
            "nombre_hoja": pd.ExcelFile(uploaded_excel).sheet_names[0] if pd.ExcelFile(uploaded_excel).sheet_names else "Hoja1",
            "contenido_excel": editado,
            "fecha_creacion": fecha_creacion,
            "usuario": session.get("user", "default_user"),
            "proceso_admin": id_proceso
        }

        # Debug: Verificar contenido antes de serializar
        print("Contenido de plantilla_final:", plantilla_final)
        print("Tipos de datos:", {k: type(v) for k, v in plantilla_final.items()})

        # Clase para serializar objetos datetime
        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)

        # Crear nombre del archivo con fecha y abreviatura
        nombre_hoja = plantilla_final["nombre_hoja"]
        prefijo_archivo = f"{abreviatura}_{nombre_base}_{nombre_hoja}"

        # Buscar archivos existentes con el mismo prefijo
        archivos_existentes = [
            f for f in os.listdir(OUTPUT_FOLDER)
            if f.startswith(prefijo_archivo) and f.endswith(".json")
        ]

        # Extraer número de versión más alto y sumar 1
        numeros = []
        for nombre in archivos_existentes:
            partes = nombre.replace(".json", "").split("_")
            if len(partes) >= 4 and partes[-1].isdigit():
                numeros.append(int(partes[-1]))

        siguiente_numero = max(numeros) + 1 if numeros else 1
       

        # Crear nombre final con número consecutivo
        nombre_archivo = f"{prefijo_archivo}_{siguiente_numero}.json"
        ruta_archivo = os.path.join(OUTPUT_FOLDER, nombre_archivo)


        # Guardar JSON en archivo
        with open(ruta_archivo, "w", encoding="utf-8") as f:
            json.dump(plantilla_final, f, cls=DateTimeEncoder, ensure_ascii=False, indent=2)

        print(f"Plantilla guardada exitosamente en: {ruta_archivo}")

        # Serializar nuevamente para la base de datos con el mismo encoder
        json_serializado = json.dumps(plantilla_final, cls=DateTimeEncoder)

        # Insertar en la base de datos (PlantillasValidacion)
        cursor.execute("""
            INSERT INTO dbo.PlantillasValidacion (
                idProcesoAdmin,
                NombrePlantilla,
                ContenidoJSON,
                RutaJSON,
                FechaCarga,
                UsuarioCargue,
                EstadoPlantilla
            )
            OUTPUT INSERTED.idPlantillasValidacion
            VALUES (?, ?, ?, ?, GETDATE(), ?, 'activo')
        """, (
            id_proceso,
            nombre_archivo,
            json_serializado,  # Usamos el JSON ya serializado
            ruta_archivo,
            session.get("user", "default_user")
        ))

        row = cursor.fetchone()
        id_insertado = row[0] if row else None
        conn.commit()

        return jsonify({
            "success": True, 
            "download_url": url_for("descargar_archivo", nombre_archivo=nombre_archivo),
            "db_id": id_insertado
        })

    except Exception as e:
        print("Error al guardar plantilla:", str(e))
        traceback.print_exc()
        if conn:
            conn.rollback()
        return jsonify({
            "success": False, 
            "error": f"Error interno al guardar plantilla: {str(e)}"
        }), 500
    finally:
        if conn:
            conn.close()

@app.route('/descargar_archivo/<nombre_archivo>')
def descargar_archivo(nombre_archivo):
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ContenidoJSON 
            FROM dbo.PlantillasValidacion 
            WHERE NombrePlantilla = ?
        """, (nombre_archivo,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            if 'user' in session and session.get('rol') == 'administrador':
                flash("Archivo no encontrado en la base de datos.", "danger")
                return redirect(url_for('admin_gestion_plantillas'))
            else:
                flash("No tiene permisos para acceder o el archivo no existe.", "danger")
                return redirect(url_for('inicio_sesion'))

        contenido_json = row.ContenidoJSON if hasattr(row, 'ContenidoJSON') else row[0]

        # Formatear JSON con indentación (4 espacios)
        contenido_formateado = json.dumps(json.loads(contenido_json), indent=4, ensure_ascii=False)

        return app.response_class(
            response=contenido_formateado,
            mimetype='application/json',
            headers={
                "Content-Disposition": f"attachment; filename={nombre_archivo}"
    }
)


    except Exception as e:
        print("Error al acceder al archivo:", str(e))
        flash("No se pudo acceder al archivo.", "danger")
        return redirect(url_for('admin_gestion_plantillas'))


def obtener_rol_usuario(email):
    """
    Retorna el rol del usuario según su correo.
    """
    try:
        conn = conectar_db()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT rol FROM dbo.usuariosValidador WHERE correoUsuario = ? AND estadoUsuario = 'activo'",
            (email,)
        )
        row = cursor.fetchone()
        return row.rol if row else None
    except Exception as e:
        print(f"Error al obtener rol: {e}")
        return None
    finally:
        if conn:
            conn.close()



@app.route('/admin/gestion_plantillas')
def admin_gestion_plantillas():
    if 'user' not in session or session.get('rol') != 'administrador':
        flash("Acceso restringido solo para administradores.", "error")
        return redirect(url_for('inicio_sesion'))

    conn = conectar_db()
    cursor = conn.cursor()

    # Plantillas registradas
    cursor.execute("""
        SELECT idPlantillasValidacion, NombrePlantilla, FechaCarga, UsuarioCargue
        FROM dbo.PlantillasValidacion
        ORDER BY FechaCarga DESC
    """)
    plantillas = cursor.fetchall()

    # Validaciones realizadas
    cursor.execute("""
        SELECT u.nombreUsuario, u.correoUsuario, p.NombrePlantilla, v.FechaValidacion, v.nombreArchivo
        FROM dbo.usuariosValidador u
        JOIN dbo.Validaciones v ON u.idUsuario = v.idUsuario
        JOIN dbo.PlantillasValidacion p ON v.idPlantillasValidacion = p.idPlantillasValidacion
        JOIN dbo.ProcesosAdministrativos pa ON v.idProcesoAdmin = pa.idProcesoAdmin
        JOIN dbo.estadoValidacion ev ON v.idEstado = ev.idEstado
        ORDER BY v.FechaValidacion DESC
    """)
    validaciones = cursor.fetchall()

    conn.close()

    return render_template('admin_gestion_plantillas.html', plantillas=plantillas, validaciones=validaciones)

def parse_fecha_datetime_local(fecha_str):
    if fecha_str:
        try:
            return datetime.strptime(fecha_str, "%Y-%m-%dT%H:%M")
        except ValueError:
            pass
        try:
            return datetime.strptime(fecha_str, "%Y-%m-%d")
        except ValueError:
            pass
    return None


def limpiar_validados_y_mover_a_historicos():
    """
    Deja solo el archivo más reciente (por fecha de modificación) de cada base de nombre y mes/año en Validados (Excel)
    y Salida (JSON), y mueve los demás a la carpeta historicos/Excel o historicos/Json.
    """
    # --- EXCEL ---
    validados_dir = os.path.join(BASE_DIR, "Plantillas", "Validados")
    historicos_excel_dir = os.path.join(BASE_DIR, "Plantillas", "historicos", "Excel")
    os.makedirs(historicos_excel_dir, exist_ok=True)

    archivos_excel = [f for f in os.listdir(validados_dir) if f.lower().endswith(".xlsx") or f.lower().endswith(".xls")]
    grupos_excel = {}
    patron_excel = re.compile(r"^(.*?)(?:_(\d+))?\.(xlsx|xls)$", re.IGNORECASE)
    for archivo in archivos_excel:
        match = patron_excel.match(archivo)
        if match:
            base = match.group(1)
            ruta = os.path.join(validados_dir, archivo)
            fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
            clave = (base, fecha_mod.year, fecha_mod.month)
            grupos_excel.setdefault(clave, []).append((archivo, fecha_mod))

    for clave, archivos_base in grupos_excel.items():
        archivos_base.sort(key=lambda x: x[1])
        for antiguo, _ in archivos_base[:-1]:
            origen = os.path.join(validados_dir, antiguo)
            destino = os.path.join(historicos_excel_dir, antiguo)
            shutil.move(origen, destino)

    # --- JSON ---
    salida_dir = os.path.join(BASE_DIR, "Plantillas", "Salida")
    historicos_json_dir = os.path.join(BASE_DIR, "Plantillas", "historicos", "Json")
    os.makedirs(historicos_json_dir, exist_ok=True)

    archivos_json = [f for f in os.listdir(salida_dir) if f.lower().endswith(".json")]
    grupos_json = {}
    patron_json = re.compile(r"^(.*?)(?:_(\d+))?\.json$", re.IGNORECASE)
    for archivo in archivos_json:
        match = patron_json.match(archivo)
        if match:
            base = match.group(1)
            ruta = os.path.join(salida_dir, archivo)
            fecha_mod = datetime.fromtimestamp(os.path.getmtime(ruta))
            clave = (base, fecha_mod.year, fecha_mod.month)
            grupos_json.setdefault(clave, []).append((archivo, fecha_mod))

    for clave, archivos_base in grupos_json.items():
        archivos_base.sort(key=lambda x: x[1])
        for antiguo, _ in archivos_base[:-1]:
            origen = os.path.join(salida_dir, antiguo)
            destino = os.path.join(historicos_json_dir, antiguo)
            shutil.move(origen, destino)

@app.route('/ver_archivo_historico/<tipo_archivo>/<archivo>')
def ver_archivo_historico(tipo_archivo, archivo):
    """
    Muestra o descarga el archivo histórico seleccionado.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plantillas", "historicos"))
    if tipo_archivo == "excel":
        carpeta = os.path.join(base_dir, "Excel")
    else:
        carpeta = os.path.join(base_dir, "Json")
    # Seguridad: evita rutas relativas peligrosas
    archivo = os.path.basename(archivo)
    try:
        return send_from_directory(carpeta, archivo, as_attachment=True)
    except Exception as e:
        flash(f"No se pudo acceder al archivo: {str(e)}", "danger")
        return redirect(url_for('ver_historicos', tipo_archivo=tipo_archivo))

@app.route('/ver_json_historico/<archivo>')
def ver_json_historico(archivo):
    import json
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "Plantillas", "historicos", "Json"))
    archivo = os.path.basename(archivo)
    ruta = os.path.join(base_dir, archivo)
    try:
        with open(ruta, encoding="utf-8") as f:
            contenido = json.load(f)
        return jsonify(contenido)
    except Exception as e:
        return jsonify({"error": str(e)}), 404

from flask import jsonify, send_from_directory

@app.route('/ver_json/<nombre_archivo>')
def ver_json(nombre_archivo):
    import os, json
    base_dir = os.path.abspath(os.path.dirname(__file__))
    ruta_salida = os.path.join(base_dir, "Plantillas", "Salida", nombre_archivo)
    ruta_historico = os.path.join(base_dir, "Plantillas", "historicos", "Json", nombre_archivo)
    try:
        with open(ruta_salida, 'r', encoding='utf-8') as f:
            contenido = json.load(f)
        return jsonify(contenido)
    except Exception:
        # Si no está en Salida, intenta buscar en históricos
        if os.path.exists(ruta_historico):
            return jsonify({
                "mensaje": "Esta plantilla se encuentra en el histórico. Puedes descargarla desde la sección de históricos."
            })
        else:
            return jsonify({'error': 'No se pudo leer el archivo'}), 404
