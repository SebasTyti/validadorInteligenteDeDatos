from app.routeDIv import app  #  ¡Importa la instancia de Flask desde routeDIv.py!
import os

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=True, host='0.0.0.0', port=port)