from flask import Blueprint, request, jsonify, current_app, g
from marshmallow import Schema, fields, ValidationError, validate
from datetime import datetime, date
from models import db, Student, Goal, Objective, TrialLog, Session
from auth.decorators import require_auth, require_permission
import logging

api_bp = Blueprint('api', __name__)

# Validation Schemas
class StudentSchema(Schema):
    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    preferred_name = fields.Str(validate=validate.Length(max=100), allow_none=True)
    pronouns = fields.Str(validate=validate.Length(max=50), allow_none=True)
    grade_level = fields.Str(validate=validate.OneOf([
        'Grade 9', 'Grade 10', 'Grade 11', 'Grade 12'
    ]))
    monthly_services = fields.Int(validate=validate.Range(min=1, max=20))

class TrialLogSchema(Schema):
    session_date = fields.Date(required=True)
    independent = fields.Int(validate=validate.Range(min=0, max=100), missing=0)
    minimal_support = fields.Int(validate=validate.Range(min=0, max=100), missing=0)
    moderate_support = fields.Int(validate=validate.Range(min=0, max=100), missing=0)
    maximal_support = fields.Int(validate=validate.Range(min=0, max=100), missing=0)
    incorrect = fields.Int(validate=validate.Range(min=0, max=100), missing=0)
    session_notes = fields.Str(validate=validate.Length(max=1000), allow_none=True)

# Error handlers
@api_bp.errorhandler(ValidationError)
def handle_validation_error(error):
    current_app.logger.warning(f'Validation error: {error.messages}')
    return jsonify({'error': 'Validation failed', 'messages': error.messages}), 400

# Health check
@api_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'version': '2.0.0'
        })
    except Exception as e:
        current_app.logger.error(f'Health check failed: {str(e)}')
        return jsonify({
            'status': 'unhealthy',
            'error': 'Database connection failed',
            'timestamp': datetime.utcnow().isoformat()
        }), 503

# Students API
@api_bp.route('/students', methods=['GET'])
@require_auth
def get_students():
    """Get all students with filtering and pagination."""
    try:
        # Get query parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        search = request.args.get('search', '')
        grade_filter = request.args.get('grade')
        active_only = request.args.get('active_only', 'true').lower() == 'true'
        
        # Build query
        query = Student.query
        
        if active_only:
            query = query.filter(Student.active == True)
            
        if search:
            query = query.filter(
                db.or_(
                    Student.first_name.ilike(f'%{search}%'),
                    Student.last_name.ilike(f'%{search}%'),
                    Student.anonymous_id.ilike(f'%{search}%')
                )
            )
            
        if grade_filter:
            query = query.filter(Student.grade_level == grade_filter)
        
        # Execute paginated query
        pagination = query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        students = pagination.items
        
        # Check privacy permissions
        include_sensitive = g.current_user.has_permission('admin')
        
        # Serialize students
        students_data = [student.to_dict(include_sensitive=include_sensitive) 
                        for student in students]
        
        return jsonify({
            'students': students_data,
            'pagination': {
                'page': page,
                'pages': pagination.pages,
                'per_page': per_page,
                'total': pagination.total,
                'has_next': pagination.has_next,
                'has_prev': pagination.has_prev
            }
        })
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving students: {str(e)}')
        return jsonify({'error': 'Failed to retrieve students'}), 500

@api_bp.route('/students', methods=['POST'])
@require_auth
@require_permission('write')
def create_student():
    """Create a new student."""
    try:
        # Validate input data
        schema = StudentSchema()
        student_data = schema.load(request.json)
        
        # Create new student
        student = Student(**student_data)
        db.session.add(student)
        db.session.commit()
        
        current_app.logger.info(f'Created new student: {student.display_name}')
        
        return jsonify({
            'message': 'Student created successfully',
            'student': student.to_dict()
        }), 201
        
    except ValidationError as e:
        raise e
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating student: {str(e)}')
        return jsonify({'error': 'Failed to create student'}), 500

@api_bp.route('/students/<int:student_id>', methods=['GET'])
@require_auth
def get_student(student_id):
    """Get a specific student by ID."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Check privacy permissions
        include_sensitive = g.current_user.has_permission('admin')
        
        # Include related data
        include_goals = request.args.get('include_goals', 'false').lower() == 'true'
        include_sessions = request.args.get('include_sessions', 'false').lower() == 'true'
        include_trials = request.args.get('include_trials', 'false').lower() == 'true'
        
        student_data = student.to_dict(include_sensitive=include_sensitive)
        
        if include_goals:
            student_data['goals'] = [goal.to_dict() for goal in student.goals if goal.active]
            
        if include_sessions:
            recent_sessions = [s for s in student.sessions if 
                             (datetime.now().date() - s.session_date).days <= 30]
            student_data['recent_sessions'] = [session.to_dict() for session in recent_sessions]
            
        if include_trials:
            recent_trials = [t for t in student.trial_logs if 
                           (datetime.now().date() - t.session_date).days <= 30]
            student_data['recent_trials'] = [trial.to_dict() for trial in recent_trials]
        
        return jsonify(student_data)
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving student {student_id}: {str(e)}')
        return jsonify({'error': 'Failed to retrieve student'}), 500

@api_bp.route('/students/<int:student_id>', methods=['PUT'])
@require_auth
@require_permission('write')
def update_student(student_id):
    """Update a student."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Validate input data
        schema = StudentSchema(partial=True)
        student_data = schema.load(request.json)
        
        # Update student
        for key, value in student_data.items():
            setattr(student, key, value)
            
        db.session.commit()
        
        current_app.logger.info(f'Updated student: {student.display_name}')
        
        return jsonify({
            'message': 'Student updated successfully',
            'student': student.to_dict()
        })
        
    except ValidationError as e:
        raise e
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating student {student_id}: {str(e)}')
        return jsonify({'error': 'Failed to update student'}), 500

# Trial Logs API
@api_bp.route('/students/<int:student_id>/trial-logs', methods=['GET'])
@require_auth
def get_trial_logs(student_id):
    """Get trial logs for a specific student."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Get query parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        objective_id = request.args.get('objective_id', type=int)
        
        # Build query
        query = TrialLog.query.filter(TrialLog.student_id == student_id)
        
        if start_date:
            try:
                start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(TrialLog.session_date >= start_date)
            except ValueError:
                return jsonify({'error': 'Invalid start_date format. Use YYYY-MM-DD'}), 400
                
        if end_date:
            try:
                end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(TrialLog.session_date <= end_date)
            except ValueError:
                return jsonify({'error': 'Invalid end_date format. Use YYYY-MM-DD'}), 400
                
        if objective_id:
            query = query.filter(TrialLog.objective_id == objective_id)
        
        trial_logs = query.order_by(TrialLog.session_date.desc()).all()
        
        # Include objective information
        logs_data = []
        for log in trial_logs:
            log_dict = log.to_dict()
            if log.objective:
                log_dict['objective'] = {
                    'id': log.objective.id,
                    'description': log.objective.description,
                    'goal_description': log.objective.goal.description
                }
            logs_data.append(log_dict)
        
        return jsonify({'trial_logs': logs_data})
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving trial logs for student {student_id}: {str(e)}')
        return jsonify({'error': 'Failed to retrieve trial logs'}), 500

@api_bp.route('/students/<int:student_id>/trial-logs', methods=['POST'])
@require_auth
@require_permission('write')
def create_trial_log(student_id):
    """Create a new trial log for a student."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Validate input data
        schema = TrialLogSchema()
        log_data = schema.load(request.json)
        
        # Validate objective exists
        objective_id = request.json.get('objective_id')
        if objective_id:
            objective = Objective.query.filter_by(
                id=objective_id
            ).join(Goal).filter(Goal.student_id == student_id).first()
            
            if not objective:
                return jsonify({'error': 'Invalid objective for this student'}), 400
                
            log_data['objective_id'] = objective_id
        
        # Create trial log
        trial_log = TrialLog(student_id=student_id, **log_data)
        db.session.add(trial_log)
        db.session.commit()
        
        current_app.logger.info(f'Created trial log for student {student.display_name}')
        
        return jsonify({
            'message': 'Trial log created successfully',
            'trial_log': trial_log.to_dict()
        }), 201
        
    except ValidationError as e:
        raise e
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error creating trial log for student {student_id}: {str(e)}')
        return jsonify({'error': 'Failed to create trial log'}), 500

# Dashboard Analytics
@api_bp.route('/analytics/dashboard', methods=['GET'])
@require_auth
def get_dashboard_analytics():
    """Get dashboard analytics data."""
    try:
        from datetime import timedelta
        from sqlalchemy import func
        
        today = date.today()
        one_week_ago = today - timedelta(days=7)
        one_month_ago = today - timedelta(days=30)
        
        # Basic counts
        total_students = Student.query.filter(Student.active == True).count()
        total_goals = Goal.query.filter(Goal.active == True).count()
        
        # Sessions this week
        sessions_this_week = Session.query.filter(
            Session.session_date >= one_week_ago,
            Session.status == 'Completed'
        ).count()
        
        # Completion rate
        total_sessions = Session.query.filter(
            Session.session_date >= one_month_ago
        ).count()
        
        completed_sessions = Session.query.filter(
            Session.session_date >= one_month_ago,
            Session.status == 'Completed'
        ).count()
        
        completion_rate = round(
            (completed_sessions / total_sessions) * 100, 1
        ) if total_sessions > 0 else 0
        
        # Recent activity
        recent_sessions = Session.query.filter(
            Session.session_date >= one_week_ago
        ).order_by(Session.session_date.desc()).limit(5).all()
        
        recent_activity = []
        for session in recent_sessions:
            recent_activity.append({
                'type': 'session',
                'date': session.session_date.isoformat(),
                'student_name': session.student.display_name,
                'status': session.status,
                'description': f"{session.session_type} session"
            })
        
        return jsonify({
            'stats': {
                'total_students': total_students,
                'total_goals': total_goals,
                'sessions_this_week': sessions_this_week,
                'completion_rate': completion_rate
            },
            'recent_activity': recent_activity
        })
        
    except Exception as e:
        current_app.logger.error(f'Error retrieving dashboard analytics: {str(e)}')
        return jsonify({'error': 'Failed to retrieve analytics'}), 500