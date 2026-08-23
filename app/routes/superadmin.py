import csv
import io
from flask import render_template, request, flash, redirect, url_for, jsonify, Response
from flask_login import current_user
from app.decorators import superadmin_only
from app.services import ApartmentService
from app.models import Booking, Payment, AgentCommission, Refund, Apartment
from app.extensions import db

apt_service = ApartmentService()

def init_superadmin_routes(app):
    @app.route('/superadmin/', endpoint='superadmin_panel.dashboard')
    @app.route('/superadmin/dashboard')
    @superadmin_only
    def superadmin_dashboard_route():
        apartments = apt_service.get_all_active_apartments()

        # Compute Financial & Operational Metrics
        all_bookings = Booking.query.all()
        verified_payments = Payment.query.filter_by(status='verified').all()
        total_revenue = sum(float(p.amount) for p in verified_payments)
        caution_fee_liability = sum(float(b.caution_fee_amount or 50000.00) for b in all_bookings if b.status in ['confirmed', 'CONFIRMED', 'CHECKED_IN'])
        
        all_refunds = Refund.query.all()
        pending_refunds_cnt = len([r for r in all_refunds if r.refund_status == 'pending_approval'])
        completed_refunds_val = sum(float(r.refund_amount) for r in all_refunds if r.refund_status == 'processed')

        all_commissions = AgentCommission.query.all()
        total_agent_commissions = sum(float(c.commission_amount) for c in all_commissions)

        total_apts = len(Apartment.query.all()) or 1
        available_apts = len(Apartment.query.filter_by(status='available').all())
        occupancy_rate = round(((total_apts - available_apts) / total_apts) * 100, 1)

        metrics = {
            'total_revenue': total_revenue,
            'caution_fee_liability': caution_fee_liability,
            'pending_refunds_count': pending_refunds_cnt,
            'completed_refunds_amount': completed_refunds_val,
            'total_agent_commissions': total_agent_commissions,
            'occupancy_rate': occupancy_rate,
            'total_bookings': len(all_bookings),
            'confirmed_bookings': len([b for b in all_bookings if b.status in ['confirmed', 'CONFIRMED']])
        }

        return render_template('dashboard/superadmin_dashboard.html', apartments=apartments, metrics=metrics, refunds=all_refunds, bookings=all_bookings)

    @app.route('/superadmin/add-property', methods=['GET', 'POST'], endpoint='superadmin_panel.add_property')
    @superadmin_only
    def add_property():
        import os, uuid
        from werkzeug.utils import secure_filename
        from PIL import Image as PILImage
        from app.models import Category, Amenity, Apartment, ApartmentImage, ApartmentAmenity, Property, AuditLog
        from app.services import NotificationService

        # Mandatory Server-Side SuperAdmin Authorization Check
        if not current_user.is_authenticated or not getattr(current_user, 'is_superadmin', False):
            flash('Unauthorized access: SuperAdmin privileges required for Property Onboarding.', 'danger')
            return redirect(url_for('public.index'))

        # Seed standard amenities if empty
        standard_amenities = [
            ("Wi-Fi", "fas fa-wifi", "Connectivity"),
            ("24-Hour Power Generator", "fas fa-bolt", "Utilities"),
            ("Air Conditioning", "fas fa-snowflake", "Comfort"),
            ("Swimming Pool", "fas fa-swimmer", "Leisure"),
            ("Fitness Gym", "fas fa-dumbbell", "Leisure"),
            ("Fully Equipped Kitchen", "fas fa-utensils", "Dining"),
            ("Smart TV & Netflix", "fas fa-tv", "Entertainment"),
            ("Security & CCTV", "fas fa-shield-alt", "Safety"),
            ("Washing Machine", "fas fa-soap", "Laundry"),
            ("Dedicated Workspace", "fas fa-laptop-house", "Work"),
            ("Elevator Access", "fas fa-elevator", "Accessibility"),
            ("Private Balcony", "fas fa-store-alt", "Outdoors"),
            ("Private Parking", "fas fa-parking", "Parking"),
            ("Water Supply & Treatment", "fas fa-faucet", "Utilities")
        ]

        for a_name, a_icon, a_cat in standard_amenities:
            if not Amenity.query.filter_by(name=a_name).first():
                db.session.add(Amenity(name=a_name, icon=a_icon, category=a_cat, is_active=True))
        db.session.commit()

        categories = Category.query.filter_by(is_active=True).all()
        amenities = Amenity.query.filter_by(is_active=True).all()

        if request.method == 'POST':
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            category_id = request.form.get('category_id', type=int)
            price_per_night = request.form.get('price_per_night', type=float)
            bedrooms = request.form.get('bedrooms', 1, type=int)
            bathrooms = request.form.get('bathrooms', 1, type=int)
            capacity = request.form.get('capacity', 2, type=int)
            square_feet = request.form.get('square_feet', type=int)
            status = request.form.get('status', 'available').strip()
            is_featured = True if request.form.get('is_featured') == '1' else False
            
            # Address & Location Fields
            address = request.form.get('address', '').strip()
            neighborhood = request.form.get('neighborhood', '').strip()
            city = request.form.get('city', 'Ikeja').strip()
            state = request.form.get('state', 'Lagos State').strip()
            latitude = request.form.get('latitude', '').strip()
            longitude = request.form.get('longitude', '').strip()

            if not title or not description or not category_id or not price_per_night:
                flash("Title, description, category, and price per night are required.", "danger")
                return render_template('dashboard/add_property.html', categories=categories, amenities=amenities)

            # Combine full description with location & address details
            full_desc = f"{description}\n\n📍 Address: {address}, {neighborhood}, {city}, {state}\n🌍 Location: Lat {latitude}, Long {longitude}"

            # Step 1: Create Apartment Entity
            try:
                apartment = Apartment(
                    title=title,
                    description=full_desc,
                    category_id=category_id,
                    price_per_night=price_per_night,
                    bedrooms=bedrooms,
                    bathrooms=bathrooms,
                    capacity=capacity,
                    square_feet=square_feet,
                    status=status,
                    is_featured=is_featured,
                    created_by=current_user.user_id
                )
                db.session.add(apartment)
                db.session.flush()

                # Step 2: Associate Selected Amenities
                selected_amenity_ids = request.form.getlist('amenities')
                for am_id in selected_amenity_ids:
                    try:
                        db.session.add(ApartmentAmenity(apartment_id=apartment.apartment_id, amenity_id=int(am_id)))
                    except ValueError:
                        pass

                # Step 3: Handle Image Uploads & Validation
                uploaded_files = request.files.getlist('images')
                upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'properties')
                os.makedirs(upload_dir, exist_ok=True)
                
                cover_index = request.form.get('cover_image_index', 0, type=int)
                saved_images = []

                for idx, file in enumerate(uploaded_files):
                    if file and file.filename:
                        filename = secure_filename(file.filename)
                        ext = os.path.splitext(filename)[1].lower()
                        if ext not in ['.jpg', '.jpeg', '.png']:
                            continue
                        
                        unique_filename = f"prop_{apartment.apartment_id}_{uuid.uuid4().hex[:8]}{ext}"
                        file_path = os.path.join(upload_dir, unique_filename)
                        file.save(file_path)

                        # Backend MIME & Image integrity check via PIL
                        try:
                            with PILImage.open(file_path) as img:
                                img.verify()
                        except Exception:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                            continue

                        rel_url = f"uploads/properties/{unique_filename}"
                        is_cover = (idx == cover_index)
                        img_obj = ApartmentImage(
                            apartment_id=apartment.apartment_id,
                            uploaded_by=current_user.user_id,
                            image_url=rel_url,
                            is_cover=is_cover,
                            caption=request.form.get(f'caption_{idx}', f"{title} Photo")
                        )
                        db.session.add(img_obj)
                        saved_images.append(img_obj)

                # Ensure at least one image is marked as cover
                if saved_images and not any(i.is_cover for i in saved_images):
                    saved_images[0].is_cover = True

                # Step 4: Audit & Notifications
                audit = AuditLog(
                    user_id=current_user.user_id,
                    action='CREATE_PROPERTY',
                    activity_type='PROPERTY_ONBOARDING',
                    module='PROPERTIES',
                    ip_address=request.remote_addr,
                    description=f"Superadmin {current_user.full_name} created new property '{title}' (#{apartment.apartment_id})"
                )
                db.session.add(audit)

                db.session.commit()

                NotificationService.create_notification(
                    title=f"New Property Listed: {title}",
                    message=f"Superadmin {current_user.full_name} onboarded property '{title}' with {len(saved_images)} images.",
                    notification_type='PROPERTY',
                    related_type='PROPERTY',
                    related_id=str(apartment.apartment_id)
                )

                flash(f"Property '{title}' created successfully!", "success")
                return redirect(url_for('superadmin_panel.dashboard'))

            except Exception as e:
                db.session.rollback()
                flash(f"Failed to create property: {str(e)}", "danger")

        return render_template('dashboard/add_property.html', categories=categories, amenities=amenities)

    @app.route('/superadmin/apartments/<int:apartment_id>/availability', methods=['POST'], endpoint='superadmin_panel.update_apartment_availability')
    @superadmin_only
    def update_availability_route(apartment_id):
        # Mandatory Server-Side SuperAdmin Authorization Check
        if not current_user.is_authenticated or not getattr(current_user, 'is_superadmin', False):
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': 'Unauthorized. Only Super Admin can modify apartment availability.'}), 403
            flash('Unauthorized. Only Super Admin can modify apartment availability.', 'danger')
            return redirect(url_for('public.index'))

        apartment = apt_service.get_apartment_by_id(apartment_id)
        if not apartment:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': 'Apartment not found.'}), 404
            flash('Apartment not found.', 'danger')
            return redirect(url_for('superadmin_panel.dashboard'))

        new_status = request.form.get('status') or (request.json.get('status') if request.is_json else None)
        if new_status not in ['available', 'unavailable']:
            if request.is_json or request.headers.get('Accept') == 'application/json':
                return jsonify({'success': False, 'error': 'Invalid status. Must be "available" or "unavailable".'}), 400
            flash('Invalid status provided.', 'danger')
            return redirect(url_for('superadmin_panel.dashboard'))

        apartment.status = new_status
        db.session.commit()

        msg = f"Apartment '{apartment.title}' availability updated to '{new_status}' successfully."
        if request.is_json or request.headers.get('Accept') == 'application/json':
            return jsonify({'success': True, 'apartment_id': apartment_id, 'status': new_status, 'message': msg}), 200

        flash(msg, 'success')
        return redirect(url_for('superadmin_panel.dashboard'))

    @app.route('/admin/reports/export', endpoint='admin_panel.export_report')
    @superadmin_only
    def export_report():
        report_type = request.args.get('type', 'revenue')
        output = io.StringIO()
        writer = csv.writer(output)

        if report_type == 'revenue':
            writer.writerow(['Payment ID', 'Booking Ref', 'Amount (NGN)', 'Payment Method', 'Status', 'Date'])
            payments = Payment.query.all()
            for p in payments:
                ref = p.booking.booking_ref if p.booking else 'N/A'
                writer.writerow([p.payment_id, ref, p.amount, p.payment_method, p.status, p.created_at])
        elif report_type == 'refunds':
            writer.writerow(['Refund ID', 'Booking Ref', 'Refund Type', 'Amount (NGN)', 'Reason', 'Status', 'Date'])
            refunds = Refund.query.all()
            for r in refunds:
                ref = r.booking.booking_ref if r.booking else 'N/A'
                writer.writerow([r.refund_id, ref, r.refund_type, r.refund_amount, r.refund_reason, r.refund_status, r.created_at])
        elif report_type == 'commissions':
            writer.writerow(['Commission ID', 'Agent ID', 'Booking Ref', 'Commission Amount (NGN)', 'Status', 'Date'])
            commissions = AgentCommission.query.all()
            for c in commissions:
                ref = c.booking.booking_ref if c.booking else 'N/A'
                writer.writerow([c.commission_id, c.agent_id, ref, c.commission_amount, c.payment_status, c.created_at])
        else:
            writer.writerow(['Booking Ref', 'Guest Name', 'Check In', 'Check Out', 'Total (NGN)', 'Status'])
            bookings = Booking.query.all()
            for b in bookings:
                writer.writerow([b.booking_ref, b.guest_name, b.check_in, b.check_out, b.final_amount, b.status])

        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': f'attachment; filename={report_type}_report.csv'})

    # -------------------------------------------------------------------------
    # ENTERPRISE SUPERADMIN ADMIN MANAGEMENT MODULE
    # -------------------------------------------------------------------------
    @app.route('/superadmin/admins', methods=['GET'], endpoint='superadmin_panel.manage_admins')
    @superadmin_only
    def manage_admins_route():
        from sqlalchemy import or_
        from app.models import User, Role, Admin, AuditLog

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        status_filter = request.args.get('status', '').strip().lower()
        search_query = request.args.get('search', '').strip()

        # Query all users with Admin or SuperAdmin role
        query = User.query.join(Role).filter(Role.hierarchy_level >= 3)

        if status_filter and status_filter != 'all':
            query = query.filter(User.status == status_filter)

        if search_query:
            query = query.filter(
                or_(
                    User.full_name.ilike(f"%{search_query}%"),
                    User.email.ilike(f"%{search_query}%"),
                    User.phone.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        admins = pagination.items

        # Real-time Admin Metrics
        all_admin_users = User.query.join(Role).filter(Role.hierarchy_level >= 3).all()
        total_admins = len(all_admin_users)
        active_admins = len([u for u in all_admin_users if u.status == 'active'])
        suspended_admins = len([u for u in all_admin_users if u.status in ['suspended', 'deactivated']])
        recent_logins = len([u for u in all_admin_users if u.last_login])

        metrics = {
            'total_admins': total_admins,
            'active_admins': active_admins,
            'suspended_admins': suspended_admins,
            'recent_logins': recent_logins
        }

        roles = Role.query.filter(Role.hierarchy_level >= 3).all()

        return render_template(
            'superadmin/manage_admins.html',
            admins=admins,
            pagination=pagination,
            metrics=metrics,
            roles=roles,
            status_filter=status_filter,
            search_query=search_query
        )

    @app.route('/superadmin/admins/create', methods=['POST'], endpoint='superadmin_panel.create_admin')
    @superadmin_only
    def create_admin_route():
        from app.models import User, Role, Admin
        from app.services import UserService

        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        phone = request.form.get('phone', '').strip()
        password = request.form.get('password', '').strip()
        role_id = request.form.get('role_id', type=int)

        if not full_name or not email or not password or not role_id:
            flash('All fields are required to create an Admin account.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash(f"User with email '{email}' already exists.", 'warning')
            return redirect(url_for('superadmin_panel.manage_admins'))

        target_role = Role.query.get(role_id)
        role_name = target_role.role_name if target_role else 'Admin'

        u_service = UserService()
        new_user, err = u_service.register_user(full_name, email, phone, password, role_name)
        if err:
            flash(f"Error creating Admin: {err}", 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        if not new_user.admin_profile:
            admin_prof = Admin(user_id=new_user.user_id, can_manage_agents=True, can_manage_apartments=True, can_manage_bookings=True, can_manage_payments=True)
            db.session.add(admin_prof)
            db.session.commit()

        # Trigger SuperAdmin Notification
        from app.services import NotificationService
        NotificationService.create_notification(
            notification_type='ADMIN_ACCOUNT_CREATED',
            portal='ADMIN',
            title='New Admin Provisioned',
            message=f"New admin account '{full_name}' ({role_name}) created successfully.",
            priority='HIGH',
            requires_action=True,
            related_type='User',
            related_id=new_user.user_id,
            action_url=url_for('superadmin_panel.manage_admins')
        )

        flash(f"Admin account for '{full_name}' ({role_name}) created successfully!", 'success')
        return redirect(url_for('superadmin_panel.manage_admins'))

    @app.route('/superadmin/admins/<int:user_id>/status', methods=['POST'], endpoint='superadmin_panel.update_admin_status')
    @superadmin_only
    def update_admin_status_route(user_id):
        from app.models import User
        from app.services import NotificationService

        if user_id == current_user.user_id:
            flash('You cannot modify your own SuperAdmin status.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        target_admin = User.query.get(user_id)
        if not target_admin:
            flash('Admin account not found.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        new_status = request.form.get('status', '').strip().lower()
        if new_status not in ['active', 'suspended', 'deactivated']:
            flash('Invalid status specified.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        old_status = target_admin.status
        target_admin.status = new_status
        db.session.commit()

        NotificationService.create_notification(
            notification_type='ADMIN_STATUS_CHANGED',
            portal='ADMIN',
            title='Admin Status Updated',
            message=f"Admin '{target_admin.full_name}' account status changed from '{old_status}' to '{new_status}'.",
            priority='HIGH' if new_status == 'suspended' else 'MEDIUM',
            requires_action=(new_status == 'suspended'),
            related_type='User',
            related_id=user_id,
            action_url=url_for('superadmin_panel.manage_admins')
        )

        flash(f"Admin '{target_admin.full_name}' status updated from '{old_status}' to '{new_status}' successfully.", 'success')
        return redirect(url_for('superadmin_panel.manage_admins'))

    @app.route('/superadmin/admins/<int:user_id>/reset_password', methods=['POST'], endpoint='superadmin_panel.reset_admin_password')
    @superadmin_only
    def reset_admin_password_route(user_id):
        from app.models import User
        from app.services import NotificationService

        target_admin = User.query.get(user_id)
        if not target_admin:
            flash('Admin account not found.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        new_password = request.form.get('password', '').strip()
        if not new_password or len(new_password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return redirect(url_for('superadmin_panel.manage_admins'))

        target_admin.set_password(new_password)
        db.session.commit()

        NotificationService.create_notification(
            notification_type='ADMIN_PASSWORD_RESET',
            portal='ADMIN',
            title='Admin Password Reset',
            message=f"Password reset executed for Admin '{target_admin.full_name}'.",
            priority='MEDIUM',
            requires_action=False,
            related_type='User',
            related_id=user_id,
            action_url=url_for('superadmin_panel.manage_admins')
        )

        flash(f"Password reset for Admin '{target_admin.full_name}' successfully.", 'success')
        return redirect(url_for('superadmin_panel.manage_admins'))

    @app.route('/superadmin/admins/<int:user_id>/delete', methods=['POST'], endpoint='superadmin_panel.delete_admin')
    @superadmin_only
    def delete_admin_route(user_id):
        from app.models import User
        from app.services import NotificationService

        if user_id == current_user.user_id:
            flash('You cannot delete your own SuperAdmin account.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        target_admin = User.query.get(user_id)
        if not target_admin:
            flash('Admin account not found.', 'danger')
            return redirect(url_for('superadmin_panel.manage_admins'))

        admin_name = target_admin.full_name
        target_admin.status = 'deactivated'
        db.session.delete(target_admin)
        db.session.commit()

        NotificationService.create_notification(
            notification_type='ADMIN_ACCOUNT_DELETED',
            portal='ADMIN',
            title='Admin Account Deleted',
            message=f"Admin account '{admin_name}' was deleted permanently by SuperAdmin.",
            priority='CRITICAL',
            requires_action=True,
            related_type='User',
            related_id=user_id,
            action_url=url_for('superadmin_panel.manage_admins')
        )

        flash(f"Admin account '{admin_name}' deleted permanently by SuperAdmin.", 'warning')
        return redirect(url_for('superadmin_panel.manage_admins'))

    @app.route('/superadmin/admins/export', methods=['GET'], endpoint='superadmin_panel.export_admins')
    @superadmin_only
    def export_admins_route():
        from app.models import User, Role

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Admin ID', 'Full Name', 'Email', 'Phone', 'Role', 'Status', 'Last Login', 'Created Date'])

        admins = User.query.join(Role).filter(Role.hierarchy_level >= 3).all()
        for a in admins:
            role_name = a.role.role_name if a.role else 'Admin'
            writer.writerow([f"ADM-{a.user_id}", a.full_name, a.email, a.phone or 'N/A', role_name, a.status, a.last_login or 'Never', a.created_at])

        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=admin_users_report.csv'})

    # -------------------------------------------------------------------------
    # ENTERPRISE SUPERADMIN NOTIFICATION CENTER
    # -------------------------------------------------------------------------
    @app.route('/superadmin/notifications', methods=['GET'], endpoint='superadmin_panel.view_notifications')
    @superadmin_only
    def view_notifications_route():
        from sqlalchemy import or_
        from app.models import Notification
        from app.services import NotificationService

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 12, type=int)
        portal_filter = request.args.get('portal', '').strip().upper()
        priority_filter = request.args.get('priority', '').strip().upper()
        status_filter = request.args.get('status', '').strip().upper()
        search_query = request.args.get('search', '').strip()

        query = Notification.query

        if portal_filter and portal_filter != 'ALL':
            query = query.filter(Notification.portal == portal_filter)

        if priority_filter and priority_filter != 'ALL':
            query = query.filter(Notification.priority == priority_filter)

        if status_filter and status_filter != 'ALL':
            query = query.filter(Notification.status == status_filter)

        if search_query:
            query = query.filter(
                or_(
                    Notification.title.ilike(f"%{search_query}%"),
                    Notification.message.ilike(f"%{search_query}%"),
                    Notification.notification_type.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(Notification.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        notifications = pagination.items

        all_notifs = Notification.query.all()
        metrics = {
            'total_notifications': len(all_notifs),
            'unread_count': len([n for n in all_notifs if not n.is_read]),
            'action_required_count': len([n for n in all_notifs if n.requires_action and n.status != 'RESOLVED']),
            'critical_count': len([n for n in all_notifs if n.priority == 'CRITICAL'])
        }

        return render_template(
            'superadmin/notifications.html',
            notifications=notifications,
            pagination=pagination,
            metrics=metrics,
            portal_filter=portal_filter,
            priority_filter=priority_filter,
            status_filter=status_filter,
            search_query=search_query
        )

    @app.route('/superadmin/notifications/<int:notification_id>/read', methods=['POST', 'GET'], endpoint='superadmin_panel.mark_notification_read')
    @superadmin_only
    def mark_notification_read_route(notification_id):
        from app.services import NotificationService
        from app.models import Notification

        notif = Notification.query.get(notification_id)
        success, msg = NotificationService.mark_as_read(notification_id)
        
        if request.args.get('redirect_to_action') and notif and notif.action_url:
            return redirect(notif.action_url)

        flash(msg, 'success' if success else 'warning')
        return redirect(url_for('superadmin_panel.view_notifications'))

    @app.route('/superadmin/notifications/<int:notification_id>/unread', methods=['POST'], endpoint='superadmin_panel.mark_notification_unread')
    @superadmin_only
    def mark_notification_unread_route(notification_id):
        from app.services import NotificationService
        success, msg = NotificationService.mark_as_unread(notification_id)
        flash(msg, 'success' if success else 'warning')
        return redirect(url_for('superadmin_panel.view_notifications'))

    @app.route('/superadmin/notifications/<int:notification_id>/resolve', methods=['POST'], endpoint='superadmin_panel.resolve_notification')
    @superadmin_only
    def resolve_notification_route(notification_id):
        from app.services import NotificationService
        success, msg = NotificationService.resolve_notification(notification_id)
        flash(msg, 'success' if success else 'warning')
        return redirect(url_for('superadmin_panel.view_notifications'))

    # -------------------------------------------------------------------------
    # ENTERPRISE SUPERADMIN AUDIT LOGS PORTAL
    # -------------------------------------------------------------------------
    @app.route('/superadmin/audit_logs', methods=['GET'], endpoint='superadmin_panel.view_audit_logs')
    @superadmin_only
    def view_audit_logs_route():
        from sqlalchemy import or_
        from app.models import AuditLog, User

        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 15, type=int)
        module_filter = request.args.get('module', '').strip()
        search_query = request.args.get('search', '').strip()

        query = AuditLog.query

        if module_filter:
            query = query.filter(AuditLog.module.ilike(module_filter))

        if search_query:
            query = query.filter(
                or_(
                    AuditLog.activity_type.ilike(f"%{search_query}%"),
                    AuditLog.description.ilike(f"%{search_query}%"),
                    AuditLog.action.ilike(f"%{search_query}%")
                )
            )

        pagination = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        logs = pagination.items

        metrics = {
            'total_logs': AuditLog.query.count(),
            'booking_logs': AuditLog.query.filter_by(module='BOOKINGS').count(),
            'review_logs': AuditLog.query.filter_by(module='REVIEWS').count(),
            'security_logs': AuditLog.query.filter(AuditLog.module.in_(['SECURITY', 'AUTH'])).count()
        }

        return render_template(
            'superadmin/audit_logs.html',
            logs=logs,
            pagination=pagination,
            metrics=metrics,
            module_filter=module_filter,
            search_query=search_query
        )

    @app.route('/superadmin/audit_logs/export', methods=['GET'], endpoint='superadmin_panel.export_audit_logs')
    @superadmin_only
    def export_audit_logs_route():
        from app.models import AuditLog

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Log ID', 'Performer ID', 'Activity Type', 'Module', 'Action', 'Description', 'IP Address', 'Timestamp'])

        logs = AuditLog.query.order_by(AuditLog.created_at.desc()).all()
        for l in logs:
            writer.writerow([l.log_id, l.user_id or 'System', l.activity_type, l.module, l.action, l.description, l.ip_address or '127.0.0.1', l.created_at])

        output.seek(0)
        return Response(output.getvalue(), mimetype='text/csv', headers={'Content-Disposition': 'attachment; filename=system_audit_logs.csv'})
