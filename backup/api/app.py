from datetime import datetime
import os
from dotenv import load_dotenv
from flask import Flask, request, jsonify, abort
from werkzeug.utils import secure_filename
from functools import wraps

app = Flask(__name__)

load_dotenv()

# Configuración de autenticación básica
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'admin')

# Directorios para almacenar los archivos
LOGS_DIR = os.getenv('LOGS_DIR', 'logs')
SQL_DIR = os.getenv('SQL_DIR', 'sql')


os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(SQL_DIR, exist_ok=True)

def check_auth(username, password):
    return username == AUTH_USERNAME and password == AUTH_PASSWORD

def authenticate():
    message = {'message': "Authenticate."}
    resp = jsonify(message)
    resp.status_code = 401
    resp.headers['WWW-Authenticate'] = 'Basic realm="Example"'
    return resp

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

def save_file(file, directory):
    filename = secure_filename(file.filename)
    file_path = os.path.join(directory, filename)
    
    if os.path.exists(file_path):
        base, extension = os.path.splitext(filename)
        counter = 2
        while os.path.exists(file_path):
            new_filename = f"{base}-{counter}{extension}"
            file_path = os.path.join(directory, new_filename)
            counter += 1

    file.save(file_path)
    return file_path

@app.route('/upload/log', methods=['POST'])
@requires_auth
def upload_log():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    file_path = save_file(file, LOGS_DIR)
    return jsonify({"message": f"File saved as {file_path}"}), 201

@app.route('/upload/sql', methods=['POST'])
@requires_auth
def upload_sql():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    today = datetime.now().strftime('%Y-%m-%d')

    if not file.filename.startswith(today):
        file.filename = f"{today}-{file.filename}"

    file_path = save_file(file, SQL_DIR)
    return jsonify({"message": f"File saved as {file_path}"}), 201


if __name__ == '__main__':
    host = os.getenv('HOST', '127.0.0.1')
    port = os.getenv('PORT', 5000)
    app.run(debug=True, host=host, port=port)
