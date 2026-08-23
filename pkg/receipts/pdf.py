import os
import qrcode
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from flask import current_app

def generate_qr_code(data_string, save_path):
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    qr = qrcode.QRCode(version=1, box_size=4, border=2)
    qr.add_data(data_string)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(save_path)
    return save_path

def create_branded_receipt_pdf(receipt_number, booking, payment, output_pdf_path):
    """
    Generates a high-end luxury branded PDF receipt for The Height Apartment.
    """
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)

    # 1. Generate QR Code
    qr_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'receipts', 'qr')
    qr_path = os.path.join(qr_dir, f"{receipt_number}.png")
    qr_verify_url = f"https://theheightapartment.com/receipts/verify/{receipt_number}"
    generate_qr_code(qr_verify_url, qr_path)

    # 2. Setup ReportLab document
    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    # Brand Colors
    GOLD = colors.HexColor('#D19828')
    DARK_BG = colors.HexColor('#0F0F11')
    LIGHT_TEXT = colors.HexColor('#1E1E24')

    # Custom Paragraph Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        textColor=GOLD,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        textColor=colors.HexColor('#6E6E82'),
        spaceAfter=15
    )

    h2_style = ParagraphStyle(
        'Heading2Custom',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        textColor=GOLD,
        spaceBefore=10,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=LIGHT_TEXT
    )

    # Header Section Table
    header_data = [
        [
            Paragraph("<b>THE HEIGHT APARTMENT</b><br/><font size=9 color='#6E6E82'>AMRS Official Payment Receipt</font>", title_style),
            Paragraph(f"<b>RECEIPT #:</b> {receipt_number}<br/><b>DATE:</b> {payment.created_at.strftime('%d %B %Y')}", body_style)
        ]
    ]
    header_table = Table(header_data, colWidths=[360, 180])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 15))

    # Divider Line
    divider = Table([['']], colWidths=[540])
    divider.setStyle(TableStyle([
        ('LINEABOVE', (0, 0), (-1, -1), 2, GOLD)
    ]))
    story.append(divider)
    story.append(Spacer(1, 15))

    # Customer & Stay Summary Table
    guest_name = booking.guest_name or (booking.user.full_name if booking.user else 'Guest')
    guest_email = booking.guest_email or (booking.user.email if booking.user else 'N/A')

    info_data = [
        [
            Paragraph("<b>RECEIVED FROM:</b>", h2_style),
            Paragraph("<b>RESERVATION SUMMARY:</b>", h2_style)
        ],
        [
            Paragraph(f"<b>Name:</b> {guest_name}<br/><b>Email:</b> {guest_email}<br/><b>Ref:</b> {booking.booking_ref}", body_style),
            Paragraph(f"<b>Suite:</b> {booking.apartment.title}<br/><b>Check-in:</b> {booking.check_in.strftime('%d %b %Y')}<br/><b>Check-out:</b> {booking.check_out.strftime('%d %b %Y')} ({booking.total_nights} nights)", body_style)
        ]
    ]
    info_table = Table(info_data, colWidths=[270, 270])
    info_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
        ('PADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(info_table)
    story.append(Spacer(1, 20))

    # Payment Items Breakdown Table
    items_data = [
        [Paragraph("<b>Description</b>", body_style), Paragraph("<b>Nights / Rate</b>", body_style), Paragraph("<b>Amount (₦)</b>", body_style)],
        [
            Paragraph(f"Shortlet Reservation: {booking.apartment.title}", body_style),
            Paragraph(f"{booking.total_nights} night(s) @ ₦{booking.price_per_night:,.2f}", body_style),
            Paragraph(f"₦{booking.total_price:,.2f}", body_style)
        ],
        [
            Paragraph("<b>Amount Paid (This Payment)</b>", body_style),
            Paragraph(f"Method: {payment.payment_method.replace('_', ' ').title()}", body_style),
            Paragraph(f"<b>₦{payment.amount:,.2f}</b>", body_style)
        ]
    ]
    items_table = Table(items_data, colWidths=[260, 160, 120])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E1E24')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E0E0E0')),
        ('PADDING', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 25))

    # Footer with QR code & Official Stamp
    qr_image = RLImage(qr_path, width=70, height=70)
    footer_data = [
        [
            qr_image,
            Paragraph("<b>Official Digital Verification</b><br/><font size=8 color='#6E6E82'>Scan QR code to verify receipt authenticity online.<br/>The Height Apartments Ltd • Victoria Island, Lagos</font>", body_style)
        ]
    ]
    footer_table = Table(footer_data, colWidths=[80, 460])
    footer_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    story.append(footer_table)

    # Build PDF
    doc.build(story)
    return output_pdf_path, f"/static/uploads/receipts/qr/{receipt_number}.png"
