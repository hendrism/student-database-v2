"""Database models for Student Database v2.0."""

from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string

# Initialize SQLAlchemy
db = SQLAlchemy()

class User(db.Model):
    """User model for authentication."""
    
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='therapist')
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime)
    
    # Privacy fields
    access_level = db.Column(db.String(20), default='standard', nullable=False)
    data_retention_consent = db.Column(db.Boolean, default=True, nullable=False)
    
    def set_password(self, password):
        """Set password hash."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash."""
        return check_password_hash(self.password_hash, password)
    
    def generate_token(self):
        """Generate authentication token."""
        # Simple token for demo - use JWT in production
        return secrets.token_urlsafe(32)
    
    @staticmethod
    def verify_token(token):
        """Verify authentication token."""
        # Simplified verification - implement proper JWT verification
        return User.query.filter_by(is_active=True).first()
    
    def has_permission(self, permission):
        """Check if user has specific permission."""
        # Implement role-based permissions
        admin_permissions = ['create', 'read', 'update', 'delete', 'admin']
        therapist_permissions = ['create', 'read', 'update']
        
        if self.role == 'admin':
            return permission in admin_permissions
        elif self.role == 'therapist':
            return permission in therapist_permissions
        
        return False
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }

class Student(db.Model):
    """Student model for storing student information."""
    
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(20), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    date_of_birth = db.Column(db.Date)
    grade_level = db.Column(db.String(10))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    
    # Emergency contact
    emergency_contact_name = db.Column(db.String(100))
    emergency_contact_phone = db.Column(db.String(20))
    emergency_contact_relationship = db.Column(db.String(50))
    
    # Therapy information
    diagnosis = db.Column(db.Text)
    therapy_start_date = db.Column(db.Date)
    
    # Privacy and compliance
    consent_given = db.Column(db.Boolean, default=False, nullable=False)
    consent_date = db.Column(db.Date)
    data_sharing_consent = db.Column(db.Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    goals = db.relationship('Goal', backref='student', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('Session', backref='student', lazy=True, cascade='all, delete-orphan')
    trial_logs = db.relationship('TrialLog', backref='student', lazy=True, cascade='all, delete-orphan')
    
    def generate_student_id(self):
        """Generate unique student ID."""
        if not self.student_id:
            # Generate a unique student ID
            year = datetime.now().year
            random_part = ''.join(secrets.choice(string.digits) for _ in range(4))
            self.student_id = f"ST{year}{random_part}"
    
    @property
    def full_name(self):
        """Get full name."""
        return f"{self.first_name} {self.last_name}"
    
    @property
    def age(self):
        """Calculate age from date of birth."""
        if self.date_of_birth:
            today = datetime.now().date()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'date_of_birth': self.date_of_birth.isoformat() if self.date_of_birth else None,
            'age': self.age,
            'grade_level': self.grade_level,
            'email': self.email,
            'phone': self.phone,
            'emergency_contact_name': self.emergency_contact_name,
            'emergency_contact_phone': self.emergency_contact_phone,
            'emergency_contact_relationship': self.emergency_contact_relationship,
            'diagnosis': self.diagnosis,
            'therapy_start_date': self.therapy_start_date.isoformat() if self.therapy_start_date else None,
            'consent_given': self.consent_given,
            'consent_date': self.consent_date.isoformat() if self.consent_date else None,
            'data_sharing_consent': self.data_sharing_consent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Goal(db.Model):
    """Goal model for student therapy goals."""
    
    __tablename__ = 'goals'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    goal_text = db.Column(db.Text, nullable=False)
    target_date = db.Column(db.Date)
    status = db.Column(db.String(20), default='active', nullable=False)  # active, completed, discontinued
    priority = db.Column(db.Integer, default=1)  # 1=high, 2=medium, 3=low
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    objectives = db.relationship('Objective', backref='goal', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'goal_text': self.goal_text,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Objective(db.Model):
    """Objective model for specific measurable objectives under goals."""
    
    __tablename__ = 'objectives'
    
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey('goals.id'), nullable=False)
    objective_text = db.Column(db.Text, nullable=False)
    mastery_criteria = db.Column(db.Text)  # e.g., "80% accuracy over 3 consecutive sessions"
    status = db.Column(db.String(20), default='active', nullable=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trial_logs = db.relationship('TrialLog', backref='objective', lazy=True)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'goal_id': self.goal_id,
            'objective_text': self.objective_text,
            'mastery_criteria': self.mastery_criteria,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class Session(db.Model):
    """Session model for therapy sessions."""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_date = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer)
    session_type = db.Column(db.String(50))  # individual, group, assessment
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='scheduled')  # scheduled, completed, cancelled
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    trial_logs = db.relationship('TrialLog', backref='session', lazy=True)
    soap_notes = db.relationship('SOAPNote', backref='session', lazy=True)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'user_id': self.user_id,
            'session_date': self.session_date.isoformat() if self.session_date else None,
            'duration_minutes': self.duration_minutes,
            'session_type': self.session_type,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class TrialLog(db.Model):
    """Trial log model for recording student progress data."""
    
    __tablename__ = 'trial_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    objective_id = db.Column(db.Integer, db.ForeignKey('objectives.id'))
    
    # Trial data
    trial_number = db.Column(db.Integer, nullable=False)
    prompt_type = db.Column(db.String(50))  # independent, gestural, verbal, physical
    response = db.Column(db.String(10), nullable=False)  # correct, incorrect, prompted
    notes = db.Column(db.Text)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'session_id': self.session_id,
            'objective_id': self.objective_id,
            'trial_number': self.trial_number,
            'prompt_type': self.prompt_type,
            'response': self.response,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class SOAPNote(db.Model):
    """SOAP Note model for clinical documentation."""
    
    __tablename__ = 'soap_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'), nullable=False)
    
    # SOAP components
    subjective = db.Column(db.Text)  # What client/family reports
    objective = db.Column(db.Text)   # Observable data, trial results
    assessment = db.Column(db.Text)  # Clinical judgment
    plan = db.Column(db.Text)        # Next steps, recommendations
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary for JSON response."""
        return {
            'id': self.id,
            'session_id': self.session_id,
            'subjective': self.subjective,
            'objective': self.objective,
            'assessment': self.assessment,
            'plan': self.plan,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }