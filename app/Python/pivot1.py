import pandas as pd
import json
import os
import math

# 1. Obtener la ruta absoluta del script actual (para encontrar convertor.json)
current_dir = os.path.dirname(os.path.abspath(__file__))
schema_file = os.path.join(current_dir, "convertor.json")

# 2. Cargar el archivo convertor.json
with open(schema_file, "r", encoding="utf-8") as f:
    schema = json.load(f)

# 3. Seleccionar la hoja que se desea leer (en este caso "Hoja1")
sheet_name = "Hoja1"
schema_sheet = schema["hojas"].get(sheet_name, {})

# 4. Convertir el diccionario en un DataFrame (las claves del JSON son los nombres originales de los campos)
df = pd.DataFrame.from_dict(schema_sheet, orient="index")
df.reset_index(inplace=True)
df.rename(columns={"index": "nombre"}, inplace=True)

# 5. Agregar una columna "id" con identificadores consecutivos: id1, id2, ...
df["id"] = ["id" + str(i+1) for i in range(len(df))]

# 6. Convertir el DataFrame a una lista de diccionarios
records = df.to_dict(orient="records")

# 7. Transformar los campos editables en estructuras para edición
#    Se trabajará con los siguientes campos: "tipo", "required", "maxlength" y "regex"
campos_editables = ["tipo", "required", "maxlength", "regex"]

for rec in records:
    for campo in campos_editables:
        original_value = rec.get(campo)
        # Si el valor es NaN o None, reemplazarlo por cadena vacía
        if original_value is None or (isinstance(original_value, float) and math.isnan(original_value)):
            original_value = ""
        
        # Definir opciones predefinidas para ciertos campos
        if campo == "tipo":
            options = ["string", "integer", "number"]
        elif campo == "required":
            # Convertir valores booleanos a "obligatorio" u "opcional"
            if original_value is True:
                original_value = "obligatorio"
            elif original_value is False:
                original_value = "opcional"
            options = ["obligatorio", "opcional"]
        else:
            options = None  # para regex y maxlength no se definen opciones fijas

        rec[campo] = {
            "value": original_value,
            "editable": True
        }
        if options is not None:
            rec[campo]["options"] = options

# 8. Convertir todo a JSON (este string se usará dentro del HTML para la descarga)
json_string = json.dumps(records, ensure_ascii=False, indent=4)

# 9. Guardar el JSON resultante en un archivo (opcional, por si quieres tenerlo en disco)
json_file = os.path.join(current_dir, "convertor_excel.json")
with open(json_file, "w", encoding="utf-8") as f:
    f.write(json_string)

# 10. Generar la tabla HTML editable
#     La primera columna mostrará el id y el nombre original del campo
table_html = """
<table border="1" cellspacing="0" cellpadding="5">
    <thead>
        <tr>
            <th>ID (Nombre)</th>
            <th>Tipo</th>
            <th>Required</th>
            <th>Maxlength</th>
            <th>Regex</th>
        </tr>
    </thead>
    <tbody>
"""
for rec in records:
    table_html += "<tr>"
    # Mostrar en la primera columna "id - nombre"
    id_nombre = f"{rec.get('id', '')} - {rec.get('nombre', '')}"
    table_html += f"<td>{id_nombre}</td>"
    
    # Para cada campo editable, si hay "options" se hace un <select>, si no un <input>
    for campo in campos_editables:
        celda = ""
        valor = rec[campo]["value"]
        if "options" in rec[campo]:
            celda += "<select>"
            for opt in rec[campo]["options"]:
                selected = "selected" if opt == valor else ""
                celda += f"<option value='{opt}' {selected}>{opt}</option>"
            celda += "</select>"
        else:
            celda += f"<input type='text' value='{valor}' />"
        
        table_html += f"<td>{celda}</td>"
    table_html += "</tr>"
table_html += """
    </tbody>
</table>
"""

# 11. Crear el botón de descarga usando Data URL (no se requiere fetch ni Blob.createObjectURL)
download_button = f"""
<div style="text-align:center; margin-top:20px;">
    <button type="button" onclick="downloadJSON()">Descargar JSON</button>
</div>
<script>
// Insertamos aquí el JSON como cadena
var jsonContent = {json_string};

// Al pulsar el botón, generamos una data URL y forzamos la descarga
function downloadJSON() {{
    // Convertimos el objeto en una cadena JSON
    const jsonStr = JSON.stringify(jsonContent, null, 4);

    // Creamos la data URL
    const dataUrl = "data:application/json;charset=utf-8," + encodeURIComponent(jsonStr);

    // Creamos un enlace temporal
    const link = document.createElement('a');
    link.setAttribute('href', dataUrl);
    link.setAttribute('download', 'convertor_excel.json');
    link.style.display = 'none';
    document.body.appendChild(link);

    // Disparamos el click para descargar
    link.click();

    // Eliminamos el enlace temporal
    document.body.removeChild(link);
}}
</script>
"""

# 12. Crear el HTML final con la tabla y el botón de descarga
canvas_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    
    <title>Tabla Editable de Validaciones</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
        }}
        table {{
            border-collapse: collapse;
            width: 90%;
            margin: 20px auto;
        }}
        th, td {{
            border: 1px solid #ccc;
            padding: 8px;
            text-align: center;
        }}
        th {{
            background-color: #f2f2f2;
        }}
        select, input[type="text"] {{
            width: 100%;
            box-sizing: border-box;
            padding: 4px;
        }}
        button {{
            padding: 10px 20px;
            font-size: 16px;
            cursor: pointer;
        }}
    </style>
</head>
<body>

    <h2 style="text-align:center;">Tabla Editable de Validaciones</h2>
    <div class="canvas-container">
        {table_html}
        {download_button}
    </div>
</body>
</html>
"""

# 13. Guardar el HTML en un archivo
html_file = os.path.join(current_dir, "pivot_validaciones_editable.html")
with open(html_file, "w", encoding="utf-8") as f:
    f.write(canvas_html)

print(f"JSON generado y guardado en '{json_file}'")
print(f"Canvas HTML creado y guardado en '{html_file}'")
