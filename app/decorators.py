from functools import wraps
from flask import flash, redirect, url_for, request, jsonify
from flask_login import current_user

def role_required(role_name=None, min_hierarchy=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            is_ajax = request.is_json or request.headers.get('Accept') == 'application/json' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            if not current_user.is_authenticated:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'Session expired or authentication required. Please log in.',
                        'redirect': url_for('auth.login')
                    }), 401
                flash('Please log in to access this section.', 'warning')
                return redirect(url_for('auth.login'))
            
            user_role = current_user.role
            user_level = user_role.hierarchy_level if (user_role and hasattr(user_role, 'hierarchy_level')) else 1
            can_override = user_role.can_override if (user_role and hasattr(user_role, 'can_override')) else False
            role_name_str = user_role.role_name if (user_role and hasattr(user_role, 'role_name')) else ''

            if role_name and role_name_str != role_name and not can_override:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'Unauthorized access: Insufficient privileges for this section.'
                    }), 403
                flash('Unauthorized access: Insufficient privileges for this section.', 'danger')
                return redirect(url_for('public.index'))
                
            if min_hierarchy and user_level < min_hierarchy and not can_override:
                if is_ajax:
                    return jsonify({
                        'success': False,
                        'message': 'Unauthorized access: Insufficient hierarchy level.'
                    }), 403
                flash('Unauthorized access: Insufficient hierarchy level.', 'danger')
                return redirect(url_for('public.index'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def superadmin_only(f):
    return role_required(min_hierarchy=4)(f)

def admin_only(f):
    return role_required(min_hierarchy=3)(f)

def agent_only(f):
    return role_required(role_name='Agent')(f)
