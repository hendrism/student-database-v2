import os
import logging
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, request, g
from flask_migrate import Migrate
from flask_cors import CORS

# Import your custom modules
from config.settings import config
from models import db
from routes import register_blueprints

def create_app(config_name=None):
    """Application factory pattern for better organization."""
    
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__, instance_relative_config=True)
    
    # Load configuration
    app.config.from_object(config.get(config_name, config['default']))
    config[config_name].init_app(app)
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    CORS(app)  # Enable CORS for frontend
    
    # Register blueprints
    register_blueprints(app)
    
    # Setup logging
    setup_logging(app)
    
    # Setup error handlers
    setup_error_handlers(app)
    
    # Create database tables and instance folder
    with app.app_context():
        # Ensure instance directory exists
        instance_path = Path(app.instance_path)
        instance_path.mkdir(exist_ok=True)
        
        # Import models to create tables
        from models import User, Student, Goal, Objective, TrialLog, Session, SOAPNote
        
        # Create all database tables
        db.create_all()
        
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
    from models import User
    if User.query.first() is not None:
        return
    
    print("Database is empty, run scripts/create_admin.py to create admin user")

# Create app instance
app = create_app()

if __name__ == '__main__':
    # Development server
    app.run(debug=True, host='127.0.0.1', port=5000)