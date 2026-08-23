from flask import render_template, request, flash, redirect, url_for
from app.services import ApartmentService
from app.utils import update_booking_session, get_booking_session

apt_service = ApartmentService()

def init_apartment_routes(app):
    @app.route('/apartments/', endpoint='apartments.list_apartments')
    def list_apartments():
        check_in = request.args.get('check_in')
        check_out = request.args.get('check_out')
        guests = request.args.get('guests')

        # Update booking session if search widget parameters submitted
        if check_in or check_out or guests:
            update_booking_session(check_in=check_in, check_out=check_out, guests=guests)
        else:
            get_booking_session()

        showcase = apt_service.get_category_showcase(check_in_date=check_in, check_out_date=check_out)
        return render_template('apartments/list.html', showcase=showcase)

    @app.route('/apartments/<int:apartment_id>', endpoint='apartments.detail')
    def detail(apartment_id):
        apartment = apt_service.get_apartment_by_id(apartment_id)
        if not apartment:
            flash('Apartment not found.', 'danger')
            return redirect(url_for('apartments.list_apartments'))

        # Check for query overrides
        check_in = request.args.get('check_in')
        check_out = request.args.get('check_out')
        guests = request.args.get('guests')

        update_booking_session(check_in=check_in, check_out=check_out, guests=guests, apartment=apartment)
        avail_count, free_units = apt_service.get_category_availability(apartment.category_id, check_in, check_out)

        return render_template('apartments/detail.html', apartment=apartment, available_units_count=avail_count)
