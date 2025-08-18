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
        self.first_name = "Student"
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

# Add these to models/student.py after the Student model

class Goal(db.Model):
    """Goal model for student objectives."""
    
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # Goal details
    description = db.Column(db.Text, nullable=False)
    target_date = db.Column(db.Date)
    completion_criteria = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    
    # Progress tracking
    progress_percentage = db.Column(db.Float, default=0.0)
    last_reviewed = db.Column(db.Date)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='goals')
    objectives = db.relationship('Objective', back_populates='goal', cascade='all, delete-orphan')
    
    def calculate_progress(self):
        """Calculate overall goal progress from objectives."""
        if not self.objectives:
            return 0.0
        
        active_objectives = [obj for obj in self.objectives if obj.active]
        if not active_objectives:
            return 0.0
        
        total_progress = sum(obj.current_progress or 0 for obj in active_objectives)
        return round(total_progress / len(active_objectives), 1)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'description': self.description,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'completion_criteria': self.completion_criteria,
            'active': self.active,
            'progress_percentage': self.calculate_progress(),
            'last_reviewed': self.last_reviewed.isoformat() if self.last_reviewed else None,
            'objectives_count': len(self.objectives),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Objective(db.Model):
    """Objective model for specific measurable targets."""
    
    __tablename__ = 'objectives'
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    
    # Objective details
    description = db.Column(db.Text, nullable=False)
    accuracy_target = db.Column(db.String(50))  # e.g., "80% accuracy"
    notes = db.Column(db.Text)
    active = db.Column(db.Boolean, default=True)
    
    # Progress tracking
    current_progress = db.Column(db.Float, default=0.0)
    baseline = db.Column(db.Float)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    goal = db.relationship('Goal', back_populates='objectives')
    trial_logs = db.relationship('TrialLog', back_populates='objective')
    
    def calculate_recent_progress(self, days=30):
        """Calculate progress from recent trial logs."""
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)
        
        recent_logs = [log for log in self.trial_logs 
                      if log.session_date >= cutoff_date]
        
        if not recent_logs:
            return self.current_progress or 0.0
        
        # Average independence percentage from recent logs
        avg_independence = sum(log.independence_percentage for log in recent_logs) / len(recent_logs)
        return round(avg_independence, 1)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'description': self.description,
            'accuracy_target': self.accuracy_target,
            'notes': self.notes,
            'active': self.active,
            'current_progress': self.calculate_recent_progress(),
            'baseline': self.baseline,
            'trial_logs_count': len(self.trial_logs),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }