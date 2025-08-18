from datetime import datetime, date
from sqlalchemy.ext.hybrid import hybrid_property
from . import db

class Session(db.Model):
    """Session model for scheduling and tracking appointments."""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_date = db.Column(db.Date, default=date.today, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    # Session details
    session_type = db.Column(db.String(50), default='Individual')
    status = db.Column(db.String(50), default='Scheduled')
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    event_type = db.Column(db.String(50), default='Session')
    plan_notes = db.Column(db.Text)
    
    # Billing information
    billing_code = db.Column(db.String(20))
    units = db.Column(db.Integer)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='sessions')
    soap_notes = db.relationship('SOAPNote', back_populates='session', cascade='all, delete-orphan')
    
    @hybrid_property
    def duration_minutes(self):
        """Calculate session duration in minutes."""
        if self.start_time and self.end_time:
            start = datetime.combine(date.today(), self.start_time)
            end = datetime.combine(date.today(), self.end_time)
            return int((end - start).total_seconds() / 60)
        return 0
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'session_date': self.session_date.isoformat(),
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'session_type': self.session_type,
            'status': self.status,
            'location': self.location,
            'notes': self.notes,
            'event_type': self.event_type,
            'plan_notes': self.plan_notes,
            'duration_minutes': self.duration_minutes,
            'billing_code': self.billing_code,
            'units': self.units
        }

    def to_calendar_event(self):
        """Convert session to calendar event representation."""
        start_dt = None
        end_dt = None
        if self.session_date and self.start_time:
            start_dt = datetime.combine(self.session_date, self.start_time)
        if self.session_date and self.end_time:
            end_dt = datetime.combine(self.session_date, self.end_time)

        return {
            'id': self.id,
            'student_id': self.student_id,
            'title': self.student.display_name if self.student else f'Session {self.id}',
            'start': start_dt.isoformat() if start_dt else None,
            'end': end_dt.isoformat() if end_dt else None,
            'event_type': self.event_type,
            'session_type': self.session_type,
            'status': self.status,
            'location': self.location,
            'notes': self.notes,
            'plan_notes': self.plan_notes,
        }

class TrialLog(db.Model):
    """Trial log for tracking student progress."""
    
    __tablename__ = 'trial_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    objective_id = db.Column(db.Integer, db.ForeignKey('objectives.id'))
    session_date = db.Column(db.Date, default=date.today, nullable=False)
    
    # New support level system
    independent = db.Column(db.Integer, default=0)
    minimal_support = db.Column(db.Integer, default=0)
    moderate_support = db.Column(db.Integer, default=0)
    maximal_support = db.Column(db.Integer, default=0)
    incorrect = db.Column(db.Integer, default=0)
    
    # Legacy support system (for migration)
    correct_no_support = db.Column(db.Integer, default=0)
    correct_visual_cue = db.Column(db.Integer, default=0)
    correct_verbal_cue = db.Column(db.Integer, default=0)
    correct_visual_verbal_cue = db.Column(db.Integer, default=0)
    correct_modeling = db.Column(db.Integer, default=0)
    incorrect_legacy = db.Column(db.Integer, default=0)
    
    # Additional tracking
    session_notes = db.Column(db.Text)
    environmental_factors = db.Column(db.String(200))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='trial_logs')
    objective = db.relationship('Objective', back_populates='trial_logs')
    
    @property
    def total_trials(self):
        """Calculate total number of trials."""
        if self.uses_new_system():
            return sum([
                self.independent or 0,
                self.minimal_support or 0,
                self.moderate_support or 0,
                self.maximal_support or 0,
                self.incorrect or 0
            ])
        else:
            return sum([
                self.correct_no_support or 0,
                self.correct_visual_cue or 0,
                self.correct_verbal_cue or 0,
                self.correct_visual_verbal_cue or 0,
                self.correct_modeling or 0,
                self.incorrect_legacy or 0
            ])
    
    @property
    def independence_percentage(self):
        """Calculate independence percentage."""
        total = self.total_trials
        if total == 0:
            return 0
        
        if self.uses_new_system():
            return round((self.independent / total) * 100, 1)
        else:
            return round((self.correct_no_support / total) * 100, 1)
    
    @property
    def success_percentage(self):
        """Calculate success percentage."""
        total = self.total_trials
        if total == 0:
            return 0
        
        if self.uses_new_system():
            incorrect = self.incorrect or 0
            return round(((total - incorrect) / total) * 100, 1)
        else:
            incorrect = self.incorrect_legacy or 0
            return round(((total - incorrect) / total) * 100, 1)
    
    def uses_new_system(self):
        """Check if using new support system."""
        return any([
            self.independent,
            self.minimal_support,
            self.moderate_support,
            self.maximal_support
        ])
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'student_id': self.student_id,
            'objective_id': self.objective_id,
            'session_date': self.session_date.isoformat(),
            'total_trials': self.total_trials,
            'independence_percentage': self.independence_percentage,
            'success_percentage': self.success_percentage,
            'session_notes': self.session_notes,
            'environmental_factors': self.environmental_factors,
            'support_levels': {
                'independent': self.independent,
                'minimal_support': self.minimal_support,
                'moderate_support': self.moderate_support,
                'maximal_support': self.maximal_support,
                'incorrect': self.incorrect
            }
        }
