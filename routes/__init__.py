from flask import Blueprint
import datetime


# Central blueprint definitions used across route modules
bp_api = Blueprint('api', __name__)
bp_auth = Blueprint('auth', __name__)


def register_blueprints(app):
    """Register all blueprints with the application."""

    # Import modules so their routes are attached to the shared blueprints
    from . import api as _api, auth as _auth  # noqa: F401
    from .students import students_bp
    from .sessions import sessions_bp
    from .soap import soap_bp
    from .calendar import calendar_bp

    # Register shared blueprints
    app.register_blueprint(bp_api, url_prefix='/api')
    app.register_blueprint(bp_auth, url_prefix='/auth')
    app.register_blueprint(students_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(soap_bp)
    app.register_blueprint(calendar_bp)

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

    # Smoke-test endpoints for quick blueprint verification
    @app.get('/health/api')
    def api_smoke():
        return {'status': 'ok'}

    @app.get('/health/auth')
    def auth_smoke():
        return {'status': 'ok'}

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
            'timestamp': datetime.datetime.utcnow().isoformat(),
            'version': '2.0.0'
        }

