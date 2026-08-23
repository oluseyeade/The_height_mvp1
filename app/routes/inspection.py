from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user
from app.decorators import admin_only
from app.models import Booking, Inspection
from app.services import InspectionService, BookingService

booking_service = BookingService()
inspection_service = InspectionService()

def init_inspection_routes(app):
    @app.route('/inspections/new/<booking_ref>', methods=['GET', 'POST'], endpoint='inspections.new_inspection')
    @admin_only
    def new_inspection(booking_ref):
        booking = booking_service.get_booking_by_ref(booking_ref)
        if not booking:
            flash('Booking reference not found.', 'danger')
            return redirect(url_for('admin_panel.dashboard'))

        if request.method == 'POST':
            damage_found = request.form.get('damage_found') == 'yes'
            est_cost = float(request.form.get('estimated_repair_cost', 0.00))
            data = {
                'property_condition': request.form.get('property_condition', 'excellent'),
                'furniture_status': request.form.get('furniture_status', 'good'),
                'electronics_status': request.form.get('electronics_status', 'good'),
                'kitchen_status': request.form.get('kitchen_status', 'good'),
                'bathroom_status': request.form.get('bathroom_status', 'good'),
                'keys_status': request.form.get('keys_status', 'returned'),
                'remotes_status': request.form.get('remotes_status', 'returned'),
                'damage_found': damage_found,
                'damage_description': request.form.get('damage_description', '').strip(),
                'estimated_repair_cost': est_cost,
                'recommendation': request.form.get('recommendation', 'full_refund' if not damage_found else 'partial_refund')
            }

            inspection, msg = inspection_service.create_inspection(booking.booking_id, current_user.user_id, data)
            if inspection:
                flash(msg, 'success')
            else:
                flash(msg, 'danger')
            return redirect(url_for('admin_panel.dashboard'))

        return render_template('admin_panel/inspection_form.html', booking=booking)
