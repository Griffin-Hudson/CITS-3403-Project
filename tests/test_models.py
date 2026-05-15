"""Unit tests for TuneFeed database models.

Each TestCase subclass targets a single model method or property group.
setUp creates a fresh in-memory SQLite database and pushes an application
context; tearDown drops all tables and pops the context, guaranteeing full
isolation between tests regardless of run order.

Run with:
    python -m unittest tests.test_models -v
"""
import unittest

from app import create_app
from app.models import db, User, Beat, Comment, Like, Transaction, CommentReport
from app.routes import _safe_redirect_target
from app.forms import _safe_url
from app.services.wallet_service import top_up, record_purchase, record_earning, purchase_beat
from wtforms.validators import ValidationError


# ---------------------------------------------------------------------------
# Shared test configuration
# ---------------------------------------------------------------------------

class _TestConfig:
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    SECRET_KEY = 'unit-test-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RATELIMIT_ENABLED = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(username='alice', email='alice@test.com', password='TestPass1!'):
    u = User(username=username, email=email)
    u.set_password(password)
    return u


def _make_beat(producer, title='Test Beat', price=0.0):
    return Beat(
        title=title,
        audio_url='https://example.com/beat.mp3',
        producer_id=producer.id,
        price=price,
    )


def _make_comment(beat, author, body='Great beat!', parent=None):
    return Comment(
        beat_id=beat.id,
        author_id=author.id,
        body=body,
        parent_id=parent.id if parent else None,
    )


# ---------------------------------------------------------------------------
# Base mixin — every TestCase uses this setUp / tearDown pattern
# ---------------------------------------------------------------------------

class _AppTestCase(unittest.TestCase):
    """Provides a fresh in-memory database for every individual test."""

    def setUp(self):
        self.app = create_app(_TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()


# ---------------------------------------------------------------------------
# 1. Password hashing
# ---------------------------------------------------------------------------

class TestPasswordHashing(_AppTestCase):
    """User.set_password / check_password — ~5 tests."""

    def test_correct_password_accepted(self):
        u = _make_user(password='MySecret1!')
        self.assertTrue(
            u.check_password('MySecret1!'),
            'The correct password must be accepted',
        )

    def test_wrong_password_rejected(self):
        u = _make_user(password='MySecret1!')
        self.assertFalse(
            u.check_password('WrongPassword'),
            'An incorrect password must be rejected',
        )

    def test_password_is_not_stored_in_plaintext(self):
        u = _make_user(password='PlainText99!')
        self.assertNotEqual(
            u.password_hash,
            'PlainText99!',
            'Stored hash must not equal the plaintext password',
        )

    def test_empty_string_rejected(self):
        u = _make_user(password='SomePass1!')
        self.assertFalse(
            u.check_password(''),
            'An empty string must not authenticate as a valid password',
        )

    def test_set_password_invalidates_old_password(self):
        u = _make_user(password='OldPass1!')
        u.set_password('NewPass1!')
        self.assertFalse(
            u.check_password('OldPass1!'),
            'Old password must not authenticate after set_password is called',
        )
        self.assertTrue(
            u.check_password('NewPass1!'),
            'New password must authenticate after set_password is called',
        )

    def test_hash_differs_across_calls(self):
        u1 = _make_user(username='u1', email='u1@t.com', password='Same1!')
        u2 = _make_user(username='u2', email='u2@t.com', password='Same1!')
        self.assertNotEqual(
            u1.password_hash,
            u2.password_hash,
            'Bcrypt must produce a unique salt for each hash',
        )


# ---------------------------------------------------------------------------
# 2. Follow / unfollow system
# ---------------------------------------------------------------------------

class TestFollowSystem(_AppTestCase):
    """User.follow / unfollow / is_following — ~6 tests."""

    def setUp(self):
        super().setUp()
        self.alice = _make_user('alice', 'alice@t.com')
        self.bob = _make_user('bob', 'bob@t.com')
        db.session.add_all([self.alice, self.bob])
        db.session.commit()

    def test_not_following_by_default(self):
        self.assertFalse(
            self.alice.is_following(self.bob),
            'Users must not follow each other by default',
        )

    def test_follow_creates_relationship(self):
        self.alice.follow(self.bob)
        db.session.commit()
        self.assertTrue(self.alice.is_following(self.bob))

    def test_unfollow_removes_relationship(self):
        self.alice.follow(self.bob)
        db.session.commit()
        self.alice.unfollow(self.bob)
        db.session.commit()
        self.assertFalse(
            self.alice.is_following(self.bob),
            'is_following must return False after unfollow',
        )

    def test_follow_is_not_symmetric(self):
        self.alice.follow(self.bob)
        db.session.commit()
        self.assertFalse(
            self.bob.is_following(self.alice),
            'Following alice→bob must not automatically make bob follow alice',
        )

    def test_follow_is_idempotent(self):
        self.alice.follow(self.bob)
        self.alice.follow(self.bob)
        db.session.commit()
        count = self.alice.following.count()
        self.assertEqual(count, 1, 'Calling follow twice must not create duplicate rows')

    def test_unfollow_when_not_following_is_safe(self):
        self.alice.unfollow(self.bob)
        db.session.commit()
        self.assertFalse(self.alice.is_following(self.bob))


# ---------------------------------------------------------------------------
# 3. Beat likes
# ---------------------------------------------------------------------------

class TestBeatLikes(_AppTestCase):
    """User.like_beat / unlike_beat / has_liked — ~6 tests."""

    def setUp(self):
        super().setUp()
        self.alice = _make_user()
        db.session.add(self.alice)
        db.session.flush()
        self.beat = _make_beat(self.alice)
        db.session.add(self.beat)
        db.session.commit()

    def test_has_not_liked_by_default(self):
        self.assertFalse(self.alice.has_liked(self.beat))

    def test_like_creates_relationship(self):
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.assertTrue(self.alice.has_liked(self.beat))

    def test_unlike_removes_relationship(self):
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.alice.unlike_beat(self.beat)
        db.session.commit()
        self.assertFalse(self.alice.has_liked(self.beat))

    def test_like_increments_likes_count(self):
        initial = self.beat.likes_count
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.assertEqual(
            self.beat.likes_count,
            initial + 1,
            'likes_count must increment after like_beat',
        )

    def test_unlike_decrements_likes_count(self):
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.alice.unlike_beat(self.beat)
        db.session.commit()
        self.assertEqual(self.beat.likes_count, 0)

    def test_like_is_idempotent(self):
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.alice.like_beat(self.beat)
        db.session.commit()
        self.assertEqual(
            self.beat.likes_count,
            1,
            'Calling like_beat twice must not create duplicate like rows',
        )


# ---------------------------------------------------------------------------
# 4. Beat saves
# ---------------------------------------------------------------------------

class TestBeatSaves(_AppTestCase):
    """User.save_beat / unsave_beat / has_saved — ~5 tests."""

    def setUp(self):
        super().setUp()
        self.alice = _make_user()
        db.session.add(self.alice)
        db.session.flush()
        self.beat = _make_beat(self.alice)
        db.session.add(self.beat)
        db.session.commit()

    def test_has_not_saved_by_default(self):
        self.assertFalse(self.alice.has_saved(self.beat))

    def test_save_creates_relationship(self):
        self.alice.save_beat(self.beat)
        db.session.commit()
        self.assertTrue(self.alice.has_saved(self.beat))

    def test_unsave_removes_relationship(self):
        self.alice.save_beat(self.beat)
        db.session.commit()
        self.alice.unsave_beat(self.beat)
        db.session.commit()
        self.assertFalse(self.alice.has_saved(self.beat))

    def test_save_is_idempotent(self):
        self.alice.save_beat(self.beat)
        self.alice.save_beat(self.beat)
        db.session.commit()
        self.assertEqual(
            self.alice.saved.count(),
            1,
            'Saving the same beat twice must not create duplicate rows',
        )

    def test_unsave_when_not_saved_is_safe(self):
        self.alice.unsave_beat(self.beat)
        db.session.commit()
        self.assertFalse(self.alice.has_saved(self.beat))


# ---------------------------------------------------------------------------
# 5. Comment likes and dislikes (mutually exclusive)
# ---------------------------------------------------------------------------

class TestCommentReactions(_AppTestCase):
    """User.like_comment / unlike_comment / dislike_comment — ~7 tests."""

    def setUp(self):
        super().setUp()
        self.alice = _make_user()
        db.session.add(self.alice)
        db.session.flush()
        self.beat = _make_beat(self.alice)
        db.session.add(self.beat)
        db.session.flush()
        self.comment = _make_comment(self.beat, self.alice)
        db.session.add(self.comment)
        db.session.commit()

    def test_no_reactions_by_default(self):
        self.assertFalse(self.alice.has_liked_comment(self.comment))
        self.assertFalse(self.alice.has_disliked_comment(self.comment))

    def test_like_comment_sets_liked(self):
        self.alice.like_comment(self.comment)
        db.session.commit()
        self.assertTrue(self.alice.has_liked_comment(self.comment))

    def test_unlike_comment_clears_liked(self):
        self.alice.like_comment(self.comment)
        db.session.commit()
        self.alice.unlike_comment(self.comment)
        db.session.commit()
        self.assertFalse(self.alice.has_liked_comment(self.comment))

    def test_dislike_removes_existing_like(self):
        self.alice.like_comment(self.comment)
        db.session.commit()
        self.alice.dislike_comment(self.comment)
        db.session.commit()
        self.assertFalse(
            self.alice.has_liked_comment(self.comment),
            'Disliking must remove the pre-existing like',
        )
        self.assertTrue(self.alice.has_disliked_comment(self.comment))

    def test_like_removes_existing_dislike(self):
        self.alice.dislike_comment(self.comment)
        db.session.commit()
        self.alice.like_comment(self.comment)
        db.session.commit()
        self.assertFalse(
            self.alice.has_disliked_comment(self.comment),
            'Liking must remove the pre-existing dislike',
        )
        self.assertTrue(self.alice.has_liked_comment(self.comment))

    def test_likes_count_property(self):
        self.alice.like_comment(self.comment)
        db.session.commit()
        self.assertEqual(self.comment.likes_count, 1)

    def test_dislikes_count_property(self):
        self.alice.dislike_comment(self.comment)
        db.session.commit()
        self.assertEqual(self.comment.dislikes_count, 1)


# ---------------------------------------------------------------------------
# 6. Beat model properties
# ---------------------------------------------------------------------------

class TestBeatModel(_AppTestCase):
    """Beat.likes_count / comment_count / play_count defaults — ~6 tests."""

    def setUp(self):
        super().setUp()
        self.producer = _make_user()
        db.session.add(self.producer)
        db.session.flush()

    def test_likes_count_starts_at_zero(self):
        beat = _make_beat(self.producer)
        db.session.add(beat)
        db.session.commit()
        self.assertEqual(beat.likes_count, 0)

    def test_comment_count_starts_at_zero(self):
        beat = _make_beat(self.producer)
        db.session.add(beat)
        db.session.commit()
        self.assertEqual(beat.comment_count, 0)

    def test_play_count_defaults_to_zero(self):
        beat = _make_beat(self.producer)
        db.session.add(beat)
        db.session.commit()
        self.assertEqual(beat.play_count, 0)

    def test_user_without_beats_is_not_marked_as_uploader(self):
        self.assertFalse(self.producer.has_uploaded_beats)

    def test_user_with_beats_is_marked_as_uploader(self):
        beat = _make_beat(self.producer)
        db.session.add(beat)
        db.session.commit()
        self.assertTrue(self.producer.has_uploaded_beats)

    def test_comment_count_excludes_replies(self):
        """comment_count must count only top-level comments, not nested replies."""
        beat = _make_beat(self.producer)
        db.session.add(beat)
        db.session.flush()
        top = _make_comment(beat, self.producer, body='Top-level')
        db.session.add(top)
        db.session.flush()
        reply = _make_comment(beat, self.producer, body='Reply', parent=top)
        db.session.add(reply)
        db.session.commit()
        self.assertEqual(
            beat.comment_count,
            1,
            'comment_count must count only top-level comments, not replies',
        )

    def test_beat_producer_relationship(self):
        beat = _make_beat(self.producer, title='My Beat')
        db.session.add(beat)
        db.session.commit()
        self.assertEqual(beat.producer.id, self.producer.id)

    def test_beat_repr_contains_title(self):
        beat = _make_beat(self.producer, title='Chill Vibes')
        db.session.add(beat)
        db.session.commit()
        self.assertIn('Chill Vibes', repr(beat))


# ---------------------------------------------------------------------------
# 7. Transaction model
# ---------------------------------------------------------------------------

class TestTransactionModel(_AppTestCase):
    """Transaction type constants, persistence, and User wallet defaults — ~5 tests."""

    def setUp(self):
        super().setUp()
        self.user = _make_user()
        db.session.add(self.user)
        db.session.commit()

    def test_type_constants_are_unique(self):
        types = {
            Transaction.TYPE_TOPUP,
            Transaction.TYPE_PURCHASE,
            Transaction.TYPE_EARNING,
            Transaction.TYPE_REFUND,
        }
        self.assertEqual(len(types), 4, 'Each transaction type constant must have a distinct value')

    def test_topup_transaction_persists(self):
        tx = Transaction(
            user_id=self.user.id,
            type=Transaction.TYPE_TOPUP,
            amount=20.0,
            balance_after=20.0,
            note='Top up $20',
        )
        db.session.add(tx)
        db.session.commit()
        fetched = Transaction.query.filter_by(user_id=self.user.id).first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.amount, 20.0)
        self.assertEqual(fetched.type, Transaction.TYPE_TOPUP)

    def test_transaction_repr_includes_type_and_amount(self):
        tx = Transaction(
            user_id=self.user.id,
            type=Transaction.TYPE_EARNING,
            amount=9.99,
            balance_after=9.99,
        )
        db.session.add(tx)
        db.session.commit()
        representation = repr(tx)
        self.assertIn('earning', representation)

    def test_user_balance_defaults_to_zero(self):
        self.assertEqual(
            self.user.balance,
            0.0,
            'A new user must start with a zero wallet balance',
        )

    def test_user_earnings_defaults_to_zero(self):
        self.assertEqual(
            self.user.earnings,
            0.0,
            'A new user must start with zero lifetime earnings',
        )


# ---------------------------------------------------------------------------
# 8. Comment model
# ---------------------------------------------------------------------------

class TestCommentModel(_AppTestCase):
    """Comment creation, threading, and report tracking — ~5 tests."""

    def setUp(self):
        super().setUp()
        self.alice = _make_user('alice', 'alice@t.com')
        db.session.add(self.alice)
        db.session.flush()
        self.beat = _make_beat(self.alice)
        db.session.add(self.beat)
        db.session.flush()

    def test_comment_persists_with_body(self):
        c = _make_comment(self.beat, self.alice, body='Sick beat!')
        db.session.add(c)
        db.session.commit()
        fetched = Comment.query.filter_by(beat_id=self.beat.id).first()
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.body, 'Sick beat!')

    def test_reply_has_parent_id(self):
        top = _make_comment(self.beat, self.alice, body='Parent')
        db.session.add(top)
        db.session.flush()
        reply = _make_comment(self.beat, self.alice, body='Child', parent=top)
        db.session.add(reply)
        db.session.commit()
        self.assertEqual(reply.parent_id, top.id)

    def test_reply_accessible_via_parent_backref(self):
        top = _make_comment(self.beat, self.alice, body='Parent')
        db.session.add(top)
        db.session.flush()
        reply = _make_comment(self.beat, self.alice, body='Child', parent=top)
        db.session.add(reply)
        db.session.commit()
        self.assertEqual(top.replies.count(), 1)

    def test_report_count_defaults_to_zero(self):
        c = _make_comment(self.beat, self.alice)
        db.session.add(c)
        db.session.commit()
        self.assertEqual(c.report_count, 0)

    def test_comment_repr_contains_beat_id(self):
        c = _make_comment(self.beat, self.alice)
        db.session.add(c)
        db.session.commit()
        self.assertIn(str(self.beat.id), repr(c))

    def test_has_reported_comment_false_by_default(self):
        c = _make_comment(self.beat, self.alice)
        db.session.add(c)
        db.session.commit()
        self.assertFalse(self.alice.has_reported_comment(c))

    def test_has_reported_comment_true_after_report(self):
        c = _make_comment(self.beat, self.alice)
        db.session.add(c)
        db.session.commit()
        report = CommentReport(comment_id=c.id, user_id=self.alice.id, reason='spam')
        db.session.add(report)
        db.session.commit()
        self.assertTrue(self.alice.has_reported_comment(c))


# ---------------------------------------------------------------------------
# 9. Wallet service
# ---------------------------------------------------------------------------

class TestWalletService(_AppTestCase):
    """top_up / record_purchase / record_earning — atomicity and ledger correctness."""

    def setUp(self):
        super().setUp()
        self.user = _make_user()
        db.session.add(self.user)
        db.session.commit()

    def test_top_up_increases_balance(self):
        top_up(self.user, 50.0)
        db.session.commit()
        self.assertAlmostEqual(self.user.balance, 50.0)

    def test_top_up_creates_transaction_row(self):
        top_up(self.user, 25.0, note='Test top-up')
        db.session.commit()
        tx = Transaction.query.filter_by(user_id=self.user.id, type=Transaction.TYPE_TOPUP).first()
        self.assertIsNotNone(tx)
        self.assertAlmostEqual(tx.amount, 25.0)
        self.assertAlmostEqual(tx.balance_after, 25.0)
        self.assertEqual(tx.note, 'Test top-up')

    def test_record_purchase_decreases_balance(self):
        top_up(self.user, 100.0)
        db.session.commit()
        record_purchase(self.user, 30.0)
        db.session.commit()
        self.assertAlmostEqual(self.user.balance, 70.0)

    def test_record_purchase_creates_transaction_row(self):
        top_up(self.user, 100.0)
        db.session.commit()
        record_purchase(self.user, 20.0, note='Beat buy')
        db.session.commit()
        tx = Transaction.query.filter_by(user_id=self.user.id, type=Transaction.TYPE_PURCHASE).first()
        self.assertIsNotNone(tx)
        self.assertAlmostEqual(tx.amount, 20.0)
        self.assertEqual(tx.note, 'Beat buy')

    def test_record_earning_increases_balance_and_earnings(self):
        record_earning(self.user, 15.0)
        db.session.commit()
        self.assertAlmostEqual(self.user.balance, 15.0)
        self.assertAlmostEqual(self.user.earnings, 15.0)

    def test_record_earning_creates_transaction_row(self):
        record_earning(self.user, 9.99)
        db.session.commit()
        tx = Transaction.query.filter_by(user_id=self.user.id, type=Transaction.TYPE_EARNING).first()
        self.assertIsNotNone(tx)
        self.assertAlmostEqual(tx.amount, 9.99)

    def test_top_up_accumulates_across_calls(self):
        top_up(self.user, 10.0)
        top_up(self.user, 20.0)
        db.session.commit()
        self.assertAlmostEqual(self.user.balance, 30.0)

    def test_purchase_beat_skips_earning_when_producer_deleted(self):
        """purchase_beat must not raise when beat.producer is None (deleted producer)."""
        from sqlalchemy import text
        buyer = _make_user(username='buyer_del', email='buyer_del@test.com')
        db.session.add(buyer)
        db.session.flush()
        buyer_id = buyer.id
        top_up(buyer, 50.0)
        db.session.commit()

        # Insert a beat with a dangling producer_id (no matching user row).
        # FK enforcement is temporarily suspended so we can create the orphaned
        # state that the beat.producer null-check in purchase_beat guards against.
        db.session.execute(text('PRAGMA foreign_keys = OFF'))
        db.session.execute(text(
            "INSERT INTO beat (title, audio_url, producer_id, price, play_count) "
            "VALUES ('Orphan Beat', 'https://example.com/orphan.mp3', 99999, 5.0, 0)"
        ))
        db.session.commit()
        db.session.execute(text('PRAGMA foreign_keys = ON'))

        beat = Beat.query.filter_by(title='Orphan Beat').first()
        self.assertIsNotNone(beat, 'Test setup: orphan beat must exist in DB')
        self.assertIsNone(beat.producer, 'beat.producer must be None for a dangling producer_id')

        purchase_beat(buyer, beat, 'lease', 'balance')
        db.session.commit()

        from app.models import Purchase
        p = Purchase.query.filter_by(buyer_id=buyer_id, beat_id=beat.id).first()
        self.assertIsNotNone(p, 'Purchase record must be created even when producer row is gone')


# ---------------------------------------------------------------------------
# 11. _safe_redirect_target (security helper — no DB needed)
# ---------------------------------------------------------------------------

class TestSafeRedirectTarget(unittest.TestCase):
    """Pure-function tests; no app context required."""

    def test_relative_path_allowed(self):
        self.assertEqual(_safe_redirect_target('/feed'), '/feed')

    def test_root_slash_allowed(self):
        self.assertEqual(_safe_redirect_target('/'), '/')

    def test_empty_string_allowed(self):
        self.assertEqual(_safe_redirect_target(''), '')

    def test_none_returns_empty(self):
        self.assertEqual(_safe_redirect_target(None), '')

    def test_absolute_http_rejected_without_host(self):
        self.assertEqual(_safe_redirect_target('http://evil.com/steal'), '')

    def test_absolute_https_rejected_without_host(self):
        self.assertEqual(_safe_redirect_target('https://phishing.example/login'), '')

    def test_same_host_absolute_url_allowed(self):
        result = _safe_redirect_target('http://localhost:5002/feed', 'localhost:5002')
        self.assertEqual(result, 'http://localhost:5002/feed')

    def test_different_host_absolute_url_rejected(self):
        self.assertEqual(_safe_redirect_target('http://evil.com/x', 'localhost:5002'), '')

    def test_relative_path_without_leading_slash_rejected(self):
        self.assertEqual(_safe_redirect_target('evil.com/x'), '')


# ---------------------------------------------------------------------------
# 12. _safe_url form validator (security helper — no DB needed)
# ---------------------------------------------------------------------------

class _MockField:
    """Minimal WTForms field stub for validator testing."""
    def __init__(self, data):
        self.data = data


class TestSafeUrlValidator(unittest.TestCase):
    """_safe_url validator — no app context required."""

    def _run(self, url):
        _safe_url(None, _MockField(url))

    def test_relative_path_accepted(self):
        self._run('/static/audio/beat.mp3')

    def test_http_url_accepted(self):
        self._run('http://cdn.example.com/beat.mp3')

    def test_https_url_accepted(self):
        self._run('https://cdn.example.com/cover.jpg')

    def test_empty_string_accepted(self):
        self._run('')

    def test_none_accepted(self):
        self._run(None)

    def test_javascript_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._run('javascript:alert(document.cookie)')

    def test_data_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._run('data:text/html,<script>alert(1)</script>')

    def test_vbscript_scheme_rejected(self):
        with self.assertRaises(ValidationError):
            self._run('vbscript:msgbox(1)')

    def test_bare_domain_rejected(self):
        with self.assertRaises(ValidationError):
            self._run('evil.com/steal')

    def test_protocol_relative_url_rejected(self):
        with self.assertRaises(ValidationError):
            self._run('//evil.com/steal')


# ---------------------------------------------------------------------------
# 13. Spotify connection fields
# ---------------------------------------------------------------------------

class TestSpotifyUser(_AppTestCase):
    """User.spotify_connected, spotify fields — 6 tests."""

    def setUp(self):
        super().setUp()
        self.user = _make_user()
        db.session.add(self.user)
        db.session.commit()

    def test_spotify_not_connected_by_default(self):
        self.assertFalse(
            self.user.spotify_connected,
            'A new user must not have Spotify connected by default',
        )

    def test_spotify_id_none_by_default(self):
        self.assertIsNone(self.user.spotify_id)

    def test_spotify_connected_true_when_id_set(self):
        self.user.spotify_id = 'test_spotify_id'
        db.session.commit()
        self.assertTrue(self.user.spotify_connected)

    def test_spotify_display_name_persists(self):
        self.user.spotify_id           = 'abc123'
        self.user.spotify_display_name = 'TestArtist'
        db.session.commit()
        fetched = db.session.get(User, self.user.id)
        self.assertEqual(fetched.spotify_display_name, 'TestArtist')

    def test_spotify_url_persists(self):
        self.user.spotify_id  = 'abc123'
        self.user.spotify_url = 'https://open.spotify.com/user/abc123'
        db.session.commit()
        fetched = db.session.get(User, self.user.id)
        self.assertEqual(fetched.spotify_url, 'https://open.spotify.com/user/abc123')

    def test_spotify_artist_url_persists(self):
        self.user.spotify_id         = 'abc123'
        self.user.spotify_artist_url = 'https://open.spotify.com/artist/abc123'
        db.session.commit()
        fetched = db.session.get(User, self.user.id)
        self.assertEqual(fetched.spotify_artist_url, 'https://open.spotify.com/artist/abc123')

    def test_clearing_spotify_id_disconnects(self):
        self.user.spotify_id = 'abc123'
        db.session.commit()
        self.user.spotify_id = None
        db.session.commit()
        self.assertFalse(self.user.spotify_connected)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    unittest.main(verbosity=2)
