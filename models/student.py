from datetime import datetime, date
from sqlalchemy.ext.hybrid import hybrid_property
from . import db
import uuid

class AuditMixin:
    """Mixin for audit trail functionality."""
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

class PrivacyMixin:
    """Mixin for privacy and data protection features."""
    
    anonymized = db.Column(db.Boolean, default=False, nullable=False)
    anonymized_at = db.Column(db.DateTime)
    data_retention_until = db.Column(db.DateTime)
    
    def anonymize(self):
        """Anonymize sensitive data while preserving analytics."""
        self.anonymized = True
        self.anonymized_at = datetime.utcnow()

class Student(db.Model, AuditMixin, PrivacyMixin):
    """Student model with privacy protection."""
    
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Basic information - will be anonymized
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    preferred_name = db.Column(db.String(100))
    pronouns = db.Column(db.String(50))
    
    # Non-sensitive data for analytics
    grade_level = db.Column(db.String(20))
    monthly_services = db.Column(db.Integer)
    active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Unique anonymous identifier for analytics
    anonymous_id = db.Column(db.String(32), unique=True)
    
    # Relationships
    goals = db.relationship('Goal', back_populates='student', cascade='all, delete-orphan')
    sessions = db.relationship('Session', back_populates='student', cascade='all, delete-orphan')
    trial_logs = db.relationship('TrialLog', back_populates='student', cascade='all, delete-orphan')
    soap_notes = db.relationship('SOAPNote', back_populates='student', cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.anonymous_id:
            self.anonymous_id = uuid.uuid4().hex
    
    @hybrid_property
    def display_name(self):
        """Return anonymized name if student is anonymized."""
        if self.anonymized:
            return f"Student {self.anonymous_id[:8]}"
        return f"{self.first_name} {self.last_name}"
    
    def anonymize(self):
        """Anonymize student data while preserving educational value."""
        super().anonymize()
        self.first_name = f"Student"
        self.last_name = f"{self.anonymous_id[:8]}"
        self.preferred_name = None
    
    def to_dict(self, include_sensitive=True):
        """Convert to dictionary with privacy controls."""
        data = {
            'id': self.id,
            'grade_level': self.grade_level,
            'monthly_services': self.monthly_services,
            'active': self.active,
            'anonymous_id': self.anonymous_id,
            'goals_count': len([g for g in self.goals if g.active]),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive and not self.anonymized:
            data.update({
                'first_name': self.first_name,
                'last_name': self.last_name,
                'preferred_name': self.preferred_name,
                'pronouns': self.pronouns,
                'display_name': self.display_name
            })
        else:
            data['display_name'] = self.display_name
            
        return data

class Goal(db.Model, AuditMixin):
    """Goal model with enhanced tracking."""
    
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    target_date = db.Column(db.Date)
    completion_criteria = db.Column(db.Text)
    
    # Relationships
    student = db.relationship('Student', back_populates='goals')
    objectives = db.relationship('Objective', back_populates='goal', cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'description': self.description,
            'active': self.active,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completion_criteria': self.completion_criteria,
            'objectives_count': len([o for o in self.objectives if o.active]),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Objective(db.Model, AuditMixin):
    """Objective model with progress tracking."""
    
    __tablename__ = 'objectives'
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    description = db.Column(db.Text, nullable=False)
    accuracy_target = db.Column(db.String(50))
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    goal = db.relationship('Goal', back_populates='objectives')
    trial_logs = db.relationship('TrialLog', back_populates='objective', cascade='all, delete-orphan')
    
    @hybrid_property
    def current_progress(self):
        """Calculate current progress percentage."""
        from datetime import timedelta
        recent_logs = [log for log in self.trial_logs 
                      if (datetime.utcnow().date() - log.session_date).days <= 30]
        
        if not recent_logs:
            return 0
            
        total_trials = sum(log.total_trials_new() for log in recent_logs)
        independent_trials = sum(log.independent for log in recent_logs)
        
        return round((independent_trials / total_trials) * 100, 1) if total_trials > 0 else 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'description': self.description,
            'accuracy_target': self.accuracy_target,
            'notes': self.notes,
            'active': self.active,
            'current_progress': self.current_progress,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }