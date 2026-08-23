from functools import wraps
from flask import flash, redirect, url_for, request
from flask_login import current_user
from pkg.models.user import RoleHierarchy

def role_required(*allowed_hierarchy_levels):
    """
    Decorator to restrict access to endpoints based on user role hierarchy level.
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            if current_user.role.hierarchy_level not in allowed_hierarchy_levels:
                # SuperAdmin override capability
                if current_user.role.hierarchy_level == RoleHierarchy.SUPERADMIN and current_user.role.can_override:
                    return f(*args, **kwargs)

                flash('Access denied. You do not have sufficient permissions for this area.', 'danger')
                return redirect(url_for('public.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def superadmin_only(f):
    return role_required(RoleHierarchy.SUPERADMIN)(f)

def admin_only(f):
    return role_required(RoleHierarchy.ADMIN, RoleHierarchy.SUPERADMIN)(f)

def agent_only(f):
    return role_required(RoleHierarchy.AGENT, RoleHierarchy.SUPERADMIN)(f)
