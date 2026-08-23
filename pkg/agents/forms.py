from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from pkg.models.user import User

class AgentRegistrationForm(FlaskForm):
    full_name = StringField('Full Name', validators=[
        DataRequired(message="Full name is required."),
        Length(min=3, max=120)
    ])
    email = StringField('Email Address', validators=[
        DataRequired(message="Email address is required."),
        Email(message="Please enter a valid email address.")
    ])
    phone = StringField('Direct Phone Number', validators=[
        DataRequired(message="Phone number is required.")
    ])
    bank_name = StringField('Bank Name', validators=[DataRequired(message="Bank name is required for payouts.")])
    account_number = StringField('Account Number', validators=[
        DataRequired(message="Account number is required."),
        Length(min=10, max=10, message="NUBAN Account Number must be 10 digits.")
    ])
    account_holder_name = StringField('Account Holder Name', validators=[DataRequired()])
    password = PasswordField('Password', validators=[
        DataRequired(message="Password is required."),
        Length(min=8, message="Password must be at least 8 characters.")
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message="Please confirm your password."),
        EqualTo('password', message="Passwords must match.")
    ])
    submit = SubmitField('Register as Partner Agent')

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower().strip()).first():
            raise ValidationError('Email is already registered. Please login or use a different email.')
