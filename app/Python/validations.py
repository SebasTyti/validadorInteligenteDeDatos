import pandas as pd
import json
import re
import pyodbc
from app.json_handler import conectar_db
from datetime import datetime

def convertir_fecha(valor):
    """
    Convierte un valor a formato de fecha DD/MM/YYYY si es posible.
    Soporta varios formatos de entrada y objetos datetime/Timestamp.
    Retorna la fecha en 'DD/MM/YYYY' como cadena, o None si no puede convertirlo.
    """
    if pd.isna(valor):
        return None

    if isinstance(valor, str):
        valor_limpio = valor.strip()
        formatos = ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d")
        for fmt in formatos:
            try:
                return datetime.strptime(valor_limpio, fmt).strftime('%d/%m/%Y')
            except ValueError:
                continue
        return valor_limpio
    elif isinstance(valor, (pd.Timestamp, datetime)):
        return valor.strftime('%d/%m/%Y')
    return str(valor)

def validar_excel_con_cerberus(excel_path, json_path):
    """
    Valida un archivo Excel basándose en una plantilla JSON y expresiones regulares de una base de datos.
    """
    errores = []
    conn = None
    cursor = None

    try:
        df = pd.read_excel(excel_path)
        df.columns = df.columns.str.strip().str.upper()

        with open(json_path, 'r', encoding='utf-8') as f:
            plantilla = json.load(f)

        hoja = plantilla.get("nombre_hoja", "Hoja1")
        configuraciones = plantilla.get("contenido_excel", [])

        conn = conectar_db()
        cursor = conn.cursor()
        regex_cache = {}

        for columna_conf in configuraciones:
            nombre_col = columna_conf.get("Nombre")
            if not nombre_col:
                errores.append({
                    "hoja": hoja,
                    "fila": "-",
                    "errores": "Configuración JSON inválida: 'Nombre' de columna faltante."
                })
                continue

            nombre_col_normalizado = nombre_col.strip().upper()
            nombre_regex = columna_conf.get("Regex")
            tipo_dato = (columna_conf.get("Tipo") or columna_conf.get("Type", "")).lower().strip()
            requerido = columna_conf.get("Required", "").lower() == "obligatorio"

            if nombre_col_normalizado not in df.columns:
                errores.append({
                    "hoja": hoja,
                    "fila": "-",
                    "errores": f"Columna '{nombre_col}' no encontrada en el archivo Excel. Asegúrate de que el nombre sea correcto."
                })
                continue

            # Obtener regex de la caché o de la base de datos
            if nombre_regex in regex_cache:
                regex = regex_cache[nombre_regex]
            else:
                if not nombre_regex:
                    errores.append({
                        "hoja": hoja,
                        "fila": "-",
                        "errores": f"Configuración JSON inválida para columna '{nombre_col}': 'Regex' faltante."
                    })
                    continue

                cursor.execute("""
                    SELECT expresion_Regular FROM dbo.ExpresionesRegulares
                    WHERE nombre_ExpresionRegular = ? AND estado_ExpresionRegular = 'Activo'
                """, nombre_regex)
                row = cursor.fetchone()

                if not row:
                    errores.append({
                        "hoja": hoja,
                        "fila": "-",
                        "errores": f"Expresión regular '{nombre_regex}' no encontrada o inactiva en la base de datos para la columna '{nombre_col}'."
                    })
                    continue
                regex = row[0]
                regex_cache[nombre_regex] = regex

            try:
                pattern = re.compile(regex)
            except re.error as e:
                errores.append({
                    "hoja": hoja,
                    "fila": "-",
                    "errores": f"La expresión regular '{nombre_regex}' es inválida: {e}"
                })
                continue

            for idx, valor in df[nombre_col_normalizado].items():
                fila_excel = idx + 2  # +1 por índice base 0, +1 por encabezado

                # Si el campo no es obligatorio y el valor es '-' o vacío, se acepta
                if not requerido and (pd.isna(valor) or str(valor).strip().lower() in ['', '-', 'n/a']):

                    continue

                # 1. Validación de campo obligatorio vacío
                if pd.isna(valor) or (isinstance(valor, str) and valor.strip() == ''):
                    if requerido:
                        errores.append({
                            "hoja": hoja,
                            "fila": fila_excel,
                            "errores": f"Campo obligatorio vacío en columna '{nombre_col}'"
                        })
                    continue

                valor_procesado = None

                # 2. Conversión y ajuste según tipo de dato
                if tipo_dato in ("fecha", "date"):
                    valor_convertido_fecha = convertir_fecha(valor)
                    if valor_convertido_fecha is None:
                        pass
                    else:
                        try:
                            fecha_obj = datetime.strptime(valor_convertido_fecha, '%d/%m/%Y')
                            if nombre_regex.lower() == "formatoañomesdia":
                                valor_procesado = fecha_obj.strftime('%Y/%m/%d')
                            elif nombre_regex.lower() == "formatofechadiamesaño":
                                valor_procesado = fecha_obj.strftime('%d/%m/%Y')
                            elif nombre_regex.lower() == "formatofecha-d-m-a":
                                valor_procesado = fecha_obj.strftime('%d-%m-%Y')
                            elif nombre_regex.lower() == "formatofecha/d/m/a":
                                valor_procesado = fecha_obj.strftime('%d/%m/%Y')
                            else:
                                valor_procesado = valor_convertido_fecha
                        except ValueError:
                            errores.append({
                                "hoja": hoja,
                                "fila": fila_excel,
                                "errores": f"'{valor}' no es un formato de fecha válido en columna '{nombre_col}'"
                            })
                            continue

                elif nombre_regex.lower() == "formatonumeroentero":
                    try:
                        valor_entero = int(float(valor))
                        valor_procesado = str(valor_entero)
                    except (ValueError, TypeError):
                        errores.append({
                            "hoja": hoja,
                            "fila": fila_excel,
                            "errores": f"'{valor}' no es un número entero válido en columna '{nombre_col}'"
                        })
                        continue

                else:
                    valor_procesado = str(valor)

                # Limpieza final del string antes de la regex
                if valor_procesado is not None:
                    valor_procesado = valor_procesado.strip()
                    valor_procesado = re.sub(r"\s+", " ", valor_procesado)
                else:
                    valor_procesado = ""

                # 3. Validación de patrón de expresión regular
                if valor_procesado is not None and not pattern.fullmatch(valor_procesado):
                    errores.append({
                        "hoja": hoja,
                        "fila": fila_excel,
                        "errores": f"'{valor_procesado}' no cumple con el patrón '{nombre_regex}' para la columna '{nombre_col}'"
                    })

    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"Error: El archivo Excel no fue encontrado en la ruta: {excel_path}",
            "errores": []
        }
    except pd.errors.EmptyDataError:
        return {
            "status": "error",
            "message": "Error: El archivo Excel está vacío.",
            "errores": []
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error inesperado durante la validación: {str(e)}",
            "errores": []
        }
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    if errores:
        return {
            "status": "error",
            "message": "Errores encontrados durante la validación.",
            "errores": errores
        }
    else:
        return {
            "status": "success",
            "message": "Archivo validado correctamente. No se encontraron errores."
        }
