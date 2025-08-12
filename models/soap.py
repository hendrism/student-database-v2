from datetime import datetime, date
from . import db
from .student import AuditMixin, PrivacyMixin

class SOAPNote(db.Model, AuditMixin, PrivacyMixin):
    """SOAP Note model with privacy protection."""
    
    __tablename__ = 'soap_notes'
    
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    session_date = db.Column(db.Date, nullable=False)
    
    # SOAP components
    subjective = db.Column(db.Text)
    objective = db.Column(db.Text)
    assessment = db.Column(db.Text)
    plan = db.Column(db.Text)
    
    # Additional fields
    session_id = db.Column(db.Integer, db.ForeignKey('sessions.id'))
    clinician_signature = db.Column(db.String(200))
    
    # Relationships
    student = db.relationship('Student', back_populates='soap_notes')
    session = db.relationship('Session')
    
    def anonymize(self):
        """Anonymize SOAP note content."""
        super().anonymize()
        # Replace any remaining identifying information
        if self.subjective:
            self.subjective = "ANONYMIZED CONTENT"
        if self.objective:
            self.objective = "ANONYMIZED CONTENT"
        if self.assessment:
            self.assessment = "ANONYMIZED CONTENT"
        if self.plan:
            self.plan = "ANONYMIZED CONTENT"
    
    def to_dict(self, include_content=True):
        data = {
            'id': self.id,
            'student_id': self.student_id,
            'session_date': self.session_date.isoformat(),
            'session_id': self.session_id,
            'clinician_signature': self.clinician_signature,
            'anonymized': self.anonymized,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        
        if include_content and not self.anonymized:
            data.update({
                'subjective': self.subjective,
                'objective': self.objective,
                'assessment': self.assessment,
                'plan': self.plan
            })
            
        return data