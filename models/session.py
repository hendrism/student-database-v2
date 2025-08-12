from datetime import datetime, date, time
from sqlalchemy.ext.hybrid import hybrid_property
from . import db
from .student import AuditMixin

class Session(db.Model, AuditMixin):
    """Session model with comprehensive tracking."""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    session_type = db.Column(db.String(50), default='Individual', nullable=False)
    status = db.Column(db.String(50), default='Scheduled', nullable=False)
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    
    # Relationships
    student = db.relationship('Student', back_populates='sessions')
    
    @hybrid_property
    def duration_minutes(self):
        """Calculate session duration in minutes."""
        if self.start_time and self.end_time:
            start_datetime = datetime.combine(date.today(), self.start_time)
            end_datetime = datetime.combine(date.today(), self.end_time)
            return int((end_datetime - start_datetime).total_seconds() / 60)
        return 0
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'session_date': self.session_date.isoformat(),
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'session_type': self.session_type,
            'status': self.status,
            'location': self.location,
            'notes': self.notes,
            'duration_minutes': self.duration_minutes,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class TrialLog(db.Model, AuditMixin):
    """Enhanced trial log with comprehensive tracking."""
    
    __tablename__ = 'trial_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    objective_id = db.Column(db.Integer, db.ForeignKey('objectives.id'), nullable=True)
    session_date = db.Column(db.Date, default=date.today, nullable=False)
    
    # New support level system
    independent = db.Column(db.Integer, default=0)
    minimal_support = db.Column(db.Integer, default=0)
    moderate_support = db.Column(db.Integer, default=0)
    maximal_support = db.Column(db.Integer, default=0)
    incorrect = db.Column(db.Integer, default=0)
    
    # Legacy support system (for migration compatibility)
    correct_no_support = db.Column(db.Integer, default=0)
    correct_visual_cue = db.Column(db.Integer, default=0)
    correct_verbal_cue = db.Column(db.Integer, default=0)
    correct_visual_verbal_cue = db.Column(db.Integer, default=0)
    correct_modeling = db.Column(db.Integer, default=0)
    incorrect_legacy = db.Column(db.Integer, default=0)
    
    # Additional tracking
    session_notes = db.Column(db.Text)
    environmental_factors = db.Column(db.String(200))
    
    # Relationships
    student = db.relationship('Student', back_populates='trial_logs')
    objective = db.relationship('Objective', back_populates='trial_logs')
    
    def uses_new_system(self):
        """Return True if using new support level system."""
        return any(
            (getattr(self, attr) or 0) > 0
            for attr in ['independent', 'minimal_support', 'moderate_support', 'maximal_support']
        )
    
    def uses_legacy_system(self):
        """Return True if using legacy support system."""
        return any(
            (getattr(self, attr) or 0) > 0
            for attr in ['correct_no_support', 'correct_visual_cue', 'correct_verbal_cue',
                        'correct_visual_verbal_cue', 'correct_modeling']
        )
    
    @hybrid_property
    def total_trials(self):
        """Total trials using legacy system."""
        return (self.correct_no_support + self.correct_visual_cue + 
                self.correct_verbal_cue + self.correct_visual_verbal_cue + 
                self.correct_modeling + (self.incorrect_legacy or 0))
    
    def total_trials_new(self):
        """Total trials using new system."""
        return (self.independent + self.minimal_support + 
                self.moderate_support + self.maximal_support + self.incorrect)
    
    @hybrid_property
    def independence_percentage(self):
        """Calculate independence percentage for new system."""
        total = self.total_trials_new()
        return round((self.independent / total) * 100, 1) if total > 0 else 0
    
    @hybrid_property
    def success_percentage(self):
        """Calculate percentage of successful trials (all support levels)."""
        total = self.total_trials_new()
        successful = (self.independent + self.minimal_support + 
                     self.moderate_support + self.maximal_support)
        return round((successful / total) * 100, 1) if total > 0 else 0
    
    def percent_correct_up_to(self, support_level):
        """Return percent correct at or below the specified support level."""
        level_order = ['independent', 'minimal_support', 'moderate_support', 'maximal_support']
        total = self.total_trials_new()
        if total == 0 or support_level not in level_order:
            return 0.0
        idx = level_order.index(support_level) + 1
        correct_sum = sum((getattr(self, lvl) or 0) for lvl in level_order[:idx])
        return round((correct_sum / total) * 100, 1)
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'objective_id': self.objective_id,
            'session_date': self.session_date.isoformat(),
            'independent': self.independent,
            'minimal_support': self.minimal_support,
            'moderate_support': self.moderate_support,
            'maximal_support': self.maximal_support,
            'incorrect': self.incorrect,
            'total_trials': self.total_trials_new(),
            'independence_percentage': self.independence_percentage,
            'success_percentage': self.success_percentage,
            'session_notes': self.session_notes,
            'environmental_factors': self.environmental_factors,
            'uses_new_system': self.uses_new_system(),
            'uses_legacy_system': self.uses_legacy_system(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }