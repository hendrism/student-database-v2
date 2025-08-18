"""Flask application entry point for the Student Database v2.0."""

import os
import logging
from pathlib import Path
from flask import Flask
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv

# Import your custom modules
from config.settings import config
from extensions import db

def create_app(config_name=None):
    """Application factory pattern for better organization."""

    # Load environment variables from .env if present
    load_dotenv()
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Ensure instance directory exists FIRST
    instance_path = Path(app.instance_path)
    instance_path.mkdir(exist_ok=True)
    print(f"Instance path: {instance_path}")
    
    # Load configuration
    app.config.from_object(config.get(config_name, config['default']))
    config[config_name].init_app(app)

    # === AUTH TOGGLE: read env LAST and set config ===
    raw_flag = os.getenv("AUTH_DISABLED")
    flag = str(raw_flag).lower() in ("1", "true", "yes", "on")
    app.config["AUTH_DISABLED"] = flag

    # Helpful logs
    print("ENV AUTH_DISABLED =", raw_flag)
    if flag:
        print("⚠️  AUTH_DISABLED is ON - auth checks are bypassed (dev only)")
    else:
        print("🔒 AUTH_DISABLED is OFF - normal auth required")
    
    # Initialize extensions
    db.init_app(app)
    Migrate(app, db)
    CORS(app)  # Enable CORS for frontend
    
    # Register blueprints (after ensuring they exist)
    try:
        from routes import register_blueprints
        register_blueprints(app)
    except ImportError:
        print("Warning: routes module not found, skipping blueprint registration")
    
    # Setup logging
    setup_logging(app)
    
    # Setup error handlers
    setup_error_handlers(app)
    
    # Create database tables - but only if we're not in the reloader process
    if not os.environ.get('WERKZEUG_RUN_MAIN'):
        with app.app_context():
            # Import models to ensure they're registered
            try:
                import models  # noqa: F401
                print("Models imported successfully")
            except ImportError as e:
                print(f"Warning: Could not import all models: {e}")
            
            # Create all database tables
            try:
                db.create_all()
                print("Database tables created successfully")
            except Exception as e:
                print(f"Error creating database tables: {e}")
                # Don't raise here, let the app continue
            
            # Initialize default data if needed
            initialize_default_data()
    
    return app

def setup_logging(app):
    """Configure logging."""
    if not app.debug:
        # Setup file logging for production
        log_dir = Path(app.instance_path) / 'logs'
        log_dir.mkdir(exist_ok=True)
        
        handler = logging.FileHandler(log_dir / 'app.log')
        handler.setLevel(logging.INFO)
        
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        handler.setFormatter(formatter)
        
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)

def setup_error_handlers(app):
    """Setup error handling."""
    
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Resource not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return {'error': 'Internal server error'}, 500

def initialize_default_data():
    """Initialize default data if database is empty."""
    # Check if we need to create default data
    try:
        from models import User
        if User.query.first() is not None:
            return
        print("Database is empty, run scripts/create_admin.py to create admin user")
    except Exception as e:
        print(f"Could not check for existing users: {e}")

# Create app instance
app = create_app()

if __name__ == '__main__':
    # Development server - disable reloader to avoid SQLite conflicts
    print("🚀 Starting Student Database v2.0...")
    print("📍 Server will be available at: http://127.0.0.1:5000")
    print("📍 API Health check: http://127.0.0.1:5000/api/v1/health")
    print("⚠️  Debug reloader disabled to avoid SQLite conflicts")
    
    app.run(
        debug=True, 
        host='127.0.0.1', 
        port=5000,
        use_reloader=False  # This fixes the SQLite conflict
    )
    
