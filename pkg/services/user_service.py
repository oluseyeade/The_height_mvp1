from datetime import datetime, timezone
from flask_login import login_user, logout_user
from pkg.repositories.user_repository import UserRepository
from pkg.services.audit_service import AuditService
from pkg.models.user import User, Admin, Agent

class UserService:
    def __init__(self):
        self.user_repo = UserRepository()

    def authenticate(self, email, password):
        user = self.user_repo.find_by_email(email)
        if not user or not user.check_password(password):
            return False, "Invalid email address or password.", None

        if user.status != 'active':
            return False, f"Account is currently {user.status}. Please contact support.", None

        user.last_login = datetime.now(timezone.utc)
        self.user_repo.commit()

        login_user(user)
        AuditService.log_activity(
            user_id=user.user_id,
            activity_type='AUTHENTICATION',
            description=f'User {user.email} logged in successfully.',
            module='Auth',
            action='login'
        )
        return True, "Login successful.", user

    def register_user(self, full_name, email, password, phone=None, role_name='User'):
        existing_user = self.user_repo.find_by_email(email)
        if existing_user:
            return False, "An account with this email already exists.", None

        role = self.user_repo.get_role_by_name(role_name)
        if not role:
            return False, f"Role '{role_name}' does not exist.", None

        new_user = User(
            full_name=full_name.strip(),
            email=email.lower().strip(),
            phone=phone.strip() if phone else None,
            role_id=role.role_id,
            status='active'
        )
        new_user.set_password(password)

        self.user_repo.add(new_user)
        self.user_repo.commit()

        # Create sub-profiles if needed
        if role_name == 'Admin' or role_name == 'SuperAdmin':
            admin_profile = Admin(user_id=new_user.user_id)
            self.user_repo.add(admin_profile)
            self.user_repo.commit()

        AuditService.log_activity(
            user_id=new_user.user_id,
            activity_type='USER_REGISTRATION',
            description=f'New account created for {new_user.email} with role {role_name}.',
            module='Auth',
            action='register'
        )

        return True, "Registration successful. You can now log in.", new_user

    def logout_current_user(self, user):
        if user and user.is_authenticated:
            AuditService.log_activity(
                user_id=user.user_id,
                activity_type='AUTHENTICATION',
                description=f'User {user.email} logged out.',
                module='Auth',
                action='logout'
            )
            logout_user()
        return True, "Logged out successfully."
