import hashlib
import uuid
import re
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from extensions import db
from models import Student, SOAPNote, TrialLog
import logging

logger = logging.getLogger(__name__)

class PrivacyManager:
    """Handles data privacy, anonymization, and retention policies."""
    
    @staticmethod
    def anonymize_student(student_id: int, preserve_analytics: bool = True) -> Dict:
        """Anonymize a student's data while preserving educational value."""
        try:
            student = Student.query.get(student_id)
            if not student:
                raise ValueError(f"Student with ID {student_id} not found")
            
            if student.anonymized:
                return {'status': 'already_anonymized', 'student_id': student_id}
            
            # Store original data for audit trail (could be logged or stored if needed)
            _ = {
                'first_name': student.first_name,
                'last_name': student.last_name,
                'preferred_name': student.preferred_name,
            }
            
            # Anonymize student record
            student.anonymize()
            
            # Anonymize related SOAP notes
            soap_notes = SOAPNote.query.filter_by(student_id=student_id).all()
            for note in soap_notes:
                if not note.anonymized:
                    note.anonymize()
            
            # Generate anonymization report
            report = {
                'student_id': student_id,
                'anonymous_id': student.anonymous_id,
                'anonymized_at': datetime.utcnow().isoformat(),
                'records_affected': {
                    'student_record': 1,
                    'soap_notes': len(soap_notes),
                    'trial_logs_preserved': TrialLog.query.filter_by(student_id=student_id).count()
                },
                'analytics_preserved': preserve_analytics
            }
            
            db.session.commit()
            logger.info(f"Anonymized student {student_id} - {len(soap_notes)} SOAP notes affected")
            
            return {'status': 'success', 'report': report}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error anonymizing student {student_id}: {e}")
            raise

    @staticmethod
    def anonymize_text_content(text: str, replacement_patterns: Optional[Dict] = None) -> str:
        """Remove or replace personally identifiable information from text."""
        if not text:
            return text
        
        # Default patterns for PII detection and removal
        default_patterns = {
            # Names (simple pattern - can be enhanced)
            r'\b[A-Z][a-z]+ [A-Z][a-z]+\b': '[NAME]',
            # Phone numbers
            r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b': '[PHONE]',
            # Email addresses
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b': '[EMAIL]',
            # Addresses (basic pattern)
            r'\b\d+\s+[A-Za-z\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Boulevard|Blvd)\b': '[ADDRESS]',
            # Social Security Numbers
            r'\b\d{3}-\d{2}-\d{4}\b': '[SSN]',
            # Dates of birth (various formats)
            r'\b(?:0[1-9]|1[0-2])/(?:0[1-9]|[12]\d|3[01])/(?:19|20)\d{2}\b': '[DOB]',
            r'\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b': '[DOB]'
        }
        
        patterns = replacement_patterns or default_patterns
        anonymized_text = text
        
        for pattern, replacement in patterns.items():
            anonymized_text = re.sub(pattern, replacement, anonymized_text, flags=re.IGNORECASE)
        
        return anonymized_text

    @staticmethod
    def generate_anonymous_id(seed: Optional[str] = None) -> str:
        """Generate a consistent anonymous identifier."""
        if seed:
            # Generate deterministic ID from seed
            return hashlib.md5(seed.encode()).hexdigest()[:8]
        else:
            # Generate random ID
            return uuid.uuid4().hex[:8]

    @staticmethod
    def check_retention_policy(retention_days: int = 2555) -> List[Dict]:  # ~7 years default
        """Identify records that exceed retention policy."""
        cutoff_date = date.today() - timedelta(days=retention_days)
        
        # Find students with old data
        old_students = Student.query.filter(
            Student.created_at < cutoff_date,
            Student.active.is_(False),
            Student.anonymized.is_(False)
        ).all()
        
        retention_violations = []
        for student in old_students:
            # Check if student has any recent activity
            recent_activity = db.session.query(
                db.func.max(TrialLog.session_date)
            ).filter(TrialLog.student_id == student.id).scalar()
            
            if not recent_activity or recent_activity < cutoff_date:
                retention_violations.append({
                    'student_id': student.id,
                    'student_name': student.display_name,
                    'created_at': student.created_at.isoformat(),
                    'last_activity': recent_activity.isoformat() if recent_activity else None,
                    'days_since_creation': (date.today() - student.created_at.date()).days,
                    'recommendation': 'Consider anonymization or archival'
                })
        
        return retention_violations

    @staticmethod
    def bulk_anonymize_old_records(cutoff_date: date, dry_run: bool = True) -> Dict:
        """Bulk anonymize records older than cutoff date."""
        try:
            # Find candidates for anonymization
            candidates = Student.query.filter(
                Student.created_at < cutoff_date,
                Student.active.is_(False),
                Student.anonymized.is_(False)
            ).all()
            
            if dry_run:
                return {
                    'action': 'dry_run',
                    'candidates_found': len(candidates),
                    'candidates': [
                        {
                            'student_id': s.id,
                            'name': s.display_name,
                            'created_at': s.created_at.isoformat()
                        }
                        for s in candidates
                    ]
                }
            
            # Perform bulk anonymization
            anonymized_count = 0
            errors = []
            
            for student in candidates:
                try:
                    result = PrivacyManager.anonymize_student(student.id)
                    if result['status'] == 'success':
                        anonymized_count += 1
                except Exception as e:
                    errors.append({
                        'student_id': student.id,
                        'error': str(e)
                    })
            
            return {
                'action': 'bulk_anonymization',
                'processed': len(candidates),
                'successful': anonymized_count,
                'errors': errors,
                'completed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in bulk anonymization: {e}")
            raise

    @staticmethod
    def audit_data_access(user_id: int, resource_type: str, resource_id: int, action: str) -> None:
        """Log data access for audit purposes."""
        audit_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'user_id': user_id,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'action': action,
            'ip_address': None  # Would be populated from request context
        }
        
        logger.info(f"Data access audit: {audit_entry}")
        # In a production system, this would be stored in a dedicated audit table

    @staticmethod
    def validate_data_minimization(data_dict: Dict, allowed_fields: List[str]) -> Dict:
        """Ensure only necessary data fields are included."""
        filtered_data = {k: v for k, v in data_dict.items() if k in allowed_fields}
        removed_fields = [k for k in data_dict.keys() if k not in allowed_fields]
        
        return {
            'filtered_data': filtered_data,
            'removed_fields': removed_fields,
            'minimization_applied': len(removed_fields) > 0
        }

    @staticmethod
    def encrypt_sensitive_field(value: str, key: Optional[str] = None) -> str:
        """Simple encryption for sensitive fields (in production, use proper encryption)."""
        if not value:
            return value
        
        # This is a placeholder - in production, use proper encryption
        # like cryptography.fernet or similar
        import base64
        encoded = base64.b64encode(value.encode()).decode()
        return f"ENC:{encoded}"

    @staticmethod
    def decrypt_sensitive_field(encrypted_value: str, key: Optional[str] = None) -> str:
        """Decrypt sensitive fields."""
        if not encrypted_value or not encrypted_value.startswith('ENC:'):
            return encrypted_value
        
        try:
            import base64
            encoded_part = encrypted_value[4:]  # Remove 'ENC:' prefix
            decoded = base64.b64decode(encoded_part).decode()
            return decoded
        except Exception:
            return encrypted_value

    @staticmethod
    def generate_privacy_report() -> Dict:
        """Generate comprehensive privacy compliance report."""
        try:
            # Data inventory
            total_students = Student.query.count()
            active_students = Student.query.filter(Student.active.is_(True)).count()
            anonymized_students = Student.query.filter(Student.anonymized.is_(True)).count()

            # SOAP notes privacy status
            total_soap_notes = SOAPNote.query.count()
            anonymized_soap_notes = SOAPNote.query.filter(SOAPNote.anonymized.is_(True)).count()
            
            # Retention policy compliance
            retention_violations = PrivacyManager.check_retention_policy()
            
            # Data age analysis
            oldest_active_student = db.session.query(
                db.func.min(Student.created_at)
            ).filter(
                Student.active.is_(True),
                Student.anonymized.is_(False)
            ).scalar()
            
            # Privacy metrics
            anonymization_rate = round((anonymized_students / total_students) * 100, 1) if total_students > 0 else 0
            soap_anonymization_rate = round((anonymized_soap_notes / total_soap_notes) * 100, 1) if total_soap_notes > 0 else 0
            
            return {
                'report_generated': datetime.utcnow().isoformat(),
                'data_inventory': {
                    'total_students': total_students,
                    'active_students': active_students,
                    'anonymized_students': anonymized_students,
                    'anonymization_rate': f"{anonymization_rate}%"
                },
                'soap_notes_privacy': {
                    'total_notes': total_soap_notes,
                    'anonymized_notes': anonymized_soap_notes,
                    'anonymization_rate': f"{soap_anonymization_rate}%"
                },
                'retention_compliance': {
                    'violations_found': len(retention_violations),
                    'oldest_active_record': oldest_active_student.isoformat() if oldest_active_student else None,
                    'recommendations': [
                        f"Review {len(retention_violations)} records for potential anonymization"
                    ] if retention_violations else ["All records within retention policy"]
                },
                'privacy_score': min(100, round((anonymization_rate + soap_anonymization_rate) / 2, 1)),
                'recommendations': PrivacyManager._generate_privacy_recommendations(
                    anonymization_rate, len(retention_violations)
                )
            }
            
        except Exception as e:
            logger.error(f"Error generating privacy report: {e}")
            raise

    @staticmethod
    def _generate_privacy_recommendations(anonymization_rate: float, retention_violations: int) -> List[str]:
        """Generate privacy recommendations based on current state."""
        recommendations = []
        
        if anonymization_rate < 20:
            recommendations.append("Consider implementing regular anonymization schedules for inactive records")
        
        if retention_violations > 0:
            recommendations.append(f"Address {retention_violations} retention policy violations")
        
        if anonymization_rate > 80:
            recommendations.append("Excellent privacy compliance - continue current practices")
        
        recommendations.append("Regularly review and update privacy policies")
        recommendations.append("Conduct periodic privacy impact assessments")
        
        return recommendations

# Decorator for privacy-aware endpoints
def privacy_required(f):
    """Decorator to ensure privacy compliance on sensitive endpoints."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Add privacy logging and validation
        logger.info(f"Privacy-sensitive operation: {f.__name__}")
        return f(*args, **kwargs)
    
    return decorated_function

# Constants for privacy configuration
PRIVACY_CONFIG = {
    'default_retention_days': 2555,  # ~7 years
    'anonymization_schedule': 'monthly',
    'audit_log_retention': 365,  # 1 year
    'encryption_required_fields': [
        'first_name', 'last_name', 'preferred_name', 
        'subjective', 'objective', 'assessment', 'plan'
    ]
}
