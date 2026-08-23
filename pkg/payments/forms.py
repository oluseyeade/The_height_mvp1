from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, DecimalField, SubmitField
from wtforms.validators import DataRequired, NumberRange

class PaymentProofForm(FlaskForm):
    amount = DecimalField('Amount Paid (₦)', validators=[
        DataRequired(message="Payment amount is required."),
        NumberRange(min=100, message="Amount must be at least ₦100.")
    ])
    transaction_ref = StringField('Transaction Reference / Teller Number')
    payment_proof = FileField('Upload Receipt / Transfer Screenshot', validators=[
        FileAllowed(['jpg', 'jpeg', 'png', 'webp', 'pdf'], 'Permitted formats: JPG, PNG, WEBP, PDF')
    ])
    submit = SubmitField('Upload Payment Proof')
