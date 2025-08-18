from datetime import datetime, date
from . import db

class SOAPNote(db.Model):
    """SOAP Note model for clinical documentation."""
    
    __tablename__ = 'soap_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    session_date = db.Column(db.Date, default=date.today, nullable=False)
    
    # SOAP components
    subjective = db.Column(db.Text)
    objective = db.Column(db.Text)
    assessment = db.Column(db.Text)
    plan = db.Column(db.Text)
    
    # Metadata
    clinician_signature = db.Column(db.String(100))
    reviewed_by = db.Column(db.String(100))
    reviewed_date = db.Column(db.Date)
    
    # Privacy
    anonymized = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)
    
    # Relationships
    student = db.relationship('Student', back_populates='soap_notes')
    session = db.relationship('Session', back_populates='soap_notes')
    
    def anonymize(self):
        """Anonymize SOAP note content."""
        self.anonymized = True
        if self.subjective:
            self.subjective = "ANONYMIZED CONTENT"
        if self.objective:
            self.objective = "ANONYMIZED CONTENT"
        if self.assessment:
            self.assessment = "ANONYMIZED CONTENT"
        if self.plan:
            self.plan = "ANONYMIZED CONTENT"
        self.clinician_signature = "ANONYMIZED"
    
    def to_dict(self, include_content=True):
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'student_id': self.student_id,
            'session_id': self.session_id,
            'session_date': self.session_date.isoformat(),
            'clinician_signature': self.clinician_signature,
            'reviewed_by': self.reviewed_by,
            'reviewed_date': self.reviewed_date.isoformat() if self.reviewed_date else None,
            'anonymized': self.anonymized
        }
        
        if include_content and not self.anonymized:
            data.update({
                'subjective': self.subjective,
                'objective': self.objective,
                'assessment': self.assessment,
                'plan': self.plan
            })
        
        return data
