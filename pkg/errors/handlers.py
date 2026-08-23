from flask import render_template

def register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html', title='Access Forbidden - The Height Apartment'), 403

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html', title='Page Not Found - The Height Apartment'), 404

    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html', title='Server Error - The Height Apartment'), 500
