from datetime import datetime, date, timedelta
from extensions import db
from models import Student, Goal, Objective, Session, TrialLog, SOAPNote
import io
import base64
from typing import Dict, List, Optional, Tuple

# Optional imports for visualization and export
try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

def generate_progress_report(student_id: int, start_date: date, end_date: date) -> Dict:
    """Generate comprehensive progress report for a student."""
    student = Student.query.get(student_id)
    if not student:
        raise ValueError(f"Student with ID {student_id} not found")
    
    # Get all relevant data
    goals = Goal.query.filter(Goal.student_id == student_id, Goal.active == True).all()
    trial_logs = TrialLog.query.filter(
        TrialLog.student_id == student_id,
        TrialLog.session_date.between(start_date, end_date)
    ).order_by(TrialLog.session_date).all()
    
    sessions = Session.query.filter(
        Session.student_id == student_id,
        Session.session_date.between(start_date, end_date)
    ).all()
    
    # Calculate progress metrics
    progress_summary = calculate_progress_metrics(trial_logs, goals)
    attendance_summary = calculate_attendance_metrics(sessions)
    
    return {
        'student_info': student.to_dict(),
        'report_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        },
        'progress_summary': progress_summary,
        'attendance_summary': attendance_summary,
        'recommendations': generate_recommendations(progress_summary, attendance_summary)
    }

def calculate_progress_metrics(trial_logs: List[TrialLog], goals: List[Goal]) -> Dict:
    """Calculate detailed progress metrics from trial logs."""
    if not trial_logs:
        return {
            'total_trials': 0,
            'average_independence': 0,
            'progress_trend': 'No data',
            'goal_progress': []
        }
    
    # Overall metrics
    total_trials = sum(log.total_trials for log in trial_logs)
    total_independent = sum(log.independent for log in trial_logs)
    average_independence = round((total_independent / total_trials) * 100, 1) if total_trials > 0 else 0
    
    # Calculate trend (first vs last month)
    if len(trial_logs) >= 2:
        midpoint = len(trial_logs) // 2
        first_half_logs = trial_logs[:midpoint]
        second_half_logs = trial_logs[midpoint:]
        
        first_half_independence = calculate_independence_rate(first_half_logs)
        second_half_independence = calculate_independence_rate(second_half_logs)
        
        trend_change = second_half_independence - first_half_independence
        if trend_change > 5:
            progress_trend = 'Improving'
        elif trend_change < -5:
            progress_trend = 'Declining'
        else:
            progress_trend = 'Stable'
    else:
        progress_trend = 'Insufficient data'
    
    # Goal-specific progress
    goal_progress = []
    for goal in goals:
        goal_logs = [log for log in trial_logs if any(obj.goal_id == goal.id for obj in goal.objectives if log.objective_id == obj.id)]
        
        if goal_logs:
            goal_independence = calculate_independence_rate(goal_logs)
            goal_trials = sum(log.total_trials for log in goal_logs)
            
            goal_progress.append({
                'goal_id': goal.id,
                'description': goal.description,
                'independence_rate': goal_independence,
                'total_trials': goal_trials,
                'sessions_count': len(goal_logs)
            })
    
    return {
        'total_trials': total_trials,
        'average_independence': average_independence,
        'progress_trend': progress_trend,
        'goal_progress': goal_progress,
        'session_count': len(set(log.session_date for log in trial_logs))
    }

def calculate_independence_rate(trial_logs: List[TrialLog]) -> float:
    """Calculate independence rate from trial logs."""
    if not trial_logs:
        return 0.0
    
    total_trials = sum(log.total_trials for log in trial_logs)
    total_independent = sum(log.independent for log in trial_logs)
    
    return round((total_independent / total_trials) * 100, 1) if total_trials > 0 else 0.0

def calculate_attendance_metrics(sessions: List[Session]) -> Dict:
    """Calculate attendance and session metrics."""
    if not sessions:
        return {
            'total_sessions': 0,
            'attendance_rate': 0,
            'average_duration': 0,
            'session_types': {}
        }
    
    total_sessions = len(sessions)
    completed_sessions = len([s for s in sessions if s.status == 'Completed'])
    attendance_rate = round((completed_sessions / total_sessions) * 100, 1)
    
    # Average session duration
    completed_session_durations = [s.duration_minutes for s in sessions if s.status == 'Completed']
    average_duration = round(sum(completed_session_durations) / len(completed_session_durations), 1) if completed_session_durations else 0
    
    # Session type distribution
    session_types = {}
    for session in sessions:
        session_type = session.session_type
        session_types[session_type] = session_types.get(session_type, 0) + 1
    
    return {
        'total_sessions': total_sessions,
        'completed_sessions': completed_sessions,
        'attendance_rate': attendance_rate,
        'average_duration': average_duration,
        'session_types': session_types
    }

def generate_recommendations(progress_summary: Dict, attendance_summary: Dict) -> List[str]:
    """Generate actionable recommendations based on data analysis."""
    recommendations = []
    
    # Independence rate recommendations
    if progress_summary.get('average_independence', 0) < 50:
        recommendations.append("Consider increasing support levels and breaking down tasks into smaller steps")
        recommendations.append("Review current intervention strategies for effectiveness")
    elif progress_summary.get('average_independence', 0) > 80:
        recommendations.append("Student is showing high independence - consider advancing to more complex objectives")
        recommendations.append("Explore opportunities for skill generalization across settings")
    
    # Progress trend recommendations
    trend = progress_summary.get('progress_trend', '')
    if trend == 'Declining':
        recommendations.append("Progress is declining - schedule team meeting to review intervention plan")
        recommendations.append("Consider environmental factors or changes that may be affecting performance")
    elif trend == 'Improving':
        recommendations.append("Progress is positive - maintain current intervention strategies")
    
    # Attendance recommendations
    attendance_rate = attendance_summary.get('attendance_rate', 0)
    if attendance_rate < 80:
        recommendations.append("Low attendance rate - consider scheduling challenges or barriers")
        recommendations.append("Engage with family to improve consistency of services")
    
    # Session duration recommendations
    avg_duration = attendance_summary.get('average_duration', 0)
    if avg_duration < 30:
        recommendations.append("Sessions are short - consider if duration is appropriate for objectives")
    elif avg_duration > 60:
        recommendations.append("Long sessions - monitor for fatigue and attention span")
    
    return recommendations if recommendations else ["Continue current intervention approach - data shows stable progress"]

def generate_analytics_data(date_range: Tuple[date, date]) -> Dict:
    """Generate system-wide analytics data."""
    start_date, end_date = date_range
    
    # Student analytics
    total_students = Student.query.filter(Student.active == True).count()
    students_with_data = db.session.query(Student.id).join(TrialLog).filter(
        TrialLog.session_date.between(start_date, end_date),
        Student.active == True
    ).distinct().count()
    
    # Goal analytics
    active_goals = Goal.query.filter(Goal.active == True).count()
    goals_with_progress = db.session.query(Goal.id).join(Objective).join(TrialLog).filter(
        TrialLog.session_date.between(start_date, end_date),
        Goal.active == True
    ).distinct().count()
    
    # Session analytics
    total_sessions = Session.query.filter(
        Session.session_date.between(start_date, end_date)
    ).count()
    
    # Trial analytics
    trial_logs = TrialLog.query.filter(
        TrialLog.session_date.between(start_date, end_date)
    ).all()
    
    if trial_logs:
        total_trials = sum(log.total_trials for log in trial_logs)
        average_independence = calculate_independence_rate(trial_logs)
    else:
        total_trials = 0
        average_independence = 0
    
    return {
        'student_engagement': {
            'total_active_students': total_students,
            'students_with_data': students_with_data,
            'engagement_rate': round((students_with_data / total_students) * 100, 1) if total_students > 0 else 0
        },
        'goal_progress': {
            'active_goals': active_goals,
            'goals_with_progress': goals_with_progress,
            'progress_tracking_rate': round((goals_with_progress / active_goals) * 100, 1) if active_goals > 0 else 0
        },
        'service_delivery': {
            'total_sessions': total_sessions,
            'total_trials': total_trials,
            'average_independence_rate': average_independence
        }
    }

def create_progress_visualization(trial_logs: List[TrialLog], objective_id: Optional[int] = None) -> str:
    """Create a progress visualization chart and return as base64 string."""
    if not MATPLOTLIB_AVAILABLE:
        return None
    
    try:
        # Filter for specific objective if provided
        if objective_id:
            trial_logs = [log for log in trial_logs if log.objective_id == objective_id]
        
        if not trial_logs:
            return None
        
        # Prepare data for visualization
        dates = [log.session_date for log in trial_logs]
        independence_rates = [log.independence_percentage for log in trial_logs]
        
        # Create the plot
        plt.figure(figsize=(12, 6))
        plt.plot(dates, independence_rates, marker='o', linewidth=2, markersize=6)
        plt.title('Independence Rate Progress Over Time', fontsize=16, fontweight='bold')
        plt.xlabel('Session Date', fontsize=12)
        plt.ylabel('Independence Rate (%)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 100)
        
        # Add trend line
        if len(dates) > 1 and PANDAS_AVAILABLE:
            z = np.polyfit(range(len(dates)), independence_rates, 1)
            p = np.poly1d(z)
            plt.plot(dates, p(range(len(dates))), "--", alpha=0.7, color='red', label='Trend')
            plt.legend()
        
        # Format x-axis
        plt.xticks(rotation=45)
        plt.tight_layout()
        
        # Convert to base64 string
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        img_buffer.seek(0)
        img_string = base64.b64encode(img_buffer.read()).decode()
        plt.close()
        
        return img_string
        
    except Exception as e:
        print(f"Error creating visualization: {e}")
        return None

def generate_goal_mastery_report(goal_id: int, date_range: Tuple[date, date]) -> Dict:
    """Generate detailed mastery report for a specific goal."""
    start_date, end_date = date_range
    
    goal = Goal.query.get(goal_id)
    if not goal:
        raise ValueError(f"Goal with ID {goal_id} not found")
    
    # Get all objectives for this goal
    objectives = Objective.query.filter(Objective.goal_id == goal_id, Objective.active == True).all()
    
    objective_progress = []
    for objective in objectives:
        # Get trial logs for this objective
        logs = TrialLog.query.filter(
            TrialLog.objective_id == objective.id,
            TrialLog.session_date.between(start_date, end_date)
        ).order_by(TrialLog.session_date).all()
        
        if logs:
            # Calculate mastery metrics
            current_independence = logs[-1].independence_percentage
            average_independence = calculate_independence_rate(logs)
            
            # Check for mastery (80% independence for 3+ consecutive sessions)
            mastery_achieved = check_mastery_criteria(logs)
            
            # Calculate progress velocity (improvement rate)
            velocity = calculate_progress_velocity(logs)
            
            objective_progress.append({
                'objective_id': objective.id,
                'description': objective.description,
                'accuracy_target': objective.accuracy_target,
                'current_independence': current_independence,
                'average_independence': average_independence,
                'mastery_achieved': mastery_achieved,
                'progress_velocity': velocity,
                'total_sessions': len(logs),
                'trial_data': [log.to_dict() for log in logs[-10:]]  # Last 10 sessions
            })
    
    # Overall goal assessment
    goal_mastery_rate = sum(1 for obj in objective_progress if obj['mastery_achieved']) / len(objective_progress) if objective_progress else 0
    
    return {
        'goal': goal.to_dict(),
        'overall_mastery_rate': round(goal_mastery_rate * 100, 1),
        'objectives_progress': objective_progress,
        'recommendations': generate_goal_recommendations(objective_progress),
        'report_period': {
            'start_date': start_date.isoformat(),
            'end_date': end_date.isoformat()
        }
    }

def check_mastery_criteria(trial_logs: List[TrialLog], threshold: float = 80.0, consecutive_sessions: int = 3) -> bool:
    """Check if mastery criteria are met (configurable threshold and consecutive sessions)."""
    if len(trial_logs) < consecutive_sessions:
        return False
    
    # Check last N sessions for consecutive mastery
    recent_logs = trial_logs[-consecutive_sessions:]
    return all(log.independence_percentage >= threshold for log in recent_logs)

def calculate_progress_velocity(trial_logs: List[TrialLog]) -> float:
    """Calculate rate of improvement (percentage points per session)."""
    if len(trial_logs) < 2:
        return 0.0
    
    # Use linear regression to calculate slope
    sessions = list(range(len(trial_logs)))
    independence_rates = [log.independence_percentage for log in trial_logs]
    
    # Simple linear regression calculation
    n = len(sessions)
    sum_x = sum(sessions)
    sum_y = sum(independence_rates)
    sum_xy = sum(x * y for x, y in zip(sessions, independence_rates))
    sum_x2 = sum(x * x for x in sessions)
    
    # Calculate slope (velocity)
    denominator = n * sum_x2 - sum_x * sum_x
    if denominator == 0:
        return 0.0
    
    velocity = (n * sum_xy - sum_x * sum_y) / denominator
    return round(velocity, 2)

def generate_goal_recommendations(objective_progress: List[Dict]) -> List[str]:
    """Generate recommendations based on goal progress analysis."""
    recommendations = []
    
    # Count objectives in different states
    mastered_count = sum(1 for obj in objective_progress if obj['mastery_achieved'])
    total_count = len(objective_progress)
    
    if mastered_count == total_count and total_count > 0:
        recommendations.append("All objectives mastered - consider transitioning to new goal or maintenance phase")
    elif mastered_count / total_count > 0.7 if total_count > 0 else False:
        recommendations.append("Most objectives are mastered - prepare for goal transition")
    elif mastered_count == 0 and total_count > 0:
        recommendations.append("No objectives mastered yet - review intervention intensity and strategies")
    
    # Analyze progress velocity
    low_velocity_objectives = [obj for obj in objective_progress if obj['progress_velocity'] < 0.5]
    if low_velocity_objectives:
        recommendations.append(f"{len(low_velocity_objectives)} objectives showing slow progress - consider strategy modifications")
    
    high_velocity_objectives = [obj for obj in objective_progress if obj['progress_velocity'] > 2.0]
    if high_velocity_objectives:
        recommendations.append(f"{len(high_velocity_objectives)} objectives progressing rapidly - consider increasing complexity")
    
    return recommendations if recommendations else ["Continue current intervention approach"]

def export_data_to_csv(data: List[Dict], filename: str) -> str:
    """Export data to CSV format and return file path."""
    if not PANDAS_AVAILABLE:
        raise Exception("Pandas is required for CSV export but is not available")
    
    try:
        df = pd.DataFrame(data)
        filepath = f"/tmp/{filename}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(filepath, index=False)
        return filepath
    except Exception as e:
        raise Exception(f"Error exporting to CSV: {e}")

def calculate_system_health_metrics() -> Dict:
    """Calculate overall system health and usage metrics."""
    thirty_days_ago = date.today() - timedelta(days=30)
    
    # Data completeness metrics
    total_students = Student.query.filter(Student.active == True).count()
    students_with_goals = db.session.query(Student.id).join(Goal).filter(
        Student.active == True,
        Goal.active == True
    ).distinct().count()
    
    students_with_recent_data = db.session.query(Student.id).join(TrialLog).filter(
        Student.active == True,
        TrialLog.session_date >= thirty_days_ago
    ).distinct().count()
    
    # Documentation metrics
    recent_sessions = Session.query.filter(Session.session_date >= thirty_days_ago).count()
    recent_soap_notes = SOAPNote.query.filter(SOAPNote.session_date >= thirty_days_ago).count()
    
    # Data quality metrics
    trial_logs_with_data = TrialLog.query.filter(
        TrialLog.session_date >= thirty_days_ago,
        (TrialLog.independent + TrialLog.minimal_support + 
         TrialLog.moderate_support + TrialLog.maximal_support + TrialLog.incorrect) > 0
    ).count()
    
    total_recent_trial_logs = TrialLog.query.filter(TrialLog.session_date >= thirty_days_ago).count()
    
    return {
        'data_completeness': {
            'students_with_goals_rate': round((students_with_goals / total_students) * 100, 1) if total_students > 0 else 0,
            'students_with_recent_data_rate': round((students_with_recent_data / total_students) * 100, 1) if total_students > 0 else 0
        },
        'documentation_rate': {
            'soap_note_completion_rate': round((recent_soap_notes / recent_sessions) * 100, 1) if recent_sessions > 0 else 0
        },
        'data_quality': {
            'complete_trial_logs_rate': round((trial_logs_with_data / total_recent_trial_logs) * 100, 1) if total_recent_trial_logs > 0 else 0
        },
        'system_utilization': {
            'active_students': total_students,
            'recent_sessions': recent_sessions,
            'recent_trial_entries': total_recent_trial_logs
        }
    }