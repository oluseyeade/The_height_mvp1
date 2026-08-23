import os
import click
from dotenv import load_dotenv
from flask import Flask

BASE_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
load_dotenv(os.path.join(BASE_DIR, '.env'))

from pkg.config import config_by_name
from pkg.extensions import db, migrate, login_manager, csrf, mail
import pkg.models
from pkg.models.user import User

def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register package-based routes
    from pkg.routes import register_routes
    register_routes(app)

    with app.app_context():
        db.create_all()

    # Register error handlers
    from pkg.errors.handlers import register_error_handlers
    register_error_handlers(app)

    # Register CLI commands
    register_cli_commands(app)

    return app


def register_cli_commands(app):
    @app.cli.command("seed-db")
    def seed_db():
        """Seed initial database roles and SuperAdmin user."""
        from pkg.seeds.seed_roles import seed_roles_and_superadmin
        seed_roles_and_superadmin()
        click.echo("Database seeding completed successfully.")

    @app.cli.command("seed-apartments")
    def seed_apartments():
        """Seed default categories, facilities, and sample apartments."""
        from pkg.seeds.seed_apartments import seed_default_apartments
        seed_default_apartments()
        click.echo("Apartment data seeding completed successfully.")
