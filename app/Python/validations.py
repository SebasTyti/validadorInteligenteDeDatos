import pandas as pd
import json
import re
import pyodbc
from app.json_handler import conectar_db  # Usa tu función existente

def validar_excel_con_cerberus(excel_path, json_path):
    try:
        df = pd.read_excel(excel_path)

        # Normalizar columnas: quitar espacios y convertir a mayúsculas
        df.columns = df.columns.str.strip().str.upper()

        print("Columnas detectadas en el Excel:", df.columns.tolist())

        with open(json_path, 'r', encoding='utf-8') as f:
            plantilla = json.load(f)

        hoja = plantilla.get("nombre_hoja", df.columns)  # default si no se encuentra
        configuraciones = plantilla.get("contenido_excel", [])

        errores = []
        conn = conectar_db()
        cursor = conn.cursor()

        for columna_conf in configuraciones:
            nombre_col = columna_conf.get("Nombre")
            nombre_col_normalizado = nombre_col.strip().upper()
            nombre_regex = columna_conf.get("Regex")
            requerido = columna_conf.get("Required", "").lower() == "obligatorio"

            if nombre_col_normalizado not in df.columns:
                errores.append({"hoja": hoja, "fila": "-", "errores": f"Columna '{nombre_col}' no encontrada en Excel."})
                continue

            # Buscar expresión regular
            cursor.execute("""
                SELECT expresion_Regular FROM dbo.ExpresionesRegulares
                WHERE nombre_ExpresionRegular = ? AND estado_ExpresionRegular = 'Activo'
            """, nombre_regex)

            row = cursor.fetchone()
            if not row:
                errores.append({"hoja": hoja, "fila": "-", "errores": f"Regex '{nombre_regex}' no encontrada o inactiva."})
                continue

            regex = row[0]
            pattern = re.compile(regex)

            for idx, valor in df[nombre_col_normalizado].items():
                fila_excel = idx + 2  # base 1 + encabezado

                if pd.isna(valor):
                    if requerido:
                        errores.append({
                            "hoja": hoja,
                            "fila": fila_excel,
                            "errores": f"Campo obligatorio vacío en columna '{nombre_col}'"
                        })
                    continue

                valor_str = str(valor).strip().strip("'\"")  # quita comillas simples y dobles
                valor_str = re.sub(r"[^\S\r\n]+", " ", valor_str)  # colapsa espacios raros

                if not pattern.fullmatch(valor_str):
                    errores.append({
                        "hoja": hoja,
                        "fila": fila_excel,
                        "errores": f"'{valor_str}' no cumple con el patrón de '{nombre_regex}'"
                    })

        cursor.close()
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

    except Exception as e:
        return {
            "status": "error",
            "message": f"Error en validación: {str(e)}",
            "errores": []
        }
