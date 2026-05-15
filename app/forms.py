"""WTForms definitions for auth, profile, search, and beat upload flows."""

import re
from urllib.parse import urlparse

from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import BooleanField, FloatField, IntegerField, StringField, PasswordField, SubmitField, SelectField, TextAreaField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange, Optional, Regexp, ValidationError

AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'ogg'}
COVER_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


# Mainstream password rules: 8–128 chars, mixed case, digit, special char.
PASSWORD_SPECIAL_CHARS = r"!@#$%^&*()\-_=+\[\]{};:'\",.<>/?\\|`~"
_PASSWORD_SPECIAL_RE = re.compile(f'[{PASSWORD_SPECIAL_CHARS}]')


def _safe_url(form, field):
    """Allow local paths and http(s) URLs; reject script-like or bare-domain inputs."""
    value = (field.data or '').strip()
    if not value:
        return

    parsed = urlparse(value)
    if value.startswith('/') and not value.startswith('//') and not parsed.scheme and not parsed.netloc:
        return

    if parsed.scheme in {'http', 'https'} and parsed.netloc:
        return

    raise ValidationError('Enter a safe URL or local path.')


class SignupForm(FlaskForm):
    """Registration form for new accounts."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=32, message='Username must be 3–32 characters.'),
        Regexp(
            r'^[A-Za-z][A-Za-z0-9_.]*$',
            message='Username must start with a letter and contain only letters, digits, underscores, or dots.',
        ),
    ])
    email    = StringField('Email',    validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, max=128, message='Password must be 8–128 characters.'),
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(), EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Create Account')

    def validate_password(self, field):
        pw = field.data or ''
        if not re.search(r'[A-Z]', pw):
            raise ValidationError('Password must contain at least one uppercase letter.')
        if not re.search(r'[a-z]', pw):
            raise ValidationError('Password must contain at least one lowercase letter.')
        if not re.search(r'\d', pw):
            raise ValidationError('Password must contain at least one number.')
        if not _PASSWORD_SPECIAL_RE.search(pw):
            raise ValidationError('Password must contain at least one special character (e.g. !@#$%).')
        if re.search(r'\s', pw):
            raise ValidationError('Password must not contain spaces.')


class LoginForm(FlaskForm):
    """Email/password sign-in form."""
    email    = StringField('Email',    validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit   = SubmitField('Log In')


class UploadBeatForm(FlaskForm):
    """Producer beat upload form including optional multi-tier pricing."""
    title        = StringField('Title',       validators=[DataRequired(), Length(max=128)])
    genre        = StringField('Genre',       validators=[Optional(), Length(max=64)])
    bpm          = IntegerField('BPM',        validators=[Optional(), NumberRange(min=1, max=300)])
    key          = StringField('Key',         validators=[Optional(), Length(max=16)])
    mood_tag     = StringField('Mood Tag',    validators=[Optional(), Length(max=128)])
    licence_type = SelectField('Licence Type',
        choices=[('Non-exclusive', 'Non-exclusive'), ('Premium Lease', 'Premium Lease'), ('Exclusive', 'Exclusive')]
    )
    price           = FloatField('Basic Lease Price',     validators=[DataRequired(), NumberRange(min=0)])
    premium_price   = FloatField('Premium License Price', validators=[Optional(), NumberRange(min=0)])
    exclusive_price = FloatField('Exclusive Rights Price', validators=[Optional(), NumberRange(min=0)])
    # one currency applies to all three tiers
    currency = SelectField('Currency',
        choices=[('AUD', 'AUD'), ('USD', 'USD'), ('EUR', 'EUR'), ('GBP', 'GBP')],
        default='AUD',
    )
    audio_file = FileField('Audio File', validators=[
        DataRequired(message='An audio file is required.'),
        FileAllowed(AUDIO_EXTENSIONS, 'MP3, WAV, M4A, or OGG only.'),
    ])
    cover_file = FileField('Cover Image', validators=[
        Optional(),
        FileAllowed(COVER_EXTENSIONS, 'PNG, JPG, or WebP only.'),
    ])
    submit = SubmitField('Upload Beat')


class EditProfileForm(FlaskForm):
    """Profile edit form (bio text only)."""
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=300)])
    submit = SubmitField('Save Bio')


MIN_TOPUP = 1.0
MAX_TOPUP = 10_000.0


class TopUpForm(FlaskForm):
    """Wallet top-up form."""
    amount = FloatField('Amount', validators=[
        DataRequired(),
        NumberRange(min=MIN_TOPUP, max=MAX_TOPUP, message=f'Amount must be between ${MIN_TOPUP:.0f} and ${MAX_TOPUP:,.0f}.'),
    ])
    submit = SubmitField('Top Up')
