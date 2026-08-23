from flask_wtf import FlaskForm
from wtforms import StringField, DateField, IntegerField, TextAreaField, DecimalField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, NumberRange, Optional

class CorporateEnquiryForm(FlaskForm):
    company_name = StringField('Company / Organization Name', validators=[
        DataRequired(message="Company name is required.")
    ])
    contact_person = StringField('Contact Person', validators=[
        DataRequired(message="Contact person is required.")
    ])
    email = StringField('Corporate Email Address', validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid corporate email address.")
    ])
    phone = StringField('Direct Phone Number', validators=[
        DataRequired(message="Phone number is required.")
    ])
    check_in = DateField('Proposed Check-in Date', validators=[DataRequired()])
    check_out = DateField('Proposed Check-out Date', validators=[DataRequired()])
    guest_count = IntegerField('Estimated Guest Count', default=1, validators=[NumberRange(min=1)])
    suite_count = IntegerField('Number of Suites Required', default=1, validators=[NumberRange(min=1)])
    budget_range = SelectField('Estimated Budget Range', choices=[
        ('₦500k - ₦1M', '₦500,000 - ₦1,000,000'),
        ('₦1M - ₦5M', '₦1,000,000 - ₦5,000,000'),
        ('₦5M - ₦10M', '₦5,000,000 - ₦10,000,000'),
        ('₦10M+', '₦10,000,000+')
    ], validators=[Optional()])
    special_requests = TextAreaField('Bespoke Requirements / Special Requests', validators=[Optional()])
    submit = SubmitField('Request Corporate Quote')


class QuoteGeneratorForm(FlaskForm):
    room_type = StringField('Suite Type / Category Description', validators=[DataRequired()])
    amount = DecimalField('Base Amount (₦)', validators=[DataRequired(), NumberRange(min=0)])
    discount = DecimalField('Corporate Discount (₦)', default=0.0, validators=[NumberRange(min=0)])
    valid_until = DateField('Quote Valid Until Date', validators=[DataRequired()])
    terms = TextAreaField('B2B Terms & Conditions', validators=[Optional()])
    submit = SubmitField('Generate Official B2B Quote')
