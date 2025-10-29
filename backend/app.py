from flask import Flask
from flask_cors import CORS
import os

def create_app():
    app = Flask(__name__)
    

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max file size
    

    CORS(app, supports_credentials=True)
    

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