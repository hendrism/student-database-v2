from flask import Blueprint

def register_blueprints(app):
    """Register all blueprints with the application."""
    
    from .api import api_bp
    from .auth import auth_bp
    
    # Register API blueprints
    app.register_blueprint(api_bp, url_prefix='/api/v1')
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    # Simple health check route
    @app.route('/')
    def index():
        return {
            'message': 'Student Database v2.0 API',
            'status': 'running',
            'version': '2.0.0'
        }