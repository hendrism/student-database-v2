from flask import jsonify, current_app
from datetime import datetime
from extensions import db
from models import Student, Goal
from sqlalchemy import text

from . import bp_api

@bp_api.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    try:
        db.session.execute(text('SELECT 1'))
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.utcnow().replace(microsecond=0).isoformat(),
            'version': '2.0.0',
            'database': 'ok'
        }), 200
    except Exception as e:
        current_app.logger.error(f'Health check failed: {str(e)}')
        return jsonify({
            'status': 'unhealthy',
            'error': 'Database connection failed',
            'timestamp': datetime.utcnow().replace(microsecond=0).isoformat()
        }), 503

@bp_api.route('/v1/health', methods=['GET'])
def health_check_v1():
    """Alias for /api/health for backward compatibility."""
    return health_check()

# Simple dashboard analytics
@bp_api.route('/analytics/dashboard', methods=['GET'])
def get_dashboard_analytics():
    """Get dashboard analytics data."""
    try:
        total_students = Student.query.filter(Student.active.is_(True)).count()
        total_goals = Goal.query.filter(Goal.active.is_(True)).count()

        return jsonify({
            'stats': {
                'total_students': total_students,
                'total_goals': total_goals,
                'sessions_this_week': 0,
                'completion_rate': 95
            },
            'recent_activity': []
        })
    except Exception as e:
        current_app.logger.error(f'Error retrieving dashboard analytics: {str(e)}')
        return jsonify({'error': 'Failed to retrieve analytics'}), 500
