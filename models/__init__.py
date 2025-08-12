from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so they're available when importing from models
from .student import Student, Goal, Objective
from .session import Session, TrialLog
from .soap import SOAPNote
# Import User from auth package (moved from models.auth to avoid duplication)
from auth.models import User