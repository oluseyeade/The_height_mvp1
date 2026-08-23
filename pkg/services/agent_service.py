import secrets
from datetime import datetime, timezone
from pkg.repositories.agent_repository import AgentRepository, AgentCommissionRepository
from pkg.repositories.user_repository import UserRepository
from pkg.models.user import User, Agent, RoleHierarchy
from pkg.models.agent import AgentCommission
from pkg.services.audit_service import AuditService
from pkg.extensions import db

class AgentService:
    def __init__(self):
        self.agent_repo = AgentRepository()
        self.user_repo = UserRepository()
        self.comm_repo = AgentCommissionRepository()

    def register_agent(self, full_name, email, password, phone, bank_name=None, account_number=None, account_holder_name=None):
        existing_user = self.user_repo.find_by_email(email)
        if existing_user:
            return False, "An account with this email address already exists.", None

        agent_role = self.user_repo.get_role_by_name('Agent')
        if not agent_role:
            return False, "Agent role is not configured.", None

        # 1. Create User
        user = User(
            full_name=full_name.strip(),
            email=email.lower().strip(),
            phone=phone.strip(),
            role_id=agent_role.role_id,
            status='active'
        )
        user.set_password(password)
        self.user_repo.add(user)
        self.user_repo.commit()

        # 2. Generate unique Agent Code (e.g. THA-AGT-8912)
        agent_code = f"THA-AGT-{secrets.randbelow(8999) + 1000}"

        # 3. Create Agent Profile
        agent = Agent(
            user_id=user.user_id,
            agent_code=agent_code,
            commission_rate=5.0,  # 5% default referral commission
            bank_name=bank_name.strip() if bank_name else None,
            account_number=account_number.strip() if account_number else None,
            account_holder_name=account_holder_name.strip() if account_holder_name else None,
            status='active'
        )
        self.agent_repo.add(agent)
        self.agent_repo.commit()

        AuditService.log_activity(
            user_id=user.user_id,
            activity_type='AGENT_REGISTRATION',
            description=f"Partner Agent account created for {user.email} with Code: {agent_code}.",
            module='Agent',
            action='register'
        )

        return True, f"Partner Agent account registered successfully! Your Agent Referral Code is: {agent_code}", agent

    def calculate_and_award_commission(self, booking):
        if not booking.agent_id or booking.status != 'confirmed':
            return None

        agent = self.agent_repo.get_by_id(booking.agent_id)
        if not agent or agent.status != 'active':
            return None

        commission_amount = (booking.final_amount * agent.commission_rate) / 100.0

        comm = AgentCommission(
            agent_id=agent.agent_id,
            booking_id=booking.booking_id,
            booking_amount=booking.final_amount,
            commission_percentage=agent.commission_rate,
            commission_amount=commission_amount,
            status='pending'
        )
        self.comm_repo.add(comm)

        agent.pending_commission = (agent.pending_commission or 0.0) + commission_amount
        self.agent_repo.commit()

        return comm

    def mark_commission_paid(self, commission_id, payment_reference, admin_user_id=None):
        comm = self.comm_repo.get_by_id(commission_id)
        if not comm or comm.status == 'paid':
            return False, "Commission record not found or already paid."

        comm.status = 'paid'
        comm.paid_date = datetime.now(timezone.utc)
        comm.payment_reference = payment_reference

        agent = comm.agent
        agent.pending_commission = max(0.0, (agent.pending_commission or 0.0) - comm.commission_amount)
        agent.total_earnings = (agent.total_earnings or 0.0) + comm.commission_amount
        self.comm_repo.commit()

        if admin_user_id:
            AuditService.log_admin_action(
                admin_id=admin_user_id,
                target_user_id=agent.user_id,
                action_type='COMMISSION_PAID',
                previous_status='pending',
                new_status='paid',
                reason=f"Paid manual commission of ₦{comm.commission_amount:,.2f} for Agent {agent.agent_code}"
            )

        return True, f"Commission of ₦{comm.commission_amount:,.2f} marked as PAID."
