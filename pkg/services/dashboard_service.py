from sqlalchemy import func
from pkg.models.booking import Booking
from pkg.models.payment import Payment
from pkg.models.apartment import Apartment
from pkg.models.user import User, Agent
from pkg.models.corporate import CorporateEnquiry
from pkg.models.audit_log import AuditLog
from pkg.extensions import db

class DashboardService:
    @staticmethod
    def get_admin_metrics():
        """
        Returns real-time operational metrics for Admin Dashboard.
        """
        total_bookings = Booking.query.count()
        pending_bookings = Booking.query.filter_by(status='pending').count()
        confirmed_bookings = Booking.query.filter_by(status='confirmed').count()
        
        # Calculate Total Verified Revenue
        verified_payments = db.session.query(func.sum(Payment.amount)).filter_by(status='verified').scalar() or 0.0
        pending_payments_count = Payment.query.filter_by(status='pending').count()

        total_apartments = Apartment.query.count()
        available_apartments = Apartment.query.filter_by(status='available').count()
        occupancy_rate = ((total_apartments - available_apartments) / total_apartments * 100.0) if total_apartments > 0 else 0.0

        new_corporate_enquiries = CorporateEnquiry.query.filter_by(status='new').count()

        return {
            'total_bookings': total_bookings,
            'pending_bookings': pending_bookings,
            'confirmed_bookings': confirmed_bookings,
            'total_revenue': verified_payments,
            'pending_payments_count': pending_payments_count,
            'total_apartments': total_apartments,
            'available_apartments': available_apartments,
            'occupancy_rate': round(occupancy_rate, 1),
            'new_corporate_enquiries': new_corporate_enquiries
        }

    @staticmethod
    def get_superadmin_metrics():
        """
        Returns platform-wide governance metrics for SuperAdmin Dashboard.
        """
        base_metrics = DashboardService.get_admin_metrics()
        total_users = User.query.count()
        total_agents = Agent.query.count()
        recent_audit_logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(10).all()

        base_metrics.update({
            'total_users': total_users,
            'total_agents': total_agents,
            'recent_audit_logs': recent_audit_logs
        })
        return base_metrics
