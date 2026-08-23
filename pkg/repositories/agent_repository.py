from pkg.repositories.base_repository import BaseRepository
from pkg.models.user import Agent
from pkg.models.agent import AgentCommission

class AgentRepository(BaseRepository):
    def __init__(self):
        super().__init__(Agent)

    def find_by_user_id(self, user_id):
        return Agent.query.filter_by(user_id=user_id).first()

    def find_by_code(self, agent_code):
        return Agent.query.filter_by(agent_code=agent_code.upper().strip()).first()


class AgentCommissionRepository(BaseRepository):
    def __init__(self):
        super().__init__(AgentCommission)

    def get_commissions_by_agent(self, agent_id):
        return AgentCommission.query.filter_by(agent_id=agent_id).order_by(AgentCommission.created_at.desc()).all()
