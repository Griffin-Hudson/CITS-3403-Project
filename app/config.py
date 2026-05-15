import os
import secrets as _secrets


def _require_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    if os.environ.get('FLASK_DEBUG', 'false').lower() == 'true':
        # Ephemeral key for local dev — sessions reset on every restart, which is fine
        return _secrets.token_hex(32)
    return None


def validate_secret_key(app):
    if app.config.get('SECRET_KEY') or app.config.get('TESTING'):
        return
    raise ValueError(
        'SECRET_KEY environment variable must be set in production. '
        'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
    )


class Config:
    SECRET_KEY = _require_secret_key()

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///tunefeed.db')

    # Spotify OAuth 2.0 — Authorization Code Flow
    # Register your app at https://developer.spotify.com/dashboard
    # Set redirect URI to http://127.0.0.1:5002/spotify/callback (dev) or your production URL
    SPOTIFY_CLIENT_ID     = os.environ.get('SPOTIFY_CLIENT_ID', '')
    SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET', '')
    SPOTIFY_REDIRECT_URI  = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:5002/spotify/callback')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # leaves headroom for 50 MB audio + 5 MB cover + form overhead
    MAX_CONTENT_LENGTH = 60 * 1024 * 1024

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    # Only send the cookie over HTTPS; disabled in local dev (FLASK_DEBUG=true) where there is no TLS
    SESSION_COOKIE_SECURE = os.environ.get('FLASK_DEBUG', 'false').lower() != 'true'
