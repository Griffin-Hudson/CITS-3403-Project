import logging
import sqlite3
from flask import Flask, render_template, request
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine
from app.config import Config, validate_secret_key

# Defined at module level so other modules can import them without triggering circular imports
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])
migrate = Migrate()


@event.listens_for(Engine, 'connect')
def _enforce_sqlite_fk(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys = ON')
        cursor.close()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    validate_secret_key(app)

    if not app.debug:
        logging.basicConfig(
            level=logging.WARNING,
            format='%(asctime)s %(levelname)s %(name)s: %(message)s',
        )

    # Import db here (not at module level) to avoid circular import:
    # models.py imports nothing from app/, so keeping db there breaks the cycle
    from app.models import db
    db.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'main.login'       # redirect target when @login_required fails
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'warning'

    csrf.init_app(app)
    limiter.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        # Called on every request to reload the user object from the session cookie
        from app.models import User
        return db.session.get(User, int(user_id))

    @app.template_filter('format_num')
    def format_num(n):
        # Jinja2 filter: renders large integers as 1.2K / 3.4M for display
        n = int(n or 0)
        if n >= 1_000_000:
            return f'{n / 1_000_000:.1f}M'
        if n >= 1_000:
            return f'{n / 1_000:.1f}K'
        return str(n)

    from app.routes import main
    app.register_blueprint(main)

    from app.api.routes import api
    app.register_blueprint(api, url_prefix='/api')  # all API routes live under /api/

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        if request.is_secure:
            response.headers.setdefault('Strict-Transport-Security', 'max-age=31536000; includeSubDomains')
        return response

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    return app
