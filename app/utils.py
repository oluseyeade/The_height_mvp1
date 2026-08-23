import os
import uuid
from datetime import datetime, date, timedelta
import qrcode
from flask import current_app, session, has_request_context

def generate_agent_qrcode(agent_code, referral_link):
    """
    Generates an agent referral QR code image and saves it to app/static/qrcodes/.
    """
    static_folder = current_app.static_folder or os.path.join(current_app.root_path, 'static')
    qr_dir = os.path.join(static_folder, 'qrcodes')
    os.makedirs(qr_dir, exist_ok=True)
    
    filename = f"{agent_code}.png"
    filepath = os.path.abspath(os.path.join(qr_dir, filename))
    
    if not os.path.exists(filepath):
        img = qrcode.make(referral_link)
        img.save(filepath)
    
    qr_code_url = f"/static/qrcodes/{filename}"
    return qr_code_url, filepath

def validate_referral_code(ref_code, customer_user_id=None, customer_email=None):
    """
    Central, production-safe referral code validator.
    Strictly verifies agent existence, active status, non-suspended state, and prevents self-referrals.
    Returns (agent, is_valid, validation_message).
    """
    if not ref_code or not isinstance(ref_code, str):
        return None, False, "No referral code provided."

    cleaned_code = ref_code.strip()
    if not cleaned_code:
        return None, False, "No referral code provided."

    from app.models import Agent
    agent = Agent.find_by_code(cleaned_code)

    if not agent:
        return None, False, "Invalid referral code. Code does not exist."

    if agent.status != 'active':
        return None, False, f"Referral code is inactive or suspended (Status: {agent.status})."

    if agent.user and agent.user.status != 'active':
        return None, False, "Referring agent account is inactive."

    # Self-Referral Prevention Guard
    if customer_user_id and agent.user_id == customer_user_id:
        return None, False, "Self-referrals are not permitted. You cannot use your own referral code."

    if customer_email and agent.user and agent.user.email and agent.user.email.strip().lower() == str(customer_email).strip().lower():
        return None, False, "Self-referrals are not permitted. You cannot use your own referral code."

    return agent, True, "Valid referral code."

def record_referral_history(ref_code, validated, validation_message, method='link'):
    """
    Records every referral click/scan attempt in referral_history table for analytics & fraud detection.
    """
    if not has_request_context():
        return None

    try:
        from flask import request, session
        from app.models import ReferralHistory, Agent
        from app.extensions import db

        agent = Agent.find_by_code(ref_code) if ref_code else None
        qr_used = (str(method).lower() == 'qr')

        history_record = ReferralHistory(
            booking_id=None,
            agent_id=agent.agent_id if agent else None,
            customer_id=None,
            referral_code=str(ref_code).strip()[:50] if ref_code else 'UNKNOWN',
            session_id=session.get('_id', ''),
            browser_fingerprint=request.user_agent.string[:250] if request.user_agent else '',
            ip_address=request.remote_addr,
            landing_page=request.path[:250],
            referral_source=request.referrer[:100] if request.referrer else 'direct',
            qr_used=qr_used,
            link_used=not qr_used,
            validated=validated,
            validation_message=str(validation_message)[:250]
        )
        db.session.add(history_record)
        db.session.commit()
        return history_record
    except Exception:
        db.session.rollback()
        return None

def get_booking_session():
    """
    Retrieves or initializes the server-side booking session dictionary.
    Single source of truth for persistent customer booking flow.
    """
    if not has_request_context():
        return {}

    b_session = session.get('booking_session')
    if not isinstance(b_session, dict):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        b_session = {
            'check_in': today.strftime('%Y-%m-%d'),
            'check_out': tomorrow.strftime('%Y-%m-%d'),
            'number_of_guests': 2,
            'number_of_nights': 1,
            'apartment_id': None,
            'apartment_name': '',
            'price_per_night': 0.0,
            'subtotal': 0.0,
            'discount': 0.0,
            'tax': 0.0,
            'total': 0.0,
            'referral_code': '',
            'referral_valid': False,
            'booking_token': uuid.uuid4().hex,
            'booking_ref': '',
            'guest_name': '',
            'guest_email': '',
            'guest_phone': '',
            'special_requests': ''
        }
        session['booking_session'] = b_session

    return session['booking_session']

def update_booking_session(check_in=None, check_out=None, guests=None, apartment=None, guest_info=None, manual_referral_code=None):
    """
    Updates the booking session with search criteria, apartment details, and/or guest info.
    Validates referral code on server-side before applying 3% discount.
    """
    if not has_request_context():
        return {}

    b_session = get_booking_session()

    # Update Dates & Guests if provided
    if check_in:
        b_session['check_in'] = str(check_in).strip()
    if check_out:
        b_session['check_out'] = str(check_out).strip()
    if guests:
        try:
            b_session['number_of_guests'] = max(1, int(guests))
        except (ValueError, TypeError):
            pass

    # Parse and validate duration
    try:
        cin = datetime.strptime(b_session['check_in'], '%Y-%m-%d').date()
        cout = datetime.strptime(b_session['check_out'], '%Y-%m-%d').date()
        if cin >= cout:
            cout = cin + timedelta(days=1)
            b_session['check_out'] = cout.strftime('%Y-%m-%d')
        b_session['number_of_nights'] = (cout - cin).days
    except (ValueError, TypeError):
        b_session['number_of_nights'] = 1

    # Update Apartment Details if provided
    if apartment:
        b_session['apartment_id'] = apartment.apartment_id
        b_session['apartment_name'] = apartment.title
        b_session['price_per_night'] = float(apartment.price_per_night)

    # Recalculate Totals
    price = float(b_session.get('price_per_night', 0.0))
    nights = int(b_session.get('number_of_nights', 1))
    subtotal = round(price * nights, 2)
    b_session['subtotal'] = subtotal

    # Server-Side Referral Code Validation & Discount Engine
    if manual_referral_code == "":
        session.pop('referral_code', None)
        ref_code = None
    elif manual_referral_code:
        ref_code = manual_referral_code
    else:
        ref_code = session.get('referral_code')

    from flask_login import current_user
    cust_id = current_user.user_id if (has_request_context() and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated) else None
    cust_email = b_session.get('guest_email') or (current_user.email if (has_request_context() and hasattr(current_user, 'is_authenticated') and current_user.is_authenticated) else None)

    agent, is_valid, val_msg = validate_referral_code(ref_code, customer_user_id=cust_id, customer_email=cust_email)

    if is_valid and agent:
        discount = round(subtotal * 0.03, 2)
        b_session['referral_code'] = agent.agent_code
        b_session['referral_valid'] = True
        session['referral_code'] = agent.agent_code
    else:
        discount = 0.0
        b_session['referral_code'] = ''
        b_session['referral_valid'] = False
        session.pop('referral_code', None)

    b_session['discount'] = discount
    b_session['tax'] = 0.0
    b_session['total'] = round(subtotal - discount, 2)

    # Ensure booking token exists
    if not b_session.get('booking_token'):
        b_session['booking_token'] = uuid.uuid4().hex

    # Update Guest Registration Info if provided
    if isinstance(guest_info, dict):
        if 'guest_name' in guest_info and guest_info['guest_name']:
            b_session['guest_name'] = str(guest_info['guest_name']).strip()
        if 'guest_email' in guest_info and guest_info['guest_email']:
            b_session['guest_email'] = str(guest_info['guest_email']).strip()
        if 'guest_phone' in guest_info and guest_info['guest_phone']:
            b_session['guest_phone'] = str(guest_info['guest_phone']).strip()
        if 'special_requests' in guest_info:
            b_session['special_requests'] = str(guest_info['special_requests']).strip()

    session['booking_session'] = b_session
    session.modified = True
    return b_session

def clear_booking_session():
    """
    Clears the temporary booking session and referral codes after successful payment verification.
    """
    if has_request_context():
        session.pop('booking_session', None)
        session.pop('referral_code', None)
        session.pop('referral_method', None)

def save_uploaded_file(file_obj, relative_dir="properties", filename_prefix="prop"):
    """
    Production File Storage Abstraction Layer for Local & Railway Persistent Volumes.
    Returns (relative_url, absolute_filepath).
    """
    ext = file_obj.filename.rsplit('.', 1)[-1].lower() if file_obj and file_obj.filename and '.' in file_obj.filename else 'jpg'
    safe_filename = f"{filename_prefix}_{uuid.uuid4().hex[:8]}.{ext}"

    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], relative_dir)
    os.makedirs(upload_dir, exist_ok=True)
    local_filepath = os.path.join(upload_dir, safe_filename)
    file_obj.save(local_filepath)
    rel_url = f"uploads/{relative_dir}/{safe_filename}"
    return rel_url, local_filepath
