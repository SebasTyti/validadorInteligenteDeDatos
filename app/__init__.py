# filepath: app/__init__.py
from flask import Flask
from app.Python.config import Config
import os

# Inicializa la aplicación Flask
app = Flask(__name__)
app.config.from_object(Config)

# Crear las carpetas si no existen
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

if not os.path.exists(app.config['VALIDATED_FOLDER']):
    os.makedirs(app.config['VALIDATED_FOLDER'])

if not os.path.exists(app.config['DIFFERENT_FOLDER']):
    os.makedirs(app.config['DIFFERENT_FOLDER'])

# Importa las rutas al final para evitar importaciones circulares
from app import routeDIv