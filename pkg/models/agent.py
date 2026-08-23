from datetime import datetime, timezone
from pkg.extensions import db

class AgentCommission(db.Model):
    __tablename__ = 'agent_commissions'

    commission_id = db.Column(db.Integer, primary_key=True)
    agent_id = db.Column(db.Integer, db.ForeignKey('agents.agent_id'), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey('bookings.booking_id'), nullable=False)

    booking_amount = db.Column(db.Float, nullable=False)
    commission_percentage = db.Column(db.Float, default=5.0, nullable=False)
    commission_amount = db.Column(db.Float, nullable=False)
    
    status = db.Column(db.String(20), default='pending', nullable=False)  # pending, paid, cancelled
    paid_date = db.Column(db.DateTime, nullable=True)
    payment_reference = db.Column(db.String(100), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    agent = db.relationship('Agent', backref='commissions')
    booking = db.relationship('Booking', backref='agent_commission')

    def __repr__(self):
        return f"<AgentCommission agent_id={self.agent_id} amount=₦{self.commission_amount:,.2f} ({self.status})>"
