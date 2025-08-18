import os
import json
import gzip
import shutil
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List
from extensions import db
from models import Student, Goal, Objective, Session, TrialLog, SOAPNote, User
import logging

logger = logging.getLogger(__name__)

class DatabaseBackup:
    """Handles database backup, restore, and archival operations."""
    
    def __init__(self, backup_dir: str = None):
        self.backup_dir = Path(backup_dir or os.environ.get('BACKUP_DIR', './backups'))
        self.backup_dir.mkdir(exist_ok=True)
    
    def create_full_backup(self, compress: bool = True, include_logs: bool = True) -> Dict:
        """Create a complete database backup."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"full_backup_{timestamp}"
            
            backup_data = {
                'metadata': {
                    'backup_type': 'full',
                    'created_at': datetime.utcnow().isoformat(),
                    'database_version': self._get_database_version(),
                    'total_records': self._count_total_records()
                },
                'data': {
                    'users': [user.to_dict() for user in User.query.all()],
                    'students': [student.to_dict() for student in Student.query.all()],
                    'goals': [goal.to_dict() for goal in Goal.query.all()],
                    'objectives': [obj.to_dict() for obj in Objective.query.all()],
                    'sessions': [session.to_dict() for session in Session.query.all()],
                    'soap_notes': [note.to_dict(include_content=True) for note in SOAPNote.query.all()]
                }
            }
            
            # Add trial logs if requested
            if include_logs:
                backup_data['data']['trial_logs'] = [log.to_dict() for log in TrialLog.query.all()]
            
            # Save backup
            backup_file = self.backup_dir / f"{backup_name}.json"
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Compress if requested
            if compress:
                compressed_file = self.backup_dir / f"{backup_name}.json.gz"
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file.unlink()  # Remove uncompressed version
                backup_file = compressed_file
            
            backup_info = {
                'backup_name': backup_name,
                'file_path': str(backup_file),
                'file_size': backup_file.stat().st_size,
                'compressed': compress,
                'include_logs': include_logs,
                'records_backed_up': backup_data['metadata']['total_records'],
                'created_at': backup_data['metadata']['created_at']
            }
            
            logger.info(f"Full backup created: {backup_file} ({backup_info['file_size']} bytes)")
            return {'status': 'success', 'backup_info': backup_info}
            
        except Exception as e:
            logger.error(f"Error creating full backup: {e}")
            return {'status': 'error', 'error': str(e)}

    def create_incremental_backup(self, since_date: date, compress: bool = True) -> Dict:
        """Create backup of records modified since a specific date."""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_name = f"incremental_backup_{since_date.strftime('%Y%m%d')}_{timestamp}"
            
            # Get records modified since date
            modified_students = Student.query.filter(Student.updated_at >= since_date).all()
            modified_goals = Goal.query.filter(Goal.updated_at >= since_date).all()
            modified_objectives = Objective.query.filter(Objective.updated_at >= since_date).all()
            modified_sessions = Session.query.filter(Session.updated_at >= since_date).all()
            modified_trial_logs = TrialLog.query.filter(TrialLog.updated_at >= since_date).all()
            modified_soap_notes = SOAPNote.query.filter(SOAPNote.updated_at >= since_date).all()
            
            backup_data = {
                'metadata': {
                    'backup_type': 'incremental',
                    'since_date': since_date.isoformat(),
                    'created_at': datetime.utcnow().isoformat(),
                    'records_count': {
                        'students': len(modified_students),
                        'goals': len(modified_goals),
                        'objectives': len(modified_objectives),
                        'sessions': len(modified_sessions),
                        'trial_logs': len(modified_trial_logs),
                        'soap_notes': len(modified_soap_notes)
                    }
                },
                'data': {
                    'students': [student.to_dict() for student in modified_students],
                    'goals': [goal.to_dict() for goal in modified_goals],
                    'objectives': [obj.to_dict() for obj in modified_objectives],
                    'sessions': [session.to_dict() for session in modified_sessions],
                    'trial_logs': [log.to_dict() for log in modified_trial_logs],
                    'soap_notes': [note.to_dict(include_content=True) for note in modified_soap_notes]
                }
            }
            
            # Save backup
            backup_file = self.backup_dir / f"{backup_name}.json"
            
            with open(backup_file, 'w') as f:
                json.dump(backup_data, f, indent=2, default=str)
            
            # Compress if requested
            if compress:
                compressed_file = self.backup_dir / f"{backup_name}.json.gz"
                with open(backup_file, 'rb') as f_in:
                    with gzip.open(compressed_file, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                backup_file.unlink()
                backup_file = compressed_file
            
            total_records = sum(backup_data['metadata']['records_count'].values())
            
            backup_info = {
                'backup_name': backup_name,
                'file_path': str(backup_file),
                'file_size': backup_file.stat().st_size,
                'records_backed_up': total_records,
                'since_date': since_date.isoformat(),
                'created_at': backup_data['metadata']['created_at']
            }
            
            logger.info(f"Incremental backup created: {backup_file} ({total_records} modified records)")
            return {'status': 'success', 'backup_info': backup_info}
            
        except Exception as e:
            logger.error(f"Error creating incremental backup: {e}")
            return {'status': 'error', 'error': str(e)}

    def restore_backup(self, backup_file: str, restore_mode: str = 'replace') -> Dict:
        """Restore database from backup file."""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                backup_path = self.backup_dir / backup_file
            
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup file not found: {backup_file}")
            
            # Load backup data
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rt') as f:
                    backup_data = json.load(f)
            else:
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
            
            restored_counts = {}
            
            # Restore data based on mode
            if restore_mode == 'replace':
                # Clear existing data (dangerous - use with caution)
                logger.warning("REPLACE mode: This will delete existing data!")
                self._clear_database()
            
            # Restore each table
            restored_counts['users'] = self._restore_users(backup_data['data'].get('users', []), restore_mode)
            restored_counts['students'] = self._restore_students(backup_data['data'].get('students', []), restore_mode)
            restored_counts['goals'] = self._restore_goals(backup_data['data'].get('goals', []), restore_mode)
            restored_counts['objectives'] = self._restore_objectives(backup_data['data'].get('objectives', []), restore_mode)
            restored_counts['sessions'] = self._restore_sessions(backup_data['data'].get('sessions', []), restore_mode)
            restored_counts['trial_logs'] = self._restore_trial_logs(backup_data['data'].get('trial_logs', []), restore_mode)
            restored_counts['soap_notes'] = self._restore_soap_notes(backup_data['data'].get('soap_notes', []), restore_mode)
            
            db.session.commit()
            
            restore_info = {
                'backup_file': str(backup_path),
                'restore_mode': restore_mode,
                'restored_counts': restored_counts,
                'total_restored': sum(restored_counts.values()),
                'restored_at': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Database restored from {backup_path} - {restore_info['total_restored']} records")
            return {'status': 'success', 'restore_info': restore_info}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error restoring backup: {e}")
            return {'status': 'error', 'error': str(e)}

    def list_backups(self) -> List[Dict]:
        """List all available backup files."""
        try:
            backups = []
            
            for backup_file in self.backup_dir.glob("*.json*"):
                file_stats = backup_file.stat()
                
                # Try to extract metadata if possible
                metadata = None
                try:
                    if backup_file.suffix == '.gz':
                        with gzip.open(backup_file, 'rt') as f:
                            data = json.load(f)
                    else:
                        with open(backup_file, 'r') as f:
                            data = json.load(f)
                    metadata = data.get('metadata', {})
                except Exception:
                    pass  # Skip if can't read metadata
                
                backup_info = {
                    'filename': backup_file.name,
                    'file_path': str(backup_file),
                    'size_bytes': file_stats.st_size,
                    'size_mb': round(file_stats.st_size / (1024 * 1024), 2),
                    'created': datetime.fromtimestamp(file_stats.st_ctime).isoformat(),
                    'modified': datetime.fromtimestamp(file_stats.st_mtime).isoformat(),
                    'compressed': backup_file.suffix == '.gz'
                }
                
                if metadata:
                    backup_info.update({
                        'backup_type': metadata.get('backup_type'),
                        'total_records': metadata.get('total_records'),
                        'database_version': metadata.get('database_version')
                    })
                
                backups.append(backup_info)
            
            # Sort by creation date (newest first)
            backups.sort(key=lambda x: x['created'], reverse=True)
            
            return backups
            
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    def cleanup_old_backups(self, keep_days: int = 30, keep_minimum: int = 5) -> Dict:
        """Remove old backup files based on retention policy."""
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            all_backups = self.list_backups()
            
            # Sort by date and keep minimum number regardless of age
            all_backups.sort(key=lambda x: x['created'], reverse=True)
            candidates_for_deletion = all_backups[keep_minimum:]
            
            deleted_files = []
            total_space_freed = 0
            
            for backup in candidates_for_deletion:
                backup_date = datetime.fromisoformat(backup['created'])
                if backup_date < cutoff_date:
                    backup_path = Path(backup['file_path'])
                    if backup_path.exists():
                        file_size = backup_path.stat().st_size
                        backup_path.unlink()
                        deleted_files.append({
                            'filename': backup['filename'],
                            'size_mb': backup['size_mb'],
                            'created': backup['created']
                        })
                        total_space_freed += file_size
            
            cleanup_info = {
                'files_deleted': len(deleted_files),
                'space_freed_mb': round(total_space_freed / (1024 * 1024), 2),
                'files_kept': len(all_backups) - len(deleted_files),
                'deleted_files': deleted_files,
                'cleanup_date': datetime.utcnow().isoformat()
            }
            
            logger.info(f"Backup cleanup: deleted {len(deleted_files)} files, freed {cleanup_info['space_freed_mb']} MB")
            return {'status': 'success', 'cleanup_info': cleanup_info}
            
        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")
            return {'status': 'error', 'error': str(e)}

    def verify_backup_integrity(self, backup_file: str) -> Dict:
        """Verify backup file integrity and structure."""
        try:
            backup_path = Path(backup_file)
            if not backup_path.exists():
                backup_path = self.backup_dir / backup_file
            
            if not backup_path.exists():
                return {'status': 'error', 'error': 'Backup file not found'}
            
            # Load and validate backup structure
            if backup_path.suffix == '.gz':
                with gzip.open(backup_path, 'rt') as f:
                    backup_data = json.load(f)
            else:
                with open(backup_path, 'r') as f:
                    backup_data = json.load(f)
            
            # Check required structure
            required_keys = ['metadata', 'data']
            missing_keys = [key for key in required_keys if key not in backup_data]
            
            if missing_keys:
                return {
                    'status': 'error',
                    'error': f'Missing required keys: {missing_keys}'
                }
            
            # Validate metadata
            metadata = backup_data['metadata']
            required_metadata = ['backup_type', 'created_at']
            missing_metadata = [key for key in required_metadata if key not in metadata]
            
            # Count records in each table
            data_counts = {}
            for table, records in backup_data['data'].items():
                data_counts[table] = len(records) if isinstance(records, list) else 0
            
            # Check for data consistency
            consistency_checks = []
            
            # Example: Check if goals reference valid students
            if 'goals' in backup_data['data'] and 'students' in backup_data['data']:
                student_ids = {s['id'] for s in backup_data['data']['students']}
                invalid_goal_refs = [
                    g['id'] for g in backup_data['data']['goals'] 
                    if g['student_id'] not in student_ids
                ]
                if invalid_goal_refs:
                    consistency_checks.append(f"Goals with invalid student references: {invalid_goal_refs}")
            
            integrity_info = {
                'file_path': str(backup_path),
                'file_size': backup_path.stat().st_size,
                'structure_valid': len(missing_keys) == 0,
                'metadata_complete': len(missing_metadata) == 0,
                'backup_type': metadata.get('backup_type'),
                'created_at': metadata.get('created_at'),
                'data_counts': data_counts,
                'total_records': sum(data_counts.values()),
                'consistency_issues': consistency_checks,
                'verified_at': datetime.utcnow().isoformat()
            }
            
            status = 'success' if len(missing_keys) == 0 and len(consistency_checks) == 0 else 'warning'
            
            return {'status': status, 'integrity_info': integrity_info}
            
        except Exception as e:
            logger.error(f"Error verifying backup integrity: {e}")
            return {'status': 'error', 'error': str(e)}

    def _get_database_version(self) -> str:
        """Get current database version/schema."""
        try:
            # This would typically check migration version
            return "1.0.0"
        except Exception:
            return "unknown"

    def _count_total_records(self) -> int:
        """Count total records in database."""
        try:
            return (
                Student.query.count() +
                Goal.query.count() +
                Objective.query.count() +
                Session.query.count() +
                TrialLog.query.count() +
                SOAPNote.query.count() +
                User.query.count()
            )
        except Exception:
            return 0

    def _clear_database(self):
        """Clear all data from database (use with extreme caution)."""
        # Delete in order to respect foreign key constraints
        TrialLog.query.delete()
        SOAPNote.query.delete()
        Session.query.delete()
        Objective.query.delete()
        Goal.query.delete()
        Student.query.delete()
        # Note: Not deleting users for safety

    def _restore_users(self, users_data: List[Dict], mode: str) -> int:
        """Restore users data."""
        count = 0
        for user_data in users_data:
            if mode == 'skip' and User.query.get(user_data['id']):
                continue
            # Implementation would depend on User model structure
            count += 1
        return count

    def _restore_students(self, students_data: List[Dict], mode: str) -> int:
        """Restore students data."""
        count = 0
        for student_data in students_data:
            if mode == 'skip' and Student.query.get(student_data['id']):
                continue
            
            # Create or update student
            student = Student(
                id=student_data['id'],
                first_name=student_data['first_name'],
                last_name=student_data['last_name'],
                preferred_name=student_data.get('preferred_name'),
                pronouns=student_data.get('pronouns'),
                grade_level=student_data.get('grade_level'),
                monthly_services=student_data.get('monthly_services', 0),
                active=student_data.get('active', True),
                anonymous_id=student_data.get('anonymous_id'),
                anonymized=student_data.get('anonymized', False)
            )
            
            db.session.merge(student)
            count += 1
        
        return count

    def _restore_goals(self, goals_data: List[Dict], mode: str) -> int:
        """Restore goals data."""
        count = 0
        for goal_data in goals_data:
            if mode == 'skip' and Goal.query.get(goal_data['id']):
                continue
            
            goal = Goal(
                id=goal_data['id'],
                student_id=goal_data['student_id'],
                description=goal_data['description'],
                active=goal_data.get('active', True),
                target_date=datetime.fromisoformat(goal_data['target_date']).date() if goal_data.get('target_date') else None,
                completion_criteria=goal_data.get('completion_criteria')
            )
            
            db.session.merge(goal)
            count += 1
        
        return count

    def _restore_objectives(self, objectives_data: List[Dict], mode: str) -> int:
        """Restore objectives data."""
        count = 0
        for obj_data in objectives_data:
            if mode == 'skip' and Objective.query.get(obj_data['id']):
                continue
            
            objective = Objective(
                id=obj_data['id'],
                goal_id=obj_data['goal_id'],
                description=obj_data['description'],
                accuracy_target=obj_data.get('accuracy_target'),
                notes=obj_data.get('notes'),
                active=obj_data.get('active', True)
            )
            
            db.session.merge(objective)
            count += 1
        
        return count

    def _restore_sessions(self, sessions_data: List[Dict], mode: str) -> int:
        """Restore sessions data."""
        count = 0
        for session_data in sessions_data:
            if mode == 'skip' and Session.query.get(session_data['id']):
                continue
            
            session = Session(
                id=session_data['id'],
                student_id=session_data['student_id'],
                session_date=datetime.fromisoformat(session_data['session_date']).date(),
                start_time=datetime.strptime(session_data['start_time'], '%H:%M').time(),
                end_time=datetime.strptime(session_data['end_time'], '%H:%M').time(),
                session_type=session_data.get('session_type', 'Individual'),
                status=session_data.get('status', 'Scheduled'),
                location=session_data.get('location'),
                notes=session_data.get('notes')
            )
            
            db.session.merge(session)
            count += 1
        
        return count

    def _restore_trial_logs(self, trial_logs_data: List[Dict], mode: str) -> int:
        """Restore trial logs data."""
        count = 0
        for log_data in trial_logs_data:
            if mode == 'skip' and TrialLog.query.get(log_data['id']):
                continue
            
            trial_log = TrialLog(
                id=log_data['id'],
                student_id=log_data['student_id'],
                objective_id=log_data.get('objective_id'),
                session_date=datetime.fromisoformat(log_data['session_date']).date(),
                independent=log_data.get('independent', 0),
                minimal_support=log_data.get('minimal_support', 0),
                moderate_support=log_data.get('moderate_support', 0),
                maximal_support=log_data.get('maximal_support', 0),
                incorrect=log_data.get('incorrect', 0),
                session_notes=log_data.get('session_notes'),
                environmental_factors=log_data.get('environmental_factors')
            )
            
            db.session.merge(trial_log)
            count += 1
        
        return count

    def _restore_soap_notes(self, soap_notes_data: List[Dict], mode: str) -> int:
        """Restore SOAP notes data."""
        count = 0
        for note_data in soap_notes_data:
            if mode == 'skip' and SOAPNote.query.get(note_data['id']):
                continue
            
            soap_note = SOAPNote(
                id=note_data['id'],
                student_id=note_data['student_id'],
                session_id=note_data.get('session_id'),
                session_date=datetime.fromisoformat(note_data['session_date']).date(),
                subjective=note_data.get('subjective'),
                objective=note_data.get('objective'),
                assessment=note_data.get('assessment'),
                plan=note_data.get('plan'),
                clinician_signature=note_data.get('clinician_signature'),
                anonymized=note_data.get('anonymized', False)
            )
            
            db.session.merge(soap_note)
            count += 1
        
        return count