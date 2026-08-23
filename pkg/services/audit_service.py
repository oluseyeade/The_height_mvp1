import json
from flask import request
from pkg.extensions import db
from pkg.models.audit_log import AuditLog, AdminActionLog, SuperAdminActionLog

class AuditService:
    @staticmethod
    def log_activity(user_id, activity_type, description, module, action, old_values=None, new_values=None):
        try:
            ip_address = request.remote_addr if request else None
            user_agent = str(request.user_agent) if request else None

            log = AuditLog(
                user_id=user_id,
                activity_type=activity_type,
                description=description,
                module=module,
                action=action,
                old_values=json.dumps(old_values) if old_values else None,
                new_values=json.dumps(new_values) if new_values else None,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            db.session.rollback()
            # Fallback logging without failing the main transaction
            print(f"[AUDIT LOG FAILURE]: {str(e)}")
            return None

    @staticmethod
    def log_admin_action(admin_id, target_user_id, action_type, previous_status=None, new_status=None, reason=None):
        try:
            ip = request.remote_addr if request else None
            log = AdminActionLog(
                admin_id=admin_id,
                target_user_id=target_user_id,
                action_type=action_type,
                previous_status=previous_status,
                new_status=new_status,
                reason=reason,
                ip_address=ip
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            db.session.rollback()
            print(f"[ADMIN AUDIT LOG FAILURE]: {str(e)}")
            return None

    @staticmethod
    def log_superadmin_action(superadmin_id, action_type, target_admin_id=None, target_agent_id=None, previous_role=None, new_role=None, reason=None):
        try:
            ip = request.remote_addr if request else None
            log = SuperAdminActionLog(
                superadmin_id=superadmin_id,
                target_admin_id=target_admin_id,
                target_agent_id=target_agent_id,
                action_type=action_type,
                previous_role=previous_role,
                new_role=new_role,
                reason=reason,
                ip_address=ip
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            db.session.rollback()
            print(f"[SUPERADMIN AUDIT LOG FAILURE]: {str(e)}")
            return None
