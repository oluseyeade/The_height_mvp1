from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, DecimalField, IntegerField, SelectField, SubmitField, MultipleFileField
from wtforms.validators import DataRequired, NumberRange, Length

class ApartmentForm(FlaskForm):
    title = StringField('Apartment Title', validators=[
        DataRequired(message="Title is required."),
        Length(min=3, max=150)
    ])
    category_id = SelectField('Category', coerce=int, validators=[DataRequired()])
    price_per_night = DecimalField('Price Per Night (₦)', validators=[
        DataRequired(message="Price is required."),
        NumberRange(min=1000, message="Price must be at least ₦1,000.")
    ])
    bedrooms = IntegerField('Bedrooms', default=1, validators=[NumberRange(min=1)])
    bathrooms = IntegerField('Bathrooms', default=1, validators=[NumberRange(min=1)])
    capacity = IntegerField('Max Guest Capacity', default=2, validators=[NumberRange(min=1)])
    square_feet = IntegerField('Square Feet', validators=[])
    status = SelectField('Status', choices=[
        ('available', 'Available'),
        ('booked', 'Booked'),
        ('maintenance', 'Under Maintenance'),
        ('renovation', 'Renovation')
    ], default='available')
    description = TextAreaField('Detailed Description', validators=[
        DataRequired(message="Description is required."),
        Length(min=10)
    ])
    submit = SubmitField('Save Apartment')


class MultipleImageUploadForm(FlaskForm):
    caption = StringField('Room / Area Caption (e.g. Master Bedroom, Balcony)')
    images = MultipleFileField('Upload Room Pictures', validators=[
        FileRequired(message="Please select at least one image file."),
        FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Only image files (jpg, png, webp) are permitted.')
    ])
    submit = SubmitField('Upload Images')
