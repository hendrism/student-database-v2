# routes/__init__.py
from datetime import datetime

from flask import Blueprint

def register_blueprints(app):
    """Register all blueprints with the application."""
    
    # Import blueprints from their correct locations
    from .api import api_bp
    from .auth import auth_bp
    from .students import students_bp
    from .sessions import sessions_bp
    from .soap import soap_bp
    
    # Register API blueprints
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(students_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(soap_bp)
    
    # Handle missing reports blueprint gracefully
    try:
        from .reports import reports_bp
        app.register_blueprint(reports_bp, url_prefix='/api/reports')
    except ImportError:
        # Create a placeholder if reports module is not ready
        placeholder_bp = Blueprint('reports', __name__)
        
        @placeholder_bp.route('/')
        def reports_placeholder():
            return {
                'message': 'Reports module is being developed',
                'status': 'placeholder'
            }, 200
        
        app.register_blueprint(placeholder_bp, url_prefix='/api/reports')
    
    # Simple health check route
    @app.route('/')
    def index():
        return {
            'message': 'Student Database v2.0 API',
            'status': 'running',
            'version': '2.0.0'
        }
    
    @app.route('/health')
    def health():
        """Health check endpoint."""
        return {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0',
        }
