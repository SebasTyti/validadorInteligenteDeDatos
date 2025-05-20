from flask import Blueprint, jsonify, request, send_file
import json
import os
from sqlalchemy import create_engine, text

# Configura el blueprint
json_routes = Blueprint("json_routes", __name__)

# Conexión a la base de datos (ajusta la cadena de conexión según tu configuración)
DATABASE_URL = "mssql+pymssql://usuario:contraseña@servidor/nombre_base_datos"
engine = create_engine(DATABASE_URL)

@json_routes.route("/get_regex", methods=["GET"])
def get_regex():
    """Obtiene la expresión regular de la base de datos según el nombre."""
    nombre = request.args.get("nombre")
    
    if not nombre:
        return jsonify({"error": "Debe proporcionar un nombre de expresión regular"}), 400

    query = text("SELECT Expresion_Regular FROM dbo.ExpresionesRegulares WHERE nombre_ExpresionRegular = :nombre")
    
    with engine.connect() as connection:
        result = connection.execute(query, {"nombre": nombre}).fetchone()

    if result:
        return jsonify({"expresion_regular": result[0]})
    else:
        return jsonify({"error": "Expresión regular no encontrada"}), 404

@json_routes.route("/download_json", methods=["GET"])
def download_json():
    """Genera y envía un archivo JSON con la expresión regular seleccionada."""
    nombre = request.args.get("nombre")
    
    if not nombre:
        return jsonify({"error": "Debe proporcionar un nombre de expresión regular"}), 400

    query = text("SELECT Expresion_Regular FROM dbo.ExpresionesRegulares WHERE nombre_ExpresionRegular = :nombre")

    with engine.connect() as connection:
        result = connection.execute(query, {"nombre": nombre}).fetchone()

    if not result:
        return jsonify({"error": "Expresión regular no encontrada"}), 404

    regex_data = {
        "nombre": nombre,
        "expresion_regular": result[0]
    }

    json_filename = f"{nombre}.json"
    json_path = os.path.join(os.getcwd(), json_filename)

    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(regex_data, json_file, indent=4, ensure_ascii=False)

    return send_file(json_path, as_attachment=True)

