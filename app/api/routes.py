"""
TuneFeed — AJAX API
All endpoints return JSON. Used by the feed and other interactive elements.
"""

import random
from datetime import datetime, timedelta
from uuid import uuid4

from flask import Blueprint, jsonify, request, session
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from app import limiter
from app.models import (db, Beat, User, Comment, BeatPlayEvent, CommentReport,
                        Like, Purchase, saved_beats, follows, comment_likes, comment_dislikes)
from app.services.feed_service import get_feed_beats

SEARCH_MAX_RESULTS = 50

api = Blueprint('api', __name__)

# Minimum seconds between play events from the same actor.
# Prevents double-click inflation while still allowing real replays.
PLAY_DEDUPE_SECONDS = 8
MAX_COMMENT_LENGTH  = 500


# ---------------------------------------------------------------------------
# Feed endpoint (AJAX infinite scroll)
# ---------------------------------------------------------------------------

@api.route('/feed')
def feed():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    # Client sends comma-separated IDs it has already rendered; algorithm excludes them
    exclude_raw = request.args.get('seen', '')
    exclude_ids = [int(x) for x in exclude_raw.split(',') if x.strip().isdigit()]

    # `seen` already excludes every previously rendered beat, so the ranked result
    # is always a fresh set — slice from 0, not from a page offset.
    # Fetch one extra to determine has_next without a separate COUNT query.
    beats = get_feed_beats(current_user, limit=per_page + 1, exclude_ids=exclude_ids)
    page_beats = beats[:per_page]

    # Batch-load interaction states in a handful of queries instead of N per beat
    liked_ids = set()
    saved_ids = set()
    following_ids = set()
    owned_tiers = {}
    if current_user.is_authenticated and page_beats:
        beat_ids = [b.id for b in page_beats]
        producer_ids = list({b.producer_id for b in page_beats if b.producer_id})
        liked_ids = {row[0] for row in
            db.session.query(Like.beat_id)
            .filter(Like.user_id == current_user.id, Like.beat_id.in_(beat_ids))
            .all()}
        saved_ids = {row[0] for row in
            db.session.query(saved_beats.c.beat_id)
            .filter(saved_beats.c.user_id == current_user.id, saved_beats.c.beat_id.in_(beat_ids))
            .all()}
        following_ids = {row[0] for row in
            db.session.query(follows.c.followed_id)
            .filter(follows.c.follower_id == current_user.id, follows.c.followed_id.in_(producer_ids))
            .all()}
        owned_rows = (db.session.query(Purchase.beat_id, Purchase.licence_type)
                      .filter(Purchase.buyer_id == current_user.id,
                              Purchase.beat_id.in_(beat_ids))
                      .all())
        for bid, lic in owned_rows:
            owned_tiers.setdefault(bid, set()).add(lic)

    result = []
    for b in page_beats:
        producer = b.producer
        result.append({
            'id':                  b.id,
            'title':               b.title,
            'genre':               b.genre or '',
            'bpm':                 b.bpm,
            'key':                 b.key or '',
            'mood_tag':            b.mood_tag or '',
            'duration':            b.duration or '3:00',
            'price':               b.price,
            'premium_price':       b.premium_price,
            'exclusive_price':     b.exclusive_price,
            'licence_type':        b.licence_type or '',
            'play_count':          b.play_count,
            'likes_count':         b.likes_count,
            'comment_count':       b.comment_count,
            'producer_id':         b.producer_id,
            'producer_username':   producer.username if producer else 'Unknown',
            'producer_avatar':     producer.avatar_url if producer else '',
            'audio_url':           b.audio_url or '',
            'is_liked':            b.id in liked_ids,
            'is_saved':            b.id in saved_ids,
            'is_following':        b.producer_id in following_ids,
            'is_trending':         b.is_trending,
            'owned_tiers':         sorted(owned_tiers.get(b.id, [])),
            'is_own_beat':         current_user.is_authenticated and b.producer_id == current_user.id,
        })

    return jsonify({'beats': result, 'has_next': len(beats) > per_page, 'page': page})


# ---------------------------------------------------------------------------
# Beat interactions
# ---------------------------------------------------------------------------

@api.route('/beats/<int:beat_id>/save', methods=['POST'])
@limiter.limit('60 per minute')
def toggle_save(beat_id):
    """Toggle the saved/bookmark state for `beat_id`. Returns {'saved': bool}."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    beat = Beat.query.get_or_404(beat_id)
    if current_user.has_saved(beat):
        current_user.unsave_beat(beat)
        saved = False
    else:
        current_user.save_beat(beat)
        saved = True
    try:
        db.session.commit()
    except IntegrityError as e:
        db.session.rollback()
        if 'UNIQUE' in str(e.orig).upper():
            saved = True  # concurrent request already committed the save
        else:
            return jsonify({'error': 'Save failed'}), 409
    return jsonify({'saved': saved})


@api.route('/beats/<int:beat_id>/like', methods=['POST'])
@limiter.limit('60 per minute')
def toggle_like(beat_id):
    """Toggle the like state for `beat_id`. Returns {'liked': bool, 'likes_count': int}."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    beat = Beat.query.get_or_404(beat_id)
    if current_user.has_liked(beat):
        current_user.unlike_beat(beat)
        liked = False
    else:
        current_user.like_beat(beat)
        liked = True
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        liked = True  # concurrent request already committed the like
    return jsonify({'liked': liked, 'likes_count': beat.likes_count})


@api.route('/beats/<int:beat_id>/play', methods=['POST'])
@limiter.limit('120 per minute')
def record_play(beat_id):
    """Increment play count with per-user/session deduplication window."""
    beat = Beat.query.get_or_404(beat_id)

    # Resolve actor: logged-in user ID, or a session-scoped anonymous key
    user_id = current_user.id if current_user.is_authenticated else None
    session_key = None
    if not user_id:
        session_key = session.get('play_session_id')
        if not session_key:
            # Generate a persistent anonymous key stored in the Flask session cookie
            session_key = uuid4().hex
            session['play_session_id'] = session_key

    # Only count if no play event exists for this actor within the deduplication window
    window_start = datetime.utcnow() - timedelta(seconds=PLAY_DEDUPE_SECONDS)
    q = BeatPlayEvent.query.filter(
        BeatPlayEvent.beat_id == beat.id,
        BeatPlayEvent.created_at >= window_start,
    )
    q = q.filter_by(user_id=user_id) if user_id else q.filter_by(session_key=session_key)
    counted = q.first() is None

    if counted:
        beat.play_count += 1
        db.session.add(BeatPlayEvent(beat_id=beat.id, user_id=user_id, session_key=session_key))
        db.session.commit()

    return jsonify({'play_count': beat.play_count, 'counted': counted})


# ---------------------------------------------------------------------------
# Follow
# ---------------------------------------------------------------------------

@api.route('/producers/<int:producer_id>/follow', methods=['POST'])
@limiter.limit('30 per minute')
def toggle_follow(producer_id):
    """Toggle follow state for `producer_id`. Returns {'following': bool, 'followers_count': int}."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    producer = User.query.get_or_404(producer_id)
    if producer.id == current_user.id:
        return jsonify({'error': 'Cannot follow yourself'}), 400
    if current_user.is_following(producer):
        current_user.unfollow(producer)
        following = False
    else:
        current_user.follow(producer)
        following = True
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        following = True  # concurrent request already committed the follow
    return jsonify({'following': following, 'followers_count': producer.followers.count()})


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def _serialize_comment(comment, liked_ids, disliked_ids, reported_ids, replies_map=None):
    author = comment.author
    name   = author.username if author else 'Deleted User'
    avatar = author.avatar_url if (author and author.avatar_url) else ''

    can_delete = current_user.is_authenticated and current_user.id == comment.author_id
    reply_to   = comment.parent.author.username if (comment.parent and comment.parent.author) else None

    replies = (replies_map.get(comment.id, [])
               if replies_map is not None and comment.parent_id is None else [])

    return {
        'id':              comment.id,
        'beat_id':         comment.beat_id,
        'body':            comment.body,
        'author_id':       comment.author_id,
        'author_username': name,
        'author_avatar':   avatar,
        'created_at':      comment.created_at.isoformat() if comment.created_at else None,
        'likes_count':     comment.likes_count,
        'dislikes_count':  comment.dislikes_count,
        'is_liked':        comment.id in liked_ids,
        'is_disliked':     comment.id in disliked_ids,
        'is_reported':     comment.id in reported_ids,
        'can_delete':      can_delete,
        'parent_id':       comment.parent_id,
        'reply_to':        reply_to,
        'replies':         [_serialize_comment(r, liked_ids, disliked_ids, reported_ids) for r in replies],
    }


@api.route('/beats/<int:beat_id>/comments', methods=['GET'])
def get_comments(beat_id):
    Beat.query.get_or_404(beat_id)
    limit = min(request.args.get('limit', 20, type=int), 100)
    now = datetime.utcnow()

    # Pre-limit before Python scoring to avoid loading the entire table into memory
    raw = Comment.query.filter_by(beat_id=beat_id, parent_id=None).limit(limit * 5).all()

    raw_ids = [c.id for c in raw]
    score_like_map = dict(
        db.session.query(comment_likes.c.comment_id, db.func.count(comment_likes.c.user_id))
        .filter(comment_likes.c.comment_id.in_(raw_ids))
        .group_by(comment_likes.c.comment_id)
        .all()
    ) if raw_ids else {}

    # Engagement-first ranking with freshness decay and bounded randomness.
    # Prevents older comments from locking in permanently.
    def comment_score(c):
        age_h = max((now - c.created_at).total_seconds() / 3600, 0) if c.created_at else 0
        return (
            score_like_map.get(c.id, 0) * 2.4
            + 6.0 / (1.0 + age_h / 3.0)
            + (1.2 if age_h < 2 else 0)
            + random.uniform(0, 2.0 if age_h < 12 else 0.45)
        )

    scored = sorted(raw, key=comment_score, reverse=True)[:limit]

    # Batch-load all replies in one query, then group by parent
    # Cap at 3× the top-level limit to prevent unbounded loads on busy beats
    scored_ids = [c.id for c in scored]
    all_replies = (Comment.query
                   .filter(Comment.parent_id.in_(scored_ids))
                   .order_by(Comment.created_at.asc())
                   .limit(limit * 3)
                   .all()) if scored_ids else []
    replies_map = {}
    for r in all_replies:
        replies_map.setdefault(r.parent_id, []).append(r)

    all_ids = [c.id for c in scored] + [r.id for r in all_replies]

    liked_ids = disliked_ids = reported_ids = set()
    if current_user.is_authenticated and all_ids:
        liked_ids = {row[0] for row in
            db.session.query(comment_likes.c.comment_id)
            .filter(comment_likes.c.user_id == current_user.id,
                    comment_likes.c.comment_id.in_(all_ids))
            .all()}
        disliked_ids = {row[0] for row in
            db.session.query(comment_dislikes.c.comment_id)
            .filter(comment_dislikes.c.user_id == current_user.id,
                    comment_dislikes.c.comment_id.in_(all_ids))
            .all()}
        reported_ids = {row[0] for row in
            db.session.query(CommentReport.comment_id)
            .filter(CommentReport.user_id == current_user.id,
                    CommentReport.comment_id.in_(all_ids))
            .all()}

    return jsonify({'comments': [_serialize_comment(c, liked_ids, disliked_ids, reported_ids, replies_map) for c in scored]})


@api.route('/beats/<int:beat_id>/comments', methods=['POST'])
@limiter.limit('20 per minute')
def post_comment(beat_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    beat = Beat.query.get_or_404(beat_id)
    data      = request.get_json() or {}
    body      = data.get('body', '').strip()
    parent_id = data.get('parent_id')

    if not body:
        return jsonify({'error': 'Comment cannot be empty'}), 400
    if len(body) > MAX_COMMENT_LENGTH:
        return jsonify({'error': f'Comment too long (max {MAX_COMMENT_LENGTH} chars)'}), 400

    parent = None
    if parent_id is not None:
        try:
            parent = Comment.query.get_or_404(int(parent_id))
        except (ValueError, TypeError):
            return jsonify({'error': 'Invalid parent_id'}), 400
        if parent.beat_id != beat.id:
            return jsonify({'error': 'Parent comment not on this beat'}), 400
        if parent.parent_id is not None:
            return jsonify({'error': 'Replies can only be one level deep'}), 400

    comment = Comment(beat_id=beat_id, author_id=current_user.id, body=body,
                      parent_id=parent.id if parent else None)
    db.session.add(comment)
    db.session.commit()
    return jsonify(_serialize_comment(comment, set(), set(), set())), 201


@api.route('/comments/<int:comment_id>/like', methods=['POST'])
def toggle_comment_like(comment_id):
    """Toggle like on a comment. Removes any dislike first (mutually exclusive)."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    comment = Comment.query.get_or_404(comment_id)
    if current_user.has_liked_comment(comment):
        current_user.unlike_comment(comment)
        liked = False
    else:
        current_user.like_comment(comment)
        liked = True
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        liked = True  # concurrent request already committed the like
    return jsonify({'liked': liked, 'likes_count': comment.likes_count,
                    'dislikes_count': comment.dislikes_count})


@api.route('/comments/<int:comment_id>/dislike', methods=['POST'])
def toggle_comment_dislike(comment_id):
    """Toggle dislike on a comment. Removes any like first (mutually exclusive). Client hides the comment on dislike."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    comment = Comment.query.get_or_404(comment_id)
    if current_user.has_disliked_comment(comment):
        current_user.undislike_comment(comment)
        disliked = False
    else:
        current_user.dislike_comment(comment)
        disliked = True
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        disliked = True  # concurrent request already committed the dislike
    return jsonify({'disliked': disliked, 'dislikes_count': comment.dislikes_count,
                    'likes_count': comment.likes_count})


@api.route('/comments/<int:comment_id>/report', methods=['POST'])
def report_comment(comment_id):
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    comment = Comment.query.get_or_404(comment_id)

    # Prevent duplicate reports from the same user
    existing = CommentReport.query.filter_by(
        comment_id=comment_id, user_id=current_user.id
    ).first()
    if existing:
        return jsonify({'error': 'Already reported'}), 409

    data   = request.get_json() or {}
    reason = data.get('reason', 'inappropriate')[:64]

    report = CommentReport(comment_id=comment_id, user_id=current_user.id, reason=reason)
    comment.report_count += 1
    db.session.add(report)
    db.session.commit()
    return jsonify({'reported': True, 'report_count': comment.report_count})


@api.route('/comments/<int:comment_id>/report', methods=['DELETE'])
def unreport_comment(comment_id):
    """Undo a previous report by the current user. Decrements the comment's report count."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    report = CommentReport.query.filter_by(
        comment_id=comment_id, user_id=current_user.id
    ).first()
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    comment = Comment.query.get_or_404(comment_id)
    comment.report_count = max(0, comment.report_count - 1)
    db.session.delete(report)
    db.session.commit()
    return jsonify({'reported': False, 'report_count': comment.report_count})


@api.route('/search')
@limiter.limit('60 per minute')
def search():
    """AJAX search endpoint — returns beats and producers as JSON."""
    query        = request.args.get('q', '').strip()[:128]
    search_type  = request.args.get('type', 'all')
    genre_filter = request.args.get('genre', '').strip()[:64]

    beats_out = []
    producers_out = []

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
            beats_list = bq.order_by(Beat.uploaded_at.desc()).limit(SEARCH_MAX_RESULTS).all()
            if beats_list:
                beat_ids = [b.id for b in beats_list]
                beat_like_counts = dict(
                    db.session.query(Like.beat_id, db.func.count(Like.id))
                    .filter(Like.beat_id.in_(beat_ids))
                    .group_by(Like.beat_id)
                    .all()
                )
                for b in beats_list:
                    beats_out.append({
                        'id':          b.id,
                        'title':       b.title,
                        'genre':       b.genre or '',
                        'bpm':         b.bpm,
                        'key':         b.key or '',
                        'likes_count': beat_like_counts.get(b.id, 0),
                    })

        if search_type in ('all', 'producers') and query:
            producers = User.query.filter(
                User.username.ilike(f'%{query}%') |
                User.bio.ilike(f'%{query}%')
            ).limit(SEARCH_MAX_RESULTS).all()
            if producers:
                rows = (db.session.query(follows.c.followed_id, db.func.count(follows.c.follower_id))
                        .filter(follows.c.followed_id.in_([p.id for p in producers]))
                        .group_by(follows.c.followed_id).all())
                follower_map = {pid: cnt for pid, cnt in rows}
                for p in producers:
                    producers_out.append({
                        'id':              p.id,
                        'username':        p.username,
                        'followers_count': follower_map.get(p.id, 0),
                    })

    return jsonify({
        'beats':        beats_out,
        'producers':    producers_out,
        'query':        query,
        'search_type':  search_type,
        'genre_filter': genre_filter,
    })


# ---------------------------------------------------------------------------
# Spotify connection status
# ---------------------------------------------------------------------------

@api.route('/spotify/status')
def spotify_status():
    """Return the current user's Spotify connection state as JSON.

    Used by the edit-profile page to reflect connection status without a
    full page reload. Returns 401 for unauthenticated requests.
    """
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    return jsonify({
        'connected':          current_user.spotify_connected,
        'display_name':       current_user.spotify_display_name or '',
        'spotify_url':        current_user.spotify_url or '',
        'spotify_artist_url': current_user.spotify_artist_url or '',
    })


@api.route('/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    """Permanently delete a comment. Only the comment's author is allowed."""
    if not current_user.is_authenticated:
        return jsonify({'error': 'Authentication required'}), 401
    comment = Comment.query.get_or_404(comment_id)
    if comment.author_id != current_user.id:
        return jsonify({'error': 'Forbidden'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'deleted': True})
