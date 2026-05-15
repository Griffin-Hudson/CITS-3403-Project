import logging
import sqlite3
from flask import Flask, jsonify, make_response, render_template, request
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

    def _is_api(req):
        return req.path.startswith('/api/')

    def _render_error(code, title, message):
        return render_template('errors/generic.html',
                               status_code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(e):
        if _is_api(request):
            return jsonify({'error': 'Bad request'}), 400
        return _render_error(400, 'Bad Request',
                             'The request could not be understood. Please check the form and try again.')

    @app.errorhandler(401)
    def unauthorized(e):
        if _is_api(request):
            return jsonify({'error': 'Authentication required'}), 401
        return _render_error(401, 'Sign In Required',
                             'You need to be signed in to view this page.')

    @app.errorhandler(403)
    def forbidden(e):
        if _is_api(request):
            return jsonify({'error': 'Forbidden'}), 403
        return _render_error(403, 'Forbidden',
                             'You do not have permission to access this page.')

    @app.errorhandler(404)
    def not_found(e):
        if _is_api(request):
            return jsonify({'error': 'Not found'}), 404
        return render_template('errors/404.html'), 404

    @app.errorhandler(409)
    def conflict(e):
        if _is_api(request):
            return jsonify({'error': 'Conflict'}), 409
        return _render_error(409, 'Conflict',
                             'That action conflicts with the current state. Please refresh and try again.')

    @app.errorhandler(405)
    def method_not_allowed(e):
        # RFC 7231 §6.5.5: 405 MUST include Allow listing the permitted methods
        allow_header = None
        if hasattr(e, 'valid_methods') and e.valid_methods:
            allow_header = ', '.join(sorted(e.valid_methods))
        if _is_api(request):
            resp = jsonify({'error': 'Method not allowed'})
            if allow_header:
                resp.headers['Allow'] = allow_header
            return resp, 405
        resp = make_response(
            render_template(
                'errors/generic.html',
                status_code=405,
                title='Method Not Allowed',
                message='That action is not allowed on this page.',
            ),
            405,
        )
        if allow_header:
            resp.headers['Allow'] = allow_header
        return resp

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        if _is_api(request):
            return jsonify({'error': 'Too many requests. Slow down and retry.'}), 429
        return _render_error(429, 'Too Many Requests',
                             'Slow down and try again in a moment.')

    @app.errorhandler(500)
    def server_error(e):
        if _is_api(request):
            return jsonify({'error': 'Internal server error'}), 500
        return render_template('errors/500.html'), 500

    return app
