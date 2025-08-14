# models/session.py - Enhanced with all Event model features
from datetime import datetime, date, time
from sqlalchemy.ext.hybrid import hybrid_property
from . import db
from .student import AuditMixin

class Session(db.Model, AuditMixin):
    """Enhanced session model combining Session + Event functionality."""
    
    __tablename__ = 'sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    
    # Event type classification
    event_type = db.Column(db.String(50), default='Session', nullable=False)
    # Options: Session, Meeting, Assessment, Reminder, Other
    
    session_type = db.Column(db.String(50), default='Individual', nullable=False)
    # Options: Individual, Group, Assessment, Consultation
    
    status = db.Column(db.String(50), default='Scheduled', nullable=False)
    # Options: Scheduled, Completed, Cancelled, No Show, Makeup Needed, Excused Absence
    
    location = db.Column(db.String(100))
    notes = db.Column(db.Text)
    plan_notes = db.Column(db.Text)  # For session planning
    
    # Makeup system
    makeup_for_session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    is_makeup = db.Column(db.Boolean, default=False)
    
    # Billing and compliance
    billable_units = db.Column(db.Numeric(4, 2))
    service_code = db.Column(db.String(20))
    
    # Relationships
    student = db.relationship('Student', back_populates='sessions')
    makeup_session = db.relationship('Session', remote_side=[id], backref='original_session')
    
    @hybrid_property
    def duration_minutes(self):
        """Calculate session duration in minutes."""
        if self.start_time and self.end_time:
            start_datetime = datetime.combine(date.today(), self.start_time)
            end_datetime = datetime.combine(date.today(), self.end_time)
            return int((end_datetime - start_datetime).total_seconds() / 60)
        return 0
    
    @hybrid_property
    def is_therapy_session(self):
        """Check if this is a billable therapy session."""
        return self.event_type == 'Session' and self.session_type in ['Individual', 'Group']
    
    @hybrid_property
    def needs_makeup(self):
        """Check if session needs a makeup."""
        return self.status == 'Makeup Needed' and not self.is_makeup
    
    def create_makeup_session(self, new_date, new_start_time, new_end_time):
        """Create a makeup session for this session."""
        makeup = Session(
            student_id=self.student_id,
            session_date=new_date,
            start_time=new_start_time,
            end_time=new_end_time,
            event_type=self.event_type,
            session_type=self.session_type,
            location=self.location,
            makeup_for_session_id=self.id,
            is_makeup=True,
            notes=f"Makeup for {self.session_date.strftime('%m/%d/%Y')} session"
        )
        db.session.add(makeup)
        return makeup
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'session_date': self.session_date.isoformat(),
            'start_time': self.start_time.strftime('%H:%M'),
            'end_time': self.end_time.strftime('%H:%M'),
            'event_type': self.event_type,
            'session_type': self.session_type,
            'status': self.status,
            'location': self.location,
            'notes': self.notes,
            'plan_notes': self.plan_notes,
            'duration_minutes': self.duration_minutes,
            'is_makeup': self.is_makeup,
            'makeup_for_session_id': self.makeup_for_session_id,
            'billable_units': float(self.billable_units) if self.billable_units else None,
            'service_code': self.service_code,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def to_calendar_event(self):
        """Convert to FullCalendar event format."""
        status_colors = {
            'Scheduled': '#007bff',
            'Completed': '#28a745', 
            'Makeup Needed': '#ffc107',
            'Excused Absence': '#6c757d',
            'Cancelled': '#dc3545',
            'No Show': '#dc3545'
        }
        
        return {
            'id': self.id,
            'title': f"{self.student.display_name} - {self.session_type}",
            'start': f"{self.session_date}T{self.start_time}",
            'end': f"{self.session_date}T{self.end_time}",
            'backgroundColor': status_colors.get(self.status, '#007bff'),
            'borderColor': status_colors.get(self.status, '#007bff'),
            'textColor': '#ffffff',
            'extendedProps': {
                'studentId': self.student_id,
                'studentName': self.student.display_name,
                'eventType': self.event_type,
                'sessionType': self.session_type,
                'status': self.status,
                'location': self.location,
                'notes': self.notes,
                'planNotes': self.plan_notes,
                'isMakeup': self.is_makeup,
                'needsMakeup': self.needs_makeup
            }
        }

class MonthlyQuota(db.Model, AuditMixin):
    """Track required monthly sessions per student."""
    
    __tablename__ = 'monthly_quotas'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM format
    required_sessions = db.Column(db.Integer, nullable=False)
    
    # Relationships
    student = db.relationship('Student')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'month': self.month,
            'required_sessions': self.required_sessions
        }

class QuarterlyReport(db.Model, AuditMixin):
    """Store generated quarterly progress reports."""
    
    __tablename__ = 'quarterly_reports'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    quarter = db.Column(db.String(20), nullable=False)  # e.g., "Q1 2024"
    report_text = db.Column(db.Text, nullable=False)
    generated_by = db.Column(db.String(100))
    
    # Relationships
    student = db.relationship('Student')
    
    def to_dict(self):
        return {
            'id': self.id,
            'student_id': self.student_id,
            'quarter': self.quarter,
            'report_text': self.report_text,
            'generated_by': self.generated_by,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class Activity(db.Model, AuditMixin):
    """Therapy activities for SOAP note templates."""
    
    __tablename__ = 'activities'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))  # Articulation, Language, Fluency, etc.
    active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'active': self.active
        }