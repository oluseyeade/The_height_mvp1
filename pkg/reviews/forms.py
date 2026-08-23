from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired, Length

class ReviewForm(FlaskForm):
    rating = SelectField('Rating Score', choices=[
        (5, '★★★★★ (5/5) Excellent'),
        (4, '★★★★☆ (4/5) Very Good'),
        (3, '★★★☆☆ (3/5) Good'),
        (2, '★★☆☆☆ (2/5) Fair'),
        (1, '★☆☆☆☆ (1/5) Poor')
    ], coerce=int, validators=[DataRequired()])
    title = StringField('Review Headline', validators=[
        DataRequired(message="Review headline is required."),
        Length(min=3, max=150)
    ])
    comment = TextAreaField('Detailed Review & Feedback', validators=[
        DataRequired(message="Please share details about your stay experience."),
        Length(min=10)
    ])
    submit = SubmitField('Submit Verified Review')
