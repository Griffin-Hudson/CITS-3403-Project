import logging
import os
from secrets import token_hex
from urllib.parse import quote, urlencode, urlsplit
from werkzeug.utils import secure_filename

import requests as http_requests

logger = logging.getLogger(__name__)

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy.exc import IntegrityError
from app import limiter
from app.forms import SignupForm, LoginForm, UploadBeatForm, EditProfileForm, TopUpForm, MIN_TOPUP, MAX_TOPUP
from app.models import db, User, Beat, Like, Purchase, Transaction, saved_beats, follows
from app.services.feed_service import get_feed_beats
from app.services.wallet_service import (
    top_up, purchase_beat, tier_price, user_owns_tier, beat_has_exclusive_owner,
    TIER_LEASE, TIER_PREMIUM, TIER_EXCLUSIVE, TIER_LABELS, METHOD_BALANCE, METHOD_CARD,
)

main = Blueprint('main', __name__)


# Avatar generation — avataaars style only for consistent profile aesthetic
# Single background color that complements the dark theme and orange accent
AVATAR_BG_COLOR = '1a1f3a'  # Deep indigo — sophisticated, matches website aesthetic

ALLOWED_UPLOAD_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_UPLOAD_SIZE_MB = 5
MAX_UPLOAD_SIZE = MAX_UPLOAD_SIZE_MB * 1024 * 1024

ALLOWED_BEAT_AUDIO_EXTENSIONS = {'mp3', 'wav', 'm4a', 'ogg'}
ALLOWED_BEAT_COVER_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_BEAT_AUDIO_SIZE_MB = 50
MAX_BEAT_AUDIO_SIZE    = MAX_BEAT_AUDIO_SIZE_MB * 1024 * 1024
MAX_BEAT_COVER_SIZE_MB = 5
MAX_BEAT_COVER_SIZE    = MAX_BEAT_COVER_SIZE_MB * 1024 * 1024

VALID_TIERS = (TIER_LEASE, TIER_PREMIUM, TIER_EXCLUSIVE)


def _safe_redirect_target(target, request_host=''):
    """Allow only same-site redirect targets or root-relative paths."""
    if not target:
        return ''

    split = urlsplit(target)
    if split.scheme:
        if request_host and split.scheme in ('http', 'https') and split.netloc == request_host:
            return target
        return ''

    if split.netloc:
        if request_host and split.netloc == request_host:
            return target
        return ''

    if split.path and not split.path.startswith('/'):
        return ''

    return target


def _random_avataaars_avatar_url():
    """Generate a randomized avataaars avatar URL with consistent background color."""
    seed = quote(token_hex(12))
    return f'https://api.dicebear.com/9.x/avataaars/svg?seed={seed}&backgroundColor={AVATAR_BG_COLOR}'


def _allowed_file(filename):
    """Check if uploaded file has an allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS


def _upload_dir(subdir):
    root = current_app.config.get('UPLOAD_ROOT')
    if root:
        return os.path.join(root, subdir)
    return os.path.join(current_app.root_path, 'static', 'uploads', subdir)


def _save_beat_upload(file, subdir, user_id, allowed_exts, max_size):
    """Save a beat audio or cover file to static/uploads/<subdir>/; return relative path or None."""
    if not file or not file.filename:
        return None
    name = secure_filename(file.filename)
    if '.' not in name:
        return None
    ext = name.rsplit('.', 1)[1].lower()
    if ext not in allowed_exts:
        return None
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size == 0 or size > max_size:
        return None
    upload_dir = _upload_dir(subdir)
    os.makedirs(upload_dir, exist_ok=True)
    filename = f'user_{user_id}_{token_hex(8)}.{ext}'
    file.save(os.path.join(upload_dir, filename))
    return f'/static/uploads/{subdir}/{filename}'


def _save_user_upload(file, user_id):
    """Save uploaded profile picture and return the relative path.

    Returns: relative path to saved file, or None if save failed
    """
    if not file or file.filename == '':
        return None

    name = secure_filename(file.filename)
    if '.' not in name:
        return None
    ext = name.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return None

    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size == 0 or size > MAX_UPLOAD_SIZE:
        return None

    upload_dir = _upload_dir('profiles')
    os.makedirs(upload_dir, exist_ok=True)
    filename = f'user_{user_id}_{token_hex(8)}.{ext}'
    file.save(os.path.join(upload_dir, filename))
    return f'/static/uploads/profiles/{filename}'


def _beat_tier_options(beat):
    owned_tiers = set()
    if current_user.is_authenticated:
        owned_tiers = {
            row[0] for row in
            db.session.query(Purchase.licence_type)
            .filter(Purchase.buyer_id == current_user.id,
                    Purchase.beat_id == beat.id)
            .all()
        }
    exclusive_sold = beat_has_exclusive_owner(beat)
    is_own_beat = current_user.is_authenticated and beat.producer_id == current_user.id
    options = []
    for tier in VALID_TIERS:
        price = tier_price(beat, tier)
        if price is None:
            continue
        disabled_reason = ''
        if is_own_beat:
            disabled_reason = 'Your beat'
        elif tier in owned_tiers:
            disabled_reason = 'Owned'
        elif tier == TIER_EXCLUSIVE and exclusive_sold:
            disabled_reason = 'Sold'
        options.append({
            'tier': tier,
            'label': TIER_LABELS[tier],
            'price': price,
            'disabled_reason': disabled_reason,
            'checkout_url': '' if disabled_reason else url_for('main.checkout', beat_id=beat.id, tier=tier),
        })
    return options


@main.route('/')
def index():
    return redirect(url_for('main.feed'))


@main.route('/login', methods=['GET', 'POST'])
@limiter.limit('5 per 15 minutes')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            flash('Logged in successfully.', 'success')
            next_page = _safe_redirect_target(request.args.get('next', ''), request.host)
            return redirect(next_page or url_for('main.feed'))
        logger.warning('Failed login attempt for email: %s', form.email.data)
        flash('Invalid email or password.', 'danger')
    return render_template('auth/login.html', form=form)


@main.route('/register', methods=['GET', 'POST'])
@limiter.limit('5 per 15 minutes')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.feed'))
    form = SignupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'danger')
            return render_template('auth/register.html', form=form)
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'danger')
            return render_template('auth/register.html', form=form)
        user = User(
            username=username,
            email=email,
            avatar_url=_random_avataaars_avatar_url(),
        )
        user.set_password(form.password.data)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            # Race: another request claimed the same username/email between
            # the lookup above and this commit. Fall back to a friendly message.
            db.session.rollback()
            flash('Username or email already registered.', 'danger')
            return render_template('auth/register.html', form=form)
        flash('Account created. Welcome to TuneFeed!', 'success')
        return redirect(url_for('main.login'))
    if form.errors:
        # Surface server-side validation errors (password rules, username pattern, etc.)
        # so the user sees why submission was rejected when JS validation is bypassed.
        for field_name, errors in form.errors.items():
            for error in errors:
                flash(error, 'danger')
    return render_template('auth/register.html', form=form)


@main.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.login'))


@main.route('/discover')
def discover():
    # Genre filter from query string
    selected_genre = request.args.get('genre', '')

    # Trending beats (top by play count), optionally filtered by genre
    trending_q = Beat.query.filter(Beat.play_count > 0)
    if selected_genre:
        trending_q = trending_q.filter(Beat.genre.ilike(f'%{selected_genre}%'))
    trending_beats = trending_q.order_by(Beat.play_count.desc()).limit(10).all()

    # New drops — most recently uploaded
    new_beats = Beat.query.order_by(Beat.uploaded_at.desc()).limit(8).all()

    # Top producers — ordered by total play count of their beats
    producers = (User.query
                 .join(Beat, Beat.producer_id == User.id)
                 .group_by(User.id)
                 .order_by(db.func.sum(Beat.play_count).desc())
                 .limit(8).all())

    # All distinct genres for the filter pills
    genre_rows = db.session.query(Beat.genre).filter(Beat.genre.isnot(None)).distinct().all()
    genres = sorted({r[0] for r in genre_rows if r[0]})

    # Batch-load beat counts and follow states for the producers grid — avoids N+1
    producer_ids = [p.id for p in producers]
    beat_count_rows = (db.session.query(Beat.producer_id, db.func.count(Beat.id))
                       .filter(Beat.producer_id.in_(producer_ids))
                       .group_by(Beat.producer_id)
                       .all()) if producer_ids else []
    beat_counts = {pid: cnt for pid, cnt in beat_count_rows}

    is_following_map = {}
    if current_user.is_authenticated and producer_ids:
        following_ids = {row[0] for row in
            db.session.query(follows.c.followed_id)
            .filter(follows.c.follower_id == current_user.id,
                    follows.c.followed_id.in_(producer_ids))
            .all()}
        is_following_map = {pid: pid in following_ids for pid in producer_ids}

    return render_template('main/discover.html',
                           trending_beats=trending_beats,
                           new_beats=new_beats,
                           producers=producers,
                           genres=genres,
                           selected_genre=selected_genre,
                           beat_counts=beat_counts,
                           is_following_map=is_following_map)


@main.route('/feed')
def feed():
    # Service-layer ranking blends engagement, freshness, and user affinity.
    focused_beat_id = request.args.get('beat', type=int)
    focused_beat = Beat.query.get_or_404(focused_beat_id) if focused_beat_id else None
    ranked_beats = get_feed_beats(
        current_user,
        limit=14 if focused_beat else 15,
        exclude_ids=[focused_beat.id] if focused_beat else None,
    )
    beats = ([focused_beat] if focused_beat else []) + ranked_beats

    is_liked_map      = {}
    is_saved_map      = {}
    is_following_map  = {}
    owned_tiers_map   = {}
    if current_user.is_authenticated:
        beat_ids = [b.id for b in beats]
        # Batch-load liked and saved states in two queries instead of 2*N
        liked_ids = {
            row[0] for row in
            db.session.query(Like.beat_id)
            .filter(Like.user_id == current_user.id, Like.beat_id.in_(beat_ids))
            .all()
        }
        saved_ids = {
            row[0] for row in
            db.session.query(saved_beats.c.beat_id)
            .filter(saved_beats.c.user_id == current_user.id,
                    saved_beats.c.beat_id.in_(beat_ids))
            .all()
        }
        is_liked_map = {bid: bid in liked_ids for bid in beat_ids}
        is_saved_map = {bid: bid in saved_ids for bid in beat_ids}

        # which tiers the current user already owns on each beat in view —
        # the feed renders 'Owned' instead of a price button for these
        owned_rows = (db.session.query(Purchase.beat_id, Purchase.licence_type)
                      .filter(Purchase.buyer_id == current_user.id,
                              Purchase.beat_id.in_(beat_ids))
                      .all())
        for bid, lic in owned_rows:
            owned_tiers_map.setdefault(bid, set()).add(lic)

        # Batch-load follow state for unique producers on this page
        producer_ids = list({b.producer_id for b in beats if b.producer_id})
        following_ids = {
            row[0] for row in
            db.session.query(follows.c.followed_id)
            .filter(follows.c.follower_id == current_user.id,
                    follows.c.followed_id.in_(producer_ids))
            .all()
        }
        is_following_map = {pid: pid in following_ids for pid in producer_ids}

    return render_template('main/feed.html',
                           beats=beats,
                           is_liked_map=is_liked_map,
                           is_saved_map=is_saved_map,
                           is_following_map=is_following_map,
                           owned_tiers_map=owned_tiers_map)


@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadBeatForm()
    if form.validate_on_submit():
        audio_path = _save_beat_upload(
            form.audio_file.data, 'beats', current_user.id,
            ALLOWED_BEAT_AUDIO_EXTENSIONS, MAX_BEAT_AUDIO_SIZE,
        )
        if not audio_path:
            flash(f'Audio file is missing or larger than {MAX_BEAT_AUDIO_SIZE_MB} MB.', 'danger')
            return render_template('main/upload.html', form=form)
        cover_path = None
        if form.cover_file.data and form.cover_file.data.filename:
            cover_path = _save_beat_upload(
                form.cover_file.data, 'covers', current_user.id,
                ALLOWED_BEAT_COVER_EXTENSIONS, MAX_BEAT_COVER_SIZE,
            )
            if not cover_path:
                flash(f'Cover must be PNG/JPG/WebP and under {MAX_BEAT_COVER_SIZE_MB} MB.', 'danger')
                return render_template('main/upload.html', form=form)

        beat = Beat(
            title=form.title.data,
            genre=form.genre.data,
            bpm=form.bpm.data,
            key=form.key.data,
            mood_tag=form.mood_tag.data,
            licence_type=form.licence_type.data,
            price=form.price.data,
            premium_price=form.premium_price.data or None,
            exclusive_price=form.exclusive_price.data or None,
            audio_url=audio_path,
            cover_url=cover_path,
            producer_id=current_user.id,
        )
        db.session.add(beat)
        db.session.commit()
        flash('Beat uploaded successfully!', 'success')
        return redirect(url_for('main.feed'))
    return render_template('main/upload.html', form=form)


@main.route('/profile/<int:user_id>')
def profile(user_id):
    user = User.query.get_or_404(user_id)
    page = request.args.get('page', 1, type=int)
    beats = user.beats.order_by(Beat.uploaded_at.desc()).paginate(page=page, per_page=12)
    is_following = current_user.is_following(user) if current_user.is_authenticated else False

    # Aggregate stats via SQL to avoid N+1 per-beat count queries
    total_plays = (db.session.query(db.func.coalesce(db.func.sum(Beat.play_count), 0))
                   .filter(Beat.producer_id == user.id).scalar())
    total_likes = (db.session.query(db.func.count(Like.id))
                   .join(Beat, Beat.id == Like.beat_id)
                   .filter(Beat.producer_id == user.id).scalar())
    followers_count = user.followers.count()
    following_count = user.following.count()

    # Saved beats — only shown on the user's own profile page
    saved_beats_page = None
    if current_user.is_authenticated and current_user.id == user.id:
        saved_pg = request.args.get('saved_page', 1, type=int)
        saved_beats_page = current_user.saved.order_by(Beat.uploaded_at.desc()).paginate(
            page=saved_pg, per_page=12
        )

    return render_template('main/profile.html',
                           user=user,
                           beats=beats,
                           is_following=is_following,
                           total_plays=total_plays,
                           total_likes=total_likes,
                           followers_count=followers_count,
                           following_count=following_count,
                           saved_beats_page=saved_beats_page)


@main.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()

    # This endpoint multiplexes three POST actions: avatar randomize,
    # picture upload, and bio update. `action` routes to the right branch.

    # Handle randomize avatar action
    if request.method == 'POST' and request.form.get('action') == 'randomize_avatar':
        current_user.avatar_url = _random_avataaars_avatar_url()
        db.session.commit()
        flash('Avatar randomized.', 'success')
        return redirect(url_for('main.edit_profile'))

    # Handle profile picture upload
    if request.method == 'POST' and request.form.get('action') == 'upload_picture':
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename and _allowed_file(file.filename):
                saved_path = _save_user_upload(file, current_user.id)
                if saved_path:
                    current_user.avatar_url = saved_path
                    db.session.commit()
                    flash('Profile picture updated successfully!', 'success')
                    return redirect(url_for('main.edit_profile'))
                else:
                    flash(f'File must be under {MAX_UPLOAD_SIZE_MB}MB.', 'danger')
            else:
                flash('Only PNG, JPG, GIF, and WebP files are allowed.', 'danger')
        else:
            flash('No file selected.', 'danger')
        return redirect(url_for('main.edit_profile'))

    # Handle bio update
    if form.validate_on_submit():
        current_user.bio = (form.bio.data or '').strip() or None
        db.session.commit()
        flash('Profile updated.', 'success')
        return redirect(url_for('main.profile', user_id=current_user.id))

    # Populate form with current data if loading page
    if request.method == 'GET':
        form.bio.data = current_user.bio or ''

    return render_template('main/edit_profile.html', form=form)


@main.route('/beats/<int:beat_id>')
def beat_detail(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    is_liked = current_user.has_liked(beat) if current_user.is_authenticated else False
    is_following = (current_user.is_following(beat.producer)
                    if current_user.is_authenticated and beat.producer else False)
    return render_template('main/beat_detail.html',
                           beat=beat,
                           is_liked=is_liked,
                           is_following=is_following,
                           tier_options=_beat_tier_options(beat))


@main.route('/follow/<int:user_id>', methods=['POST'])
@login_required
def follow(user_id):
    user = User.query.get_or_404(user_id)
    if user == current_user:
        flash('You cannot follow yourself.', 'warning')
    elif current_user.is_following(user):
        current_user.unfollow(user)
        db.session.commit()
        flash(f'Unfollowed {user.username}.', 'info')
    else:
        current_user.follow(user)
        db.session.commit()
        flash(f'Now following {user.username}.', 'success')
    referrer = _safe_redirect_target(request.referrer or '', request.host)
    return redirect(referrer or url_for('main.feed'))


@main.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    form = TopUpForm()
    # Two-step top-up: wallet form validates the amount, then bounces the user
    # to /wallet/topup where they enter (demo) card details. Mirrors the
    # checkout payment flow so the whole site speaks one visual language.
    if form.validate_on_submit():
        amount = round(float(form.amount.data), 2)
        return redirect(url_for('main.wallet_topup', amount=f'{amount:.2f}'))

    if form.errors:
        for _field, errors in form.errors.items():
            for error in errors:
                flash(error, 'danger')

    transactions = (current_user.transactions
                    .filter(Transaction.type.in_([Transaction.TYPE_TOPUP,
                                                  Transaction.TYPE_PURCHASE,
                                                  Transaction.TYPE_REFUND]))
                    .limit(50).all())
    return render_template('main/wallet.html', form=form, transactions=transactions)


@main.route('/wallet/topup', methods=['GET', 'POST'])
@login_required
def wallet_topup():
    raw = request.values.get('amount', '').strip()
    try:
        amount = round(float(raw), 2)
    except (TypeError, ValueError):
        flash('Pick an amount on the wallet page first.', 'warning')
        return redirect(url_for('main.wallet'))

    if amount < MIN_TOPUP or amount > MAX_TOPUP:
        flash(f'Amount must be between ${MIN_TOPUP:.0f} and ${MAX_TOPUP:,.0f}.', 'danger')
        return redirect(url_for('main.wallet'))

    if request.method == 'POST':
        try:
            top_up(current_user, amount, note='Wallet top-up via card (demo)')
            db.session.commit()
        except Exception:
            logger.error('Wallet top-up failed for user %s', current_user.id, exc_info=True)
            db.session.rollback()
            flash('Top-up failed. Please try again.', 'danger')
            return redirect(url_for('main.wallet_topup', amount=f'{amount:.2f}'))
        flash(f'Added ${amount:.2f} to your balance (demo — no real charge was made).', 'success')
        return redirect(url_for('main.wallet'))

    return render_template('main/wallet_topup.html',
                           amount=amount,
                           balance=current_user.balance or 0.0)


@main.route('/checkout/<int:beat_id>', methods=['GET', 'POST'])
@login_required
def checkout(beat_id):
    beat = Beat.query.get_or_404(beat_id)
    tier = (request.values.get('tier') or '').lower()

    if tier not in VALID_TIERS:
        flash('Pick a licence tier to continue.', 'warning')
        return redirect(url_for('main.beat_detail', beat_id=beat.id))

    price = tier_price(beat, tier)
    if price is None:
        flash('That licence is not available for this beat.', 'warning')
        return redirect(url_for('main.beat_detail', beat_id=beat.id))

    if beat.producer_id == current_user.id:
        flash('You cannot buy your own beat.', 'warning')
        return redirect(url_for('main.beat_detail', beat_id=beat.id))

    if user_owns_tier(current_user, beat, tier):
        flash(f'You already own the {TIER_LABELS[tier]} licence for this beat.', 'info')
        return redirect(url_for('main.my_feeds'))

    # Exclusive licence is a one-shot, platform-wide sale
    if tier == TIER_EXCLUSIVE and beat_has_exclusive_owner(beat):
        flash('Exclusive rights for this beat have already been sold.', 'danger')
        return redirect(url_for('main.beat_detail', beat_id=beat.id))

    error = None
    selected_method = request.form.get('method', METHOD_BALANCE) if request.method == 'POST' else METHOD_BALANCE

    if request.method == 'POST':
        method = selected_method
        if method not in (METHOD_BALANCE, METHOD_CARD):
            error = 'Choose a payment method.'
        elif method == METHOD_BALANCE and (current_user.balance or 0.0) < price:
            error = (f'Insufficient balance. Top up ${price - (current_user.balance or 0.0):.2f} '
                     'more to complete this purchase.')
        else:
            try:
                purchase_beat(current_user, beat, tier, method)
                db.session.commit()
            except Exception:
                logger.error('Checkout failed for user %s beat %s', current_user.id, beat.id, exc_info=True)
                db.session.rollback()
                flash('Something went wrong. Please try again.', 'danger')
                return redirect(url_for('main.checkout', beat_id=beat.id, tier=tier))

            if method == METHOD_CARD:
                # Front-end shows a demo modal before redirect; flash backs it up
                # in case the modal was dismissed early.
                flash('Card payment processed (demo — no real charge was made).', 'info')
            flash(f'{TIER_LABELS[tier]} licence purchased for "{beat.title}".', 'success')
            return redirect(url_for('main.my_feeds'))

    return render_template('main/checkout.html',
                           beat=beat,
                           tier=tier,
                           tier_label=TIER_LABELS[tier],
                           price=price,
                           selected_method=selected_method,
                           error=error,
                           balance=current_user.balance or 0.0)


@main.route('/my-feeds')
@login_required
def my_feeds():
    page = request.args.get('page', 1, type=int)
    purchases = (Purchase.query
                 .filter_by(buyer_id=current_user.id)
                 .join(Beat, Beat.id == Purchase.beat_id)
                 .order_by(Purchase.purchased_at.desc())
                 .paginate(page=page, per_page=12))
    return render_template('main/my_feeds.html',
                           purchases=purchases,
                           tier_labels=TIER_LABELS)


@main.route('/studio/earnings')
@login_required
def studio_earnings():
    if not current_user.has_uploaded_beats:
        flash('Upload your first beat to unlock the creator studio.', 'info')
        return redirect(url_for('main.upload'))

    earning_txs = (current_user.transactions
                   .filter(Transaction.type == Transaction.TYPE_EARNING)
                   .limit(100).all())
    # Show simple aggregate stats so the page is useful even before charts/calendar land
    sale_count = len(earning_txs)
    avg_sale = (sum(t.amount for t in earning_txs) / sale_count) if sale_count else 0.0
    return render_template('main/studio_earnings.html',
                           earnings=earning_txs,
                           sale_count=sale_count,
                           avg_sale=avg_sale)


@main.route('/search')
def search():
    beats, producers = [], []
    query        = request.args.get('q', '').strip()
    search_type  = request.args.get('type', 'all')
    genre_filter = request.args.get('genre', '').strip()

    if query or genre_filter:
        if search_type in ('all', 'beats'):
            bq = Beat.query
            if query:
                bq = bq.filter(
                    Beat.title.ilike(f'%{query}%') |
                    Beat.genre.ilike(f'%{query}%') |
                    Beat.mood_tag.ilike(f'%{query}%')
                )
            if genre_filter:
                bq = bq.filter(Beat.genre.ilike(f'%{genre_filter}%'))
            beats = bq.order_by(Beat.uploaded_at.desc()).all()

        if search_type in ('all', 'producers') and query:
            producers = User.query.filter(
                User.username.ilike(f'%{query}%') |
                User.bio.ilike(f'%{query}%')
            ).all()

    # Batch-load follower counts so the template doesn't fire one query per producer
    follower_counts = {}
    if producers:
        rows = (db.session.query(follows.c.followed_id, db.func.count(follows.c.follower_id))
                .filter(follows.c.followed_id.in_([p.id for p in producers]))
                .group_by(follows.c.followed_id)
                .all())
        follower_counts = {pid: cnt for pid, cnt in rows}

    return render_template('main/search.html', beats=beats, producers=producers,
                           query=query, search_type=search_type, genre_filter=genre_filter,
                           follower_counts=follower_counts)


# ---------------------------------------------------------------------------
# Spotify OAuth — Authorization Code Flow
# Docs: https://developer.spotify.com/documentation/web-api/tutorials/code-flow
# ---------------------------------------------------------------------------

_SPOTIFY_AUTH_URL  = 'https://accounts.spotify.com/authorize'
_SPOTIFY_TOKEN_URL = 'https://accounts.spotify.com/api/token'
_SPOTIFY_ME_URL    = 'https://api.spotify.com/v1/me'

# Required scopes — user-read-private gives us display name and profile URL
_SPOTIFY_SCOPE = 'user-read-private'


@main.route('/spotify/connect')
@login_required
def spotify_connect():
    """Redirect the logged-in user to Spotify's authorization page.

    A random `state` value is stored in the session to guard the callback
    against CSRF attacks (mirrors Spotify's own recommended flow).
    """
    client_id    = current_app.config.get('SPOTIFY_CLIENT_ID', '')
    redirect_uri = current_app.config.get('SPOTIFY_REDIRECT_URI', '')

    if not client_id:
        flash('Spotify integration is not configured. Contact the administrator.', 'warning')
        return redirect(url_for('main.edit_profile'))

    state = token_hex(16)
    session['spotify_oauth_state'] = state

    params = urlencode({
        'client_id':     client_id,
        'response_type': 'code',
        'redirect_uri':  redirect_uri,
        'scope':         _SPOTIFY_SCOPE,
        'state':         state,
    })
    return redirect(f'{_SPOTIFY_AUTH_URL}?{params}')


@main.route('/spotify/callback')
@login_required
def spotify_callback():
    """Handle Spotify's redirect after user authorization.

    Verifies the `state` parameter, exchanges the authorization code for an
    access token, fetches the user's Spotify profile, and saves the relevant
    fields to the TuneFeed user record. Tokens are never forwarded to the
    client — they are used server-side only for this single profile fetch.
    """
    error = request.args.get('error')
    if error:
        flash(f'Spotify authorization denied: {error}.', 'warning')
        return redirect(url_for('main.edit_profile'))

    code  = request.args.get('code', '')
    state = request.args.get('state', '')

    # Reject the callback if state does not match what we stored — prevents CSRF.
    # Use get (not pop) so a transient failure in the steps below still lets the
    # user retry the callback without restarting from /spotify/connect.
    expected_state = session.get('spotify_oauth_state')
    if not expected_state or state != expected_state:
        session.pop('spotify_oauth_state', None)
        logger.warning('Spotify callback state mismatch for user %s', current_user.id)
        flash('Spotify connection failed: invalid state. Please try again.', 'danger')
        return redirect(url_for('main.edit_profile'))

    client_id     = current_app.config.get('SPOTIFY_CLIENT_ID', '')
    client_secret = current_app.config.get('SPOTIFY_CLIENT_SECRET', '')
    redirect_uri  = current_app.config.get('SPOTIFY_REDIRECT_URI', '')

    # Exchange authorization code for access token
    try:
        token_resp = http_requests.post(
            _SPOTIFY_TOKEN_URL,
            data={
                'grant_type':   'authorization_code',
                'code':         code,
                'redirect_uri': redirect_uri,
            },
            auth=(client_id, client_secret),
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data   = token_resp.json()
        access_token = token_data['access_token']
    except Exception:
        logger.error('Spotify token exchange failed for user %s', current_user.id, exc_info=True)
        flash('Could not connect to Spotify. Please try again.', 'danger')
        return redirect(url_for('main.edit_profile'))

    # Fetch the user's Spotify profile using the short-lived access token
    try:
        me_resp = http_requests.get(
            _SPOTIFY_ME_URL,
            headers={'Authorization': f'Bearer {access_token}'},
            timeout=10,
        )
        me_resp.raise_for_status()
        profile = me_resp.json()
    except Exception:
        logger.error('Spotify /me fetch failed for user %s', current_user.id, exc_info=True)
        flash('Could not retrieve your Spotify profile. Please try again.', 'danger')
        return redirect(url_for('main.edit_profile'))

    # Persist only the identity fields — no tokens are stored
    current_user.spotify_id           = profile.get('id')
    current_user.spotify_display_name = profile.get('display_name') or profile.get('id')
    current_user.spotify_url          = (profile.get('external_urls') or {}).get('spotify') or ''

    # Artist URL is not returned by /me — profiles with an artist page have it
    # populated via the seeder or a future Spotify for Artists API integration.

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        logger.warning('Spotify id %s already linked to another user', profile.get('id'))
        flash('This Spotify account is already linked to another TuneFeed user.', 'danger')
        return redirect(url_for('main.edit_profile'))
    except Exception:
        db.session.rollback()
        logger.error('DB save failed after Spotify connect for user %s', current_user.id, exc_info=True)
        flash('Could not save your Spotify connection. Please try again.', 'danger')
        return redirect(url_for('main.edit_profile'))

    # Flow succeeded — drop the state value so it cannot be replayed
    session.pop('spotify_oauth_state', None)
    flash('Spotify account connected successfully!', 'success')
    return redirect(url_for('main.edit_profile'))


@main.route('/spotify/disconnect', methods=['POST'])
@login_required
def spotify_disconnect():
    """Remove the Spotify connection from the current user's account."""
    current_user.spotify_id           = None
    current_user.spotify_display_name = None
    current_user.spotify_url          = None
    current_user.spotify_artist_url   = None
    db.session.commit()
    flash('Spotify account disconnected.', 'info')
    return redirect(url_for('main.edit_profile'))
