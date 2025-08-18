# config/settings.py - FIXED VERSION
import os
import secrets
from datetime import timedelta
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent.absolute()

class Config:
    """Base configuration class."""
    
    # Security settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SECURITY_PASSWORD_SALT = os.environ.get('SECURITY_PASSWORD_SALT') or secrets.token_hex(16)
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        f'sqlite:///{BASE_DIR}/instance/student_database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ECHO = False
    
    # Session configuration
    SESSION_TYPE = 'filesystem'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # JWT configuration
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY') or secrets.token_hex(32)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    
    # Privacy settings
    DATA_RETENTION_DAYS = int(os.environ.get('DATA_RETENTION_DAYS', 2555))  # 7 years
    ANONYMIZE_AFTER_DAYS = int(os.environ.get('ANONYMIZE_AFTER_DAYS', 365))  # 1 year
    ENABLE_DATA_EXPORT = os.environ.get('ENABLE_DATA_EXPORT', 'true').lower() == 'true'
    
    # Rate limiting
    RATELIMIT_STORAGE_URL = os.environ.get('REDIS_URL') or 'memory://'
    RATELIMIT_DEFAULT = "1000 per hour"
    
    # Email configuration (optional)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    
    # Backup configuration
    BACKUP_ENABLED = os.environ.get('BACKUP_ENABLED', 'true').lower() == 'true'
    BACKUP_SCHEDULE = os.environ.get('BACKUP_SCHEDULE', '0 2 * * *')  # 2 AM daily
    BACKUP_RETENTION_DAYS = int(os.environ.get('BACKUP_RETENTION_DAYS', 30))
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration."""
        # Create instance folder if it doesn't exist
        instance_path = Path(app.instance_path)
        instance_path.mkdir(exist_ok=True)
        
        # Create logs folder
        log_path = instance_path / 'logs'
        log_path.mkdir(exist_ok=True)
        
        # Create backups folder
        backup_path = instance_path / 'backups'
        backup_path.mkdir(exist_ok=True)

class DevelopmentConfig(Config):
    """Development configuration."""
    
    DEBUG = True
    TESTING = False
    
    # Less strict security in development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    
    # More verbose logging
    SQLALCHEMY_ECHO = True
    
    @staticmethod
    def init_app(app):
        """Development-specific initialization."""
        Config.init_app(app)
        
        # Log to console in development
        import logging
        logging.basicConfig(level=logging.DEBUG)

class TestingConfig(Config):
    """Testing configuration."""
    
    TESTING = True
    DEBUG = True
    
    # Use in-memory database for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Faster password hashing for tests
    BCRYPT_LOG_ROUNDS = 4
    
    @staticmethod
    def init_app(app):
        """Testing-specific initialization."""
        Config.init_app(app)

class ProductionConfig(Config):
    """Production configuration."""
    
    DEBUG = False
    TESTING = False
    
    # Enhanced security in production
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Strict'
    
    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        # Fix for SQLAlchemy compatibility
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    @staticmethod
    def init_app(app):
        """Production-specific initialization."""
        Config.init_app(app)
        
        # Log to file in production
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            log_path = Path(app.instance_path) / 'logs'
            log_path.mkdir(exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_path / 'app.log',
                maxBytes=10240000,  # 10MB
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Student Database startup')

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}