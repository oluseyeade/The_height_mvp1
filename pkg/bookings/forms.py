from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, TextAreaField, SubmitField, HiddenField
from wtforms.validators import DataRequired, Email, NumberRange, Optional

class BookingRequestForm(FlaskForm):
    apartment_id = HiddenField('Apartment ID', validators=[DataRequired()])
    referral_code = HiddenField('Referral Code', validators=[Optional()])
    check_in = DateField('Check-in Date', validators=[DataRequired(message="Please select check-in date.")])
    check_out = DateField('Check-out Date', validators=[DataRequired(message="Please select check-out date.")])
    guest_count = IntegerField('Guests', default=1, validators=[NumberRange(min=1, max=10)])
    
    # Guest fields for unregistered visitors
    guest_name = StringField('Full Name', validators=[DataRequired(message="Full name is required.")])
    guest_email = StringField('Email Address', validators=[DataRequired(message="Email address is required."), Email()])
    guest_phone = StringField('Phone Number', validators=[DataRequired(message="Phone number is required.")])
    
    special_requests = TextAreaField('Special Requests (Optional)', validators=[Optional()])
    submit = SubmitField('Submit Booking Request')
