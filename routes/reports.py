from flask import Blueprint, request, jsonify, make_response
from auth.decorators import token_required, role_required
from models import db, Student, Goal, Objective, Session, TrialLog, SOAPNote
from utils.validators import validate_date_range
from datetime import datetime, date, timedelta
import logging

# Import report functions locally to handle missing dependencies
try:
    from utils.reports import generate_progress_report, generate_analytics_data
    REPORTS_AVAILABLE = True
except ImportError:
    REPORTS_AVAILABLE = False

logger = logging.getLogger(__name__)
reports_bp = Blueprint('reports', __name__, url_prefix='/api/reports')

@reports_bp.route('/student/<int:student_id>/progress', methods=['GET'])
@token_required
def get_student_progress_report(student_id):
    """Generate comprehensive progress report for a student."""
    try:
        student = Student.query.get_or_404(student_id)
        
        # Date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date', date.today().isoformat())
        
        # Default to last 3 months if no start date
        if not start_date:
            start_date = (date.today() - timedelta(days=90)).isoformat()
        
        # Validate date range
        date_error = validate_date_range(start_date, end_date)
        if date_error:
            return jsonify({'error': date_error}), 400
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Get student's goals and objectives
        goals = Goal.query.filter(
            Goal.student_id == student_id,
            Goal.active == True
        ).all()
        
        # Get trial logs in date range
        trial_logs = TrialLog.query.filter(
            TrialLog.student_id == student_id,
            TrialLog.session_date.between(start_date_obj, end_date_obj)
        ).order_by(TrialLog.session_date).all()
        
        # Get sessions in date range
        sessions = Session.query.filter(
            Session.student_id == student_id,
            Session.session_date.between(start_date_obj, end_date_obj)
        ).order_by(Session.session_date).all()
        
        # Get SOAP notes in date range
        soap_notes = SOAPNote.query.filter(
            SOAPNote.student_id == student_id,
            SOAPNote.session_date.between(start_date_obj, end_date_obj),
            SOAPNote.anonymized == False
        ).order_by(SOAPNote.session_date).all()
        
        # Calculate progress metrics
        progress_data = {}
        for goal in goals:
            goal_progress = {
                'goal_id': goal.id,
                'description': goal.description,
                'objectives': []
            }
            
            for objective in goal.objectives:
                if not objective.active:
                    continue
                    
                obj_logs = [log for log in trial_logs if log.objective_id == objective.id]
                
                if obj_logs:
                    # Calculate progress over time
                    progress_points = []
                    for log in obj_logs:
                        independence_rate = log.independence_percentage
                        progress_points.append({
                            'date': log.session_date.isoformat(),
                            'independence_rate': independence_rate,
                            'total_trials': log.total_trials_new()
                        })
                    
                    # Calculate trend
                    if len(progress_points) >= 2:
                        first_rate = progress_points[0]['independence_rate']
                        last_rate = progress_points[-1]['independence_rate']
                        trend = last_rate - first_rate
                    else:
                        trend = 0
                    
                    goal_progress['objectives'].append({
                        'objective_id': objective.id,
                        'description': objective.description,
                        'current_progress': objective.current_progress,
                        'accuracy_target': objective.accuracy_target,
                        'progress_points': progress_points,
                        'trend': round(trend, 1),
                        'total_sessions': len(obj_logs)
                    })
            
            progress_data[goal.id] = goal_progress
        
        # Session statistics
        session_stats = {
            'total_sessions': len(sessions),
            'session_types': {},
            'average_duration': 0,
            'attendance_rate': 0
        }
        
        if sessions:
            # Session type distribution
            for session in sessions:
                session_type = session.session_type
                session_stats['session_types'][session_type] = session_stats['session_types'].get(session_type, 0) + 1
            
            # Average duration
            total_duration = sum(session.duration_minutes for session in sessions)
            session_stats['average_duration'] = round(total_duration / len(sessions), 1)
            
            # Attendance rate (completed vs scheduled)
            completed_sessions = len([s for s in sessions if s.status == 'Completed'])
            session_stats['attendance_rate'] = round((completed_sessions / len(sessions)) * 100, 1)
        
        report_data = {
            'student': student.to_dict(),
            'report_period': {
                'start_date': start_date,
                'end_date': end_date,
                'duration_days': (end_date_obj - start_date_obj).days
            },
            'goals_progress': list(progress_data.values()),
            'session_statistics': session_stats,
            'total_trial_logs': len(trial_logs),
            'total_soap_notes': len(soap_notes),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(report_data), 200
        
    except Exception as e:
        logger.error(f"Error generating progress report for student {student_id}: {e}")
        return jsonify({'error': 'Failed to generate progress report'}), 500

@reports_bp.route('/analytics/overview', methods=['GET'])
@token_required
def get_analytics_overview():
    """Get system-wide analytics and insights."""
    try:
        # Date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date', date.today().isoformat())
        
        if not start_date:
            start_date = (date.today() - timedelta(days=30)).isoformat()
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Overall student statistics
        total_students = Student.query.filter(Student.active == True).count()
        anonymized_students = Student.query.filter(Student.anonymized == True).count()
        
        # Grade level distribution
        grade_distribution = db.session.query(
            Student.grade_level,
            db.func.count(Student.id).label('count')
        ).filter(Student.active == True).group_by(Student.grade_level).all()
        
        # Session analytics
        total_sessions = Session.query.filter(
            Session.session_date.between(start_date_obj, end_date_obj)
        ).count()
        
        session_type_stats = db.session.query(
            Session.session_type,
            db.func.count(Session.id).label('count')
        ).filter(
            Session.session_date.between(start_date_obj, end_date_obj)
        ).group_by(Session.session_type).all()
        
        # Trial log analytics
        total_trials = db.session.query(
            db.func.sum(TrialLog.independent + TrialLog.minimal_support + 
                       TrialLog.moderate_support + TrialLog.maximal_support + TrialLog.incorrect)
        ).filter(
            TrialLog.session_date.between(start_date_obj, end_date_obj)
        ).scalar() or 0
        
        # Independence rate analytics
        independence_stats = db.session.query(
            db.func.avg(TrialLog.independent * 100.0 / 
                       (TrialLog.independent + TrialLog.minimal_support + 
                        TrialLog.moderate_support + TrialLog.maximal_support + TrialLog.incorrect)).label('avg_independence')
        ).filter(
            TrialLog.session_date.between(start_date_obj, end_date_obj),
            (TrialLog.independent + TrialLog.minimal_support + 
             TrialLog.moderate_support + TrialLog.maximal_support + TrialLog.incorrect) > 0
        ).scalar() or 0
        
        # SOAP note completion rates
        total_soap_notes = SOAPNote.query.filter(
            SOAPNote.session_date.between(start_date_obj, end_date_obj)
        ).count()
        
        # Monthly trends
        monthly_sessions = db.session.query(
            db.extract('year', Session.session_date).label('year'),
            db.extract('month', Session.session_date).label('month'),
            db.func.count(Session.id).label('count')
        ).filter(
            Session.session_date.between(start_date_obj, end_date_obj)
        ).group_by(
            db.extract('year', Session.session_date),
            db.extract('month', Session.session_date)
        ).order_by('year', 'month').all()
        
        analytics_data = {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'duration_days': (end_date_obj - start_date_obj).days
            },
            'student_analytics': {
                'total_active': total_students,
                'anonymized': anonymized_students,
                'grade_distribution': {grade: count for grade, count in grade_distribution if grade}
            },
            'session_analytics': {
                'total_sessions': total_sessions,
                'session_types': {stype: count for stype, count in session_type_stats},
                'monthly_trends': [
                    {'year': int(year), 'month': int(month), 'sessions': count}
                    for year, month, count in monthly_sessions
                ]
            },
            'trial_analytics': {
                'total_trials': int(total_trials),
                'average_independence_rate': round(float(independence_stats), 1)
            },
            'documentation': {
                'soap_notes_created': total_soap_notes
            },
            'generated_at': datetime.utcnow().isoformat()
        }
        
        return jsonify(analytics_data), 200
        
    except Exception as e:
        logger.error(f"Error generating analytics overview: {e}")
        return jsonify({'error': 'Failed to generate analytics'}), 500

@reports_bp.route('/goal-progress', methods=['GET'])
@token_required
def get_goal_progress_summary():
    """Get progress summary across all active goals."""
    try:
        # Optional student filter
        student_id = request.args.get('student_id', type=int)
        
        query = Goal.query.filter(Goal.active == True)
        if student_id:
            query = query.filter(Goal.student_id == student_id)
        
        goals = query.all()
        
        goal_progress_data = []
        for goal in goals:
            goal_data = {
                'goal_id': goal.id,
                'student_id': goal.student_id,
                'student_name': goal.student.display_name,
                'description': goal.description,
                'target_date': goal.target_date.isoformat() if goal.target_date else None,
                'created_at': goal.created_at.isoformat(),
                'objectives': []
            }
            
            for objective in goal.objectives:
                if objective.active:
                    # Get recent progress
                    recent_logs = TrialLog.query.filter(
                        TrialLog.objective_id == objective.id,
                        TrialLog.session_date >= (date.today() - timedelta(days=30))
                    ).order_by(TrialLog.session_date.desc()).all()
                    
                    # Calculate progress metrics
                    if recent_logs:
                        latest_log = recent_logs[0]
                        avg_independence = sum(log.independence_percentage for log in recent_logs) / len(recent_logs)
                        
                        # Progress trend (comparing first and last entries)
                        if len(recent_logs) > 1:
                            first_rate = recent_logs[-1].independence_percentage  # Oldest first
                            last_rate = recent_logs[0].independence_percentage   # Newest first
                            trend = last_rate - first_rate
                        else:
                            trend = 0
                    else:
                        avg_independence = 0
                        trend = 0
                        latest_log = None
                    
                    goal_data['objectives'].append({
                        'objective_id': objective.id,
                        'description': objective.description,
                        'accuracy_target': objective.accuracy_target,
                        'current_progress': objective.current_progress,
                        'recent_avg_independence': round(avg_independence, 1),
                        'trend': round(trend, 1),
                        'last_session_date': latest_log.session_date.isoformat() if latest_log else None,
                        'total_recent_sessions': len(recent_logs)
                    })
            
            goal_progress_data.append(goal_data)
        
        return jsonify({
            'goals': goal_progress_data,
            'summary': {
                'total_goals': len(goals),
                'total_objectives': sum(len(goal.objectives) for goal in goals),
                'report_generated': datetime.utcnow().isoformat()
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating goal progress summary: {e}")
        return jsonify({'error': 'Failed to generate goal progress summary'}), 500

@reports_bp.route('/attendance', methods=['GET'])
@token_required
def get_attendance_report():
    """Generate attendance report for students."""
    try:
        # Date range parameters
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date', date.today().isoformat())
        
        if not start_date:
            start_date = (date.today() - timedelta(days=30)).isoformat()
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Optional student filter
        student_id = request.args.get('student_id', type=int)
        
        # Get sessions data
        query = Session.query.filter(
            Session.session_date.between(start_date_obj, end_date_obj)
        )
        
        if student_id:
            query = query.filter(Session.student_id == student_id)
        
        sessions = query.all()
        
        # Group by student
        student_attendance = {}
        for session in sessions:
            student_id = session.student_id
            if student_id not in student_attendance:
                student_attendance[student_id] = {
                    'student_name': session.student.display_name,
                    'scheduled': 0,
                    'completed': 0,
                    'cancelled': 0,
                    'no_show': 0,
                    'total_duration': 0
                }
            
            student_data = student_attendance[student_id]
            student_data['scheduled'] += 1
            
            if session.status == 'Completed':
                student_data['completed'] += 1
                student_data['total_duration'] += session.duration_minutes
            elif session.status == 'Cancelled':
                student_data['cancelled'] += 1
            elif session.status == 'No Show':
                student_data['no_show'] += 1
        
        # Calculate rates and add summary data
        attendance_report = []
        for student_id, data in student_attendance.items():
            if data['scheduled'] > 0:
                attendance_rate = round((data['completed'] / data['scheduled']) * 100, 1)
                avg_session_duration = round(data['total_duration'] / max(1, data['completed']), 1)
            else:
                attendance_rate = 0
                avg_session_duration = 0
            
            attendance_report.append({
                'student_id': student_id,
                'student_name': data['student_name'],
                'scheduled_sessions': data['scheduled'],
                'completed_sessions': data['completed'],
                'cancelled_sessions': data['cancelled'],
                'no_show_sessions': data['no_show'],
                'attendance_rate': attendance_rate,
                'total_service_time': data['total_duration'],
                'average_session_duration': avg_session_duration
            })
        
        # Sort by attendance rate (descending)
        attendance_report.sort(key=lambda x: x['attendance_rate'], reverse=True)
        
        # Overall statistics
        total_scheduled = sum(data['scheduled'] for data in student_attendance.values())
        total_completed = sum(data['completed'] for data in student_attendance.values())
        overall_rate = round((total_completed / max(1, total_scheduled)) * 100, 1)
        
        return jsonify({
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'overall_statistics': {
                'total_scheduled': total_scheduled,
                'total_completed': total_completed,
                'overall_attendance_rate': overall_rate,
                'students_tracked': len(attendance_report)
            },
            'student_attendance': attendance_report,
            'generated_at': datetime.utcnow().isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating attendance report: {e}")
        return jsonify({'error': 'Failed to generate attendance report'}), 500

@reports_bp.route('/data-insights', methods=['GET'])
@token_required
def get_data_insights():
    """Generate data-driven insights and recommendations."""
    try:
        insights = []
        
        # Insight 1: Students with declining performance
        declining_students = db.session.query(
            Student.id,
            Student.first_name,
            Student.last_name,
            db.func.avg(TrialLog.independence_percentage).label('avg_independence')
        ).join(TrialLog).filter(
            TrialLog.session_date >= (date.today() - timedelta(days=30)),
            Student.active == True
        ).group_by(Student.id).having(
            db.func.avg(TrialLog.independence_percentage) < 50
        ).all()
        
        if declining_students:
            insights.append({
                'type': 'performance_alert',
                'title': 'Students with Low Independence Rates',
                'description': f'{len(declining_students)} students have independence rates below 50% in the last 30 days',
                'data': [
                    {
                        'student_id': student.id,
                        'name': f"{student.first_name} {student.last_name}",
                        'avg_independence': round(student.avg_independence, 1)
                    }
                    for student in declining_students
                ],
                'recommendation': 'Consider reviewing intervention strategies and support levels for these students'
            })
        
        # Insight 2: Most effective session types
        session_effectiveness = db.session.query(
            Session.session_type,
            db.func.avg(TrialLog.independence_percentage).label('avg_independence'),
            db.func.count(Session.id).label('session_count')
        ).join(
            TrialLog, Session.student_id == TrialLog.student_id
        ).filter(
            Session.session_date >= (date.today() - timedelta(days=60)),
            TrialLog.session_date >= (date.today() - timedelta(days=60))
        ).group_by(Session.session_type).having(
            db.func.count(Session.id) >= 5  # Minimum sample size
        ).order_by(db.func.avg(TrialLog.independence_percentage).desc()).all()
        
        if session_effectiveness:
            insights.append({
                'type': 'effectiveness_analysis',
                'title': 'Session Type Effectiveness',
                'description': 'Performance analysis by session type',
                'data': [
                    {
                        'session_type': result.session_type,
                        'avg_independence': round(result.avg_independence, 1),
                        'session_count': result.session_count
                    }
                    for result in session_effectiveness
                ],
                'recommendation': f'Consider increasing {session_effectiveness[0].session_type} sessions for better outcomes'
            })
        
        # Insight 3: Goal completion patterns
        goal_completion = db.session.query(
            Goal.id,
            Goal.description,
            Student.first_name,
            Student.last_name,
            db.func.max(TrialLog.independence_percentage).label('max_independence')
        ).join(Student).join(Objective).join(TrialLog).filter(
            Goal.active == True,
            TrialLog.session_date >= (date.today() - timedelta(days=90))
        ).group_by(Goal.id).having(
            db.func.max(TrialLog.independence_percentage) >= 80
        ).order_by(db.func.max(TrialLog.independence_percentage).desc()).all()
        
        if goal_completion:
            insights.append({
                'type': 'goal_success',
                'title': 'Goals Approaching Mastery',
                'description': f'{len(goal_completion)} goals have achieved 80%+ independence',
                'data': [
                    {
                        'goal_id': goal.id,
                        'description': goal.description[:100] + '...' if len(goal.description) > 100 else goal.description,
                        'student': f"{goal.first_name} {goal.last_name}",
                        'max_independence': round(goal.max_independence, 1)
                    }
                    for goal in goal_completion[:10]  # Top 10
                ],
                'recommendation': 'Consider transitioning these goals to maintenance or introducing new challenges'
            })
        
        # Insight 4: SOAP note completion rates
        soap_completion = db.session.query(
            db.func.count(Session.id).label('total_sessions'),
            db.func.count(SOAPNote.id).label('soap_notes')
        ).outerjoin(SOAPNote, 
            db.and_(Session.student_id == SOAPNote.student_id,
                   Session.session_date == SOAPNote.session_date)
        ).filter(
            Session.session_date >= (date.today() - timedelta(days=30)),
            Session.status == 'Completed'
        ).first()
        
        if soap_completion and soap_completion.total_sessions > 0:
            completion_rate = round((soap_completion.soap_notes / soap_completion.total_sessions) * 100, 1)
            
            insights.append({
                'type': 'documentation_quality',
                'title': 'SOAP Note Completion Rate',
                'description': f'{completion_rate}% of completed sessions have corresponding SOAP notes',
                'data': {
                    'total_sessions': soap_completion.total_sessions,
                    'documented_sessions': soap_completion.soap_notes,
                    'completion_rate': completion_rate
                },
                'recommendation': 'Improve documentation compliance' if completion_rate < 80 else 'Excellent documentation compliance'
            })
        
        return jsonify({
            'insights': insights,
            'generated_at': datetime.utcnow().isoformat(),
            'analysis_period': '30-90 days (varies by insight type)'
        }), 200
        
    except Exception as e:
        logger.error(f"Error generating data insights: {e}")
        return jsonify({'error': 'Failed to generate insights'}), 500

@reports_bp.route('/export/<report_type>', methods=['GET'])
@token_required
@role_required(['admin', 'teacher'])
def export_report(report_type):
    """Export reports in different formats (CSV, JSON)."""
    try:
        format_type = request.args.get('format', 'json').lower()
        
        if report_type not in ['students', 'sessions', 'trial_logs', 'goals']:
            return jsonify({'error': 'Invalid report type'}), 400
        
        if format_type not in ['json', 'csv']:
            return jsonify({'error': 'Invalid format type'}), 400
        
        # Date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date', date.today().isoformat())
        
        if not start_date:
            start_date = (date.today() - timedelta(days=90)).isoformat()
        
        start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Generate data based on report type
        if report_type == 'students':
            data = [student.to_dict() for student in Student.query.filter(Student.active == True).all()]
        elif report_type == 'sessions':
            sessions = Session.query.filter(
                Session.session_date.between(start_date_obj, end_date_obj)
            ).all()
            data = [session.to_dict() for session in sessions]
        elif report_type == 'trial_logs':
            logs = TrialLog.query.filter(
                TrialLog.session_date.between(start_date_obj, end_date_obj)
            ).all()
            data = [log.to_dict() for log in logs]
        elif report_type == 'goals':
            goals = Goal.query.filter(Goal.active == True).all()
            data = [goal.to_dict() for goal in goals]
        
        if format_type == 'json':
            response = make_response(jsonify({
                'report_type': report_type,
                'period': {'start_date': start_date, 'end_date': end_date},
                'data': data,
                'exported_at': datetime.utcnow().isoformat()
            }))
            response.headers['Content-Disposition'] = f'attachment; filename={report_type}_report.json'
            return response
        
        # CSV format would require additional implementation
        return jsonify({'error': 'CSV export not yet implemented'}), 501
        
    except Exception as e:
        logger.error(f"Error exporting {report_type} report: {e}")
        return jsonify({'error': 'Failed to export report'}), 500