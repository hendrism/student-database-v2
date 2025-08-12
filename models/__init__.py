from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so they're available when importing from models
from .student import Student, Goal, Objective
from .session import Session, TrialLog
from .soap import SOAPNote