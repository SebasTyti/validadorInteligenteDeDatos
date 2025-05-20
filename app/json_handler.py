import datetime
import pyodbc
import os
import json
import shutil
import time
import logging
from app.Python.config import Config

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('file_operations.log'),
        logging.StreamHandler()
    ]
)

def conectar_db():
    try:
        db_config = Config.DB_CONFIG
        connection_string = (
            f"DRIVER={{{db_config['driver']}}};"
            f"SERVER={db_config['server']};"
            f"DATABASE={db_config['database']};"
            f"UID={db_config['username']};"
            f"PWD={db_config['password']};"
            f"Authentication={db_config['authentication']};"
        )
        conn = pyodbc.connect(connection_string)
        logging.info("Conexión a la base de datos exitosa.")
        return conn
    except pyodbc.Error as e:
        logging.error(f"Error al conectar a la base de datos: {e}")
        return None

def _force_remove_file(filepath):
    """Eliminación forzada con múltiples estrategias"""
    try:
        os.remove(filepath)
    except PermissionError:
        try:
            os.unlink(filepath)
        except:
            try:
                time.sleep(1)
                os.chmod(filepath, 0o777)  # Intenta cambiar permisos
                os.remove(filepath)
            except Exception as e:
                logging.error(f"No se pudo eliminar el archivo {filepath}: {e}")
                raise

def mover_a_historicos(nombre_plantilla, ruta_actual, max_reintentos=5, delay=1):
    """
    Versión mejorada con manejo robusto de archivos bloqueados en Windows
    """
    uploads_dir = os.path.join("uploads", "historicos")
    nueva_ruta = os.path.join(uploads_dir, os.path.basename(ruta_actual))
    
    if not os.path.exists(ruta_actual):
        logging.warning(f"Archivo no encontrado: {ruta_actual}")
        return None

    os.makedirs(uploads_dir, exist_ok=True)

    last_exception = None
    for intento in range(max_reintentos):
        try:
            # Estrategia de 3 pasos para máxima robustez
            try:
                # 1. Intento directo (más rápido)
                shutil.move(ruta_actual, nueva_ruta)
                return nueva_ruta
            except PermissionError:
                try:
                    # 2. Copia + eliminación con renombrado atómico
                    temp_path = nueva_ruta + ".tmp"
                    shutil.copy2(ruta_actual, temp_path)
                    os.rename(temp_path, nueva_ruta)
                    _force_remove_file(ruta_actual)
                    return nueva_ruta
                except PermissionError:
                    # 3. Intento alternativo
                    _force_remove_file(ruta_actual)
                    return nueva_ruta
        except PermissionError as e:
            last_exception = e
            logging.warning(f"Intento {intento + 1}/{max_reintentos}: Archivo bloqueado. Reintentando en {delay} segundos...")
            time.sleep(delay)
        except Exception as e:
            logging.error(f"Error inesperado: {e}")
            raise

    logging.error(f"Fallo después de {max_reintentos} intentos")
    raise last_exception if last_exception else PermissionError("No se pudo mover el archivo")

def subir_json(json_path, idProcesoAdmin):
    """Función mejorada para subir JSON con manejo seguro de archivos"""
    try:
        # Lectura segura del archivo
        with open(json_path, 'r', encoding='utf-8') as file:
            contenido_json = file.read()
        logging.info("Contenido del JSON leído correctamente")
    except Exception as e:
        logging.error(f"Error al leer JSON: {e}")
        return f"Error al leer el archivo JSON: {str(e)}"

    nombre_plantilla = os.path.basename(json_path)
    fecha_actual = datetime.datetime.now()

    conn = None
    try:
        conn = conectar_db()
        if not conn:
            return "Error al conectar a la base de datos."

        cursor = conn.cursor()
        
        # Verificar archivo existente
        cursor.execute(
            "SELECT RutaJSON FROM dbo.PlantillasValidacion WHERE NombrePlantilla = ?", 
            nombre_plantilla
        )
        row = cursor.fetchone()
        
        if row and row[0] and os.path.exists(row[0]):
            try:
                nueva_ruta = mover_a_historicos(nombre_plantilla, row[0])
                cursor.execute(
                    "UPDATE dbo.PlantillasValidacion SET RutaJSON = ? WHERE NombrePlantilla = ?", 
                    (nueva_ruta, nombre_plantilla)
                )
                conn.commit()
                logging.info(f"Archivo existente movido a {nueva_ruta}")
            except Exception as e:
                logging.error(f"Error al mover archivo existente: {e}")
                conn.rollback()
        
        # Insertar nuevo registro
        cursor.execute(
            """
            INSERT INTO [dbo].[PlantillasValidacion]
            (NombrePlantilla, ContenidoJson, RutaJSON, FechaCarga, 
             FechaUltimaModificacion, UsuarioCargue, EstadoPlantilla, idProcesoAdmin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                nombre_plantilla,
                contenido_json,
                json_path,
                fecha_actual,
                fecha_actual,
                "hectord.godoy@urosario.edu.co",
                "Activo",
                idProcesoAdmin
            )
        )
        conn.commit()
        logging.info("Registro insertado correctamente")
        return "Archivo JSON guardado exitosamente"
        
    except pyodbc.Error as e:
        if conn:
            conn.rollback()
        logging.error(f"Error de base de datos: {e}")
        return f"Error al guardar en BD: {str(e)}"
    finally:
        if conn:
            conn.close()

def obtener_nombres_json():
    conn = conectar_db()
    if not conn:
        return []

    cursor = conn.cursor()
    try:
        query = """
        SELECT NombrePlantilla, MAX(FechaCarga) as FechaUltimaModificacion 
        FROM [dbo].[PlantillasValidacion]
        GROUP BY NombrePlantilla
        ORDER BY NombrePlantilla, FechaUltimaModificacion DESC
        """
        cursor.execute(query)
        return [{"nombre": row[0]} for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

def obtener_fechas_json(nombre_plantilla):
    conn = conectar_db()
    if not conn:
        return []

    cursor = conn.cursor()
    try:
        query = """
        SELECT FechaCarga 
        FROM [dbo].[PlantillasValidacion]
        WHERE NombrePlantilla = ?
        ORDER BY FechaCarga DESC
        """
        cursor.execute(query, (nombre_plantilla,))
        return [row[0].strftime('%Y-%m-%d %H:%M:%S') for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()