from app.routes.public import init_public_routes
from app.routes.auth import init_auth_routes
from app.routes.apartment import init_apartment_routes
from app.routes.booking import init_booking_routes
from app.routes.receipt import init_receipt_routes
from app.routes.corporate import init_corporate_routes
from app.routes.agent import init_agent_routes
from app.routes.admin import init_admin_routes
from app.routes.superadmin import init_superadmin_routes
from app.routes.payment import init_payment_routes
from app.routes.inspection import init_inspection_routes
from app.routes.refund import init_refund_routes

def init_routes(app):
    init_public_routes(app)
    init_auth_routes(app)
    init_apartment_routes(app)
    init_booking_routes(app)
    init_receipt_routes(app)
    init_corporate_routes(app)
    init_agent_routes(app)
    init_admin_routes(app)
    init_superadmin_routes(app)
    init_payment_routes(app)
    init_inspection_routes(app)
    init_refund_routes(app)
