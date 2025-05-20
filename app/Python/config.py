import os
import json
import urllib
import pyodbc

# Obtener la ruta absoluta del archivo secrets.json, basado en la ubicación del script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
secrets_path = os.path.join(BASE_DIR, 'secrets.json')

# Leer las credenciales desde el archivo secrets.json
with open(secrets_path) as f:
    secrets = json.load(f)

class Config:
    DB_CONFIG = {
        'server': 'sqls-ur-datamining-dev.database.windows.net',
        'database': 'DB_ValidadorArchivos',
        'driver': 'ODBC Driver 18 for SQL Server',
        'authentication': 'ActiveDirectoryPassword',
        'username': secrets['db_user'],
        'password': secrets['db_password'],
    }

    UPLOAD_FOLDER = 'uploads'
    VALIDATED_FOLDER = 'validated'
    DIFFERENT_FOLDER = 'different'
    SECRET_KEY = 'supersecretykey'

    @staticmethod
    def get_sqlalchemy_uri():
        config = Config.DB_CONFIG
        params = urllib.parse.quote_plus(
            f"Driver={config['driver']};"
            f"Server={config['server']};"
            f"Database={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']};"
            f"Authentication={config['authentication']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
        )
        return f"mssql+pyodbc:///?odbc_connect={params}"
    
    @staticmethod
    def get_pyodbc_connection():
        config = Config.DB_CONFIG
        conn_str = (
            f"Driver={config['driver']};"
            f"Server={config['server']};"
            f"Database={config['database']};"
            f"UID={config['username']};"
            f"PWD={config['password']};"
            f"Authentication={config['authentication']};"
            f"Encrypt=yes;"
            f"TrustServerCertificate=no;"
        )
        return pyodbc.connect(conn_str)
