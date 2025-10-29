"""
Artifact Server - Lightweight Flask server to serve artifacts
"""
import os
import threading
from flask import Flask, send_from_directory, send_file

app = Flask(__name__)

# Optional CORS support
try:
    from flask_cors import CORS
    CORS(app)
except ImportError:
    # CORS not installed, but server will still work locally
    pass

# Prevent Flask logging to console
import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)


def _get_artifacts_dir() -> str:
    """Get the artifacts directory path"""
    _DIR = os.path.dirname(os.path.abspath(__file__))
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(_DIR))
    return os.path.join(_PROJECT_ROOT, "data", "artifacts")


@app.route('/artifacts/<path:filename>')
def serve_artifact(filename):
    """Serve artifact files"""
    # Extract type and actual filename from path
    # e.g., "pr/PR-1234.html" -> type="pr", file="PR-1234.html"
    parts = filename.split('/')
    if len(parts) != 2:
        return "Invalid path", 404
    
    artifact_type, file = parts
    artifacts_dir = _get_artifacts_dir()
    type_dir = os.path.join(artifacts_dir, artifact_type)
    
    if not os.path.exists(type_dir):
        return f"Artifact type '{artifact_type}' not found", 404
    
    file_path = os.path.join(type_dir, file)
    if not os.path.exists(file_path):
        return f"File not found", 404
    
    return send_file(file_path)


def start_server(host='localhost', port=8000):
    """Start the artifact server in a background thread"""
    server_thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True
    )
    server_thread.start()
    print(f"[ARTIFACT SERVER] Started at http://{host}:{port}/artifacts/")

