import csv
from io import StringIO
from pkg.models.booking import Booking
from pkg.models.payment import Payment

class ReportService:
    @staticmethod
    def generate_bookings_csv():
        """
        Generates CSV report of all bookings.
        """
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Booking Ref', 'Guest Name', 'Email', 'Suite Title', 'Check In', 'Check Out', 'Nights', 'Total Amount (NGN)', 'Status', 'Created At'])

        bookings = Booking.query.order_by(Booking.created_at.desc()).all()
        for b in bookings:
            guest_name = b.guest_name or (b.user.full_name if b.user else 'Guest')
            guest_email = b.guest_email or (b.user.email if b.user else 'N/A')
            writer.writerow([
                b.booking_ref,
                guest_name,
                guest_email,
                b.apartment.title if b.apartment else 'N/A',
                b.check_in.strftime('%Y-%m-%d'),
                b.check_out.strftime('%Y-%m-%d'),
                b.total_nights,
                f"{b.final_amount:.2f}",
                b.status,
                b.created_at.strftime('%Y-%m-%d %H:%M:%S')
            ])

        return output.getvalue()
