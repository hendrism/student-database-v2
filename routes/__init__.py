from flask import Blueprint

def register_blueprints(app):
    """Register all blueprints with the application."""
    
    from .api import api_bp
    from .auth import auth_bp
    from .students import students_bp
    from .sessions import sessions_bp
    from .soap import soap_bp
    
    # Register API blueprints
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Register new feature blueprints
    app.register_blueprint(students_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(soap_bp)
    
    # Reports blueprint temporarily disabled due to pandas/numpy compatibility issues
    # For now, create a simple placeholder
    from flask import Blueprint, jsonify
    placeholder_bp = Blueprint('reports', __name__, url_prefix='/api/reports')
    
    @placeholder_bp.route('/')
    def reports_unavailable():
        return jsonify({
            'message': 'Reports functionality temporarily unavailable',
            'reason': 'pandas/numpy compatibility issues - please check requirements',
            'status': 'placeholder'
        }), 200
    
    app.register_blueprint(placeholder_bp)
    
    # Simple health check route
    @app.route('/')
    def index():
        return {
            'message': 'Student Database v2.0 API',
            'status': 'running',
            'version': '2.0.0'
        }