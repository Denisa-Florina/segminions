from flask import Flask
from flask_cors import CORS
import os
import sys 

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_app():
    app = Flask(__name__)
    

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    

    app.config['SESSION_COOKIE_SAMESITE'] = 'None' 
    app.config['SESSION_COOKIE_SECURE'] = False   
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    CORS(app, supports_credentials=True, origins=["http://localhost:3000"])
    

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    

    from backend.api.routes.authRoutes import auth_bp
    from backend.api.routes.patientRoutes import patient_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp)
    

    @app.route('/api/health')
    def health_check():
        return {'status': 'healthy', 'message': 'MedSeg AI Backend is running'}, 200
    
    return app


if __name__ == '__main__':
    app = create_app()
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )