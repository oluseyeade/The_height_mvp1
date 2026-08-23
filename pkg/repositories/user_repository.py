from pkg.repositories.base_repository import BaseRepository
from pkg.models.user import User, Role, Admin, Agent

class UserRepository(BaseRepository):
    def __init__(self):
        super().__init__(User)

    def find_by_email(self, email):
        return User.query.filter_by(email=email.lower().strip()).first()

    def find_by_role(self, role_name):
        return User.query.join(Role).filter(Role.role_name == role_name).all()

    def get_role_by_name(self, role_name):
        return Role.query.filter_by(role_name=role_name).first()

    def get_all_roles(self):
        return Role.query.order_by(Role.hierarchy_level.asc()).all()

    def find_agent_by_code(self, agent_code):
        return Agent.query.filter_by(agent_code=agent_code).first()
