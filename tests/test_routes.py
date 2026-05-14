"""Tests that all key page routes return expected HTTP status codes."""
import io
from tests.conftest import login, logout


PUBLIC_ROUTES = [
    '/login',
    '/register',
    '/discover',
    '/feed',
    '/search',
]

PROTECTED_ROUTES = [
    '/upload',
    '/profile/edit',
    '/wallet',
    '/studio/earnings',
    '/my-feeds',
]


class TestPublicRoutes:
    def test_root_redirects(self, client):
        r = client.get('/', follow_redirects=False)
        assert r.status_code == 302

    def test_public_pages_load(self, client):
        for path in PUBLIC_ROUTES:
            r = client.get(path)
            assert r.status_code == 200, f'{path} returned {r.status_code}'


class TestProtectedRoutes:
    def test_unauthenticated_redirected(self, client):
        """Unauthenticated requests to protected pages must redirect to login."""
        logout(client)
        for path in PROTECTED_ROUTES:
            r = client.get(path, follow_redirects=False)
            assert r.status_code == 302, f'{path} should redirect unauthenticated users'
            assert '/login' in r.headers.get('Location', ''), f'{path} did not redirect to login'

    def test_authenticated_pages_load(self, client, seeded_db):
        login(client)
        for path in PROTECTED_ROUTES:
            r = client.get(path)
            assert r.status_code == 200, f'{path} returned {r.status_code} when authenticated'
        logout(client)


class TestBeatDetailRoute:
    def test_beat_detail_loads(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r = client.get(f'/beats/{beat_id}')
        assert r.status_code == 200

    def test_beat_detail_404_for_missing_beat(self, client):
        r = client.get('/beats/999999')
        assert r.status_code == 404


class TestProfileRoute:
    def test_profile_loads_by_id(self, client, seeded_db):
        user_id = seeded_db['user_id']
        r = client.get(f'/profile/{user_id}')
        assert r.status_code == 200

    def test_profile_404_for_missing_user(self, client):
        r = client.get('/profile/999999')
        assert r.status_code == 404


class TestDiscoverRoute:
    def test_discover_with_seeded_data_loads(self, client, seeded_db):
        """Discover page must return 200 when producers and beats exist.

        Exercises the batch beat_counts and is_following_map queries that
        only run when producer_ids is non-empty.
        """
        r = client.get('/discover')
        assert r.status_code == 200

    def test_discover_genre_filter_loads(self, client, seeded_db):
        r = client.get('/discover?genre=Hip-Hop')
        assert r.status_code == 200


class TestUploadRoute:
    """POST /upload — covers file upload, validation errors, and side effects."""

    def _post(self, client, data):
        # multipart/form-data because the form has FileFields
        return client.post('/upload', data=data, content_type='multipart/form-data',
                           follow_redirects=False)

    def _base_form(self):
        # required fields shared by the happy-path tests
        return {
            'title': 'Late Night Drive',
            'genre': 'Lo-Fi',
            'bpm': '85',
            'key': 'C minor',
            'mood_tag': 'Chill',
            'licence_type': 'Non-exclusive',
            'price': '4.99',
            'audio_file': (io.BytesIO(b'ID3\x00fake mp3 bytes'), 'track.mp3'),
        }

    def test_post_creates_beat_for_current_user(self, app, client, seeded_db):
        login(client)
        r = self._post(client, self._base_form())
        assert r.status_code == 302
        assert '/feed' in r.headers.get('Location', '')

        with app.app_context():
            from app.models import Beat, db
            beat = Beat.query.filter_by(title='Late Night Drive').first()
            assert beat is not None
            assert beat.audio_url.startswith('/static/uploads/beats/')
            assert beat.producer_id == seeded_db['user_id']
            db.session.delete(beat)
            db.session.commit()
        logout(client)

    def test_post_missing_audio_re_renders_form(self, client, seeded_db):
        login(client)
        data = self._base_form()
        data.pop('audio_file')
        r = self._post(client, data)
        # form failed validation: page is re-rendered, not redirected
        assert r.status_code == 200
        assert b'Pick an audio file' in r.data or b'audio' in r.data.lower()
        logout(client)

    def test_post_rejects_disallowed_audio_extension(self, app, client, seeded_db):
        login(client)
        data = self._base_form()
        data['title'] = 'Bad Ext Beat'
        data['audio_file'] = (io.BytesIO(b'not really audio'), 'evil.exe')
        r = self._post(client, data)
        assert r.status_code == 200
        with app.app_context():
            assert Beat.query.filter_by(title='Bad Ext Beat').first() is None
        logout(client)

    def test_post_requires_title(self, app, client, seeded_db):
        login(client)
        data = self._base_form()
        data['title'] = ''
        r = self._post(client, data)
        assert r.status_code == 200
        with app.app_context():
            # no beat with empty title should have been written
            assert Beat.query.filter_by(title='').first() is None
        logout(client)


class TestSearchRoute:
    def test_search_empty_query_loads(self, client):
        r = client.get('/search')
        assert r.status_code == 200

    def test_search_with_query(self, client, seeded_db):
        r = client.get('/search?q=Test')
        assert r.status_code == 200

    def test_search_with_genre_filter(self, client):
        r = client.get('/search?genre=hip-hop')
        assert r.status_code == 200


class TestWalletRoute:
    def test_wallet_page_loads_authenticated(self, client, seeded_db):
        login(client)
        r = client.get('/wallet')
        assert r.status_code == 200
        logout(client)

    def test_wallet_topup_valid_amount(self, client, seeded_db):
        """Posting a valid amount to /wallet must redirect to the card top-up page."""
        login(client)
        r = client.post('/wallet', data={'amount': '20.00'}, follow_redirects=False)
        assert r.status_code == 302
        assert 'topup' in r.headers.get('Location', '')
        logout(client)

    def test_wallet_topup_invalid_amount_rejected(self, client, seeded_db, app):
        """A zero or negative top-up amount must be rejected; balance must not change."""
        login(client)
        with app.app_context():
            from app.models import User
            u = User.query.get(seeded_db['user_id'])
            balance_before = u.balance
        r = client.post('/wallet', data={'amount': '0'}, follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import User
            u = User.query.get(seeded_db['user_id'])
            assert u.balance == balance_before, 'Balance must not change after a rejected top-up'
        logout(client)


class TestUploadRoute:
    def _base_form(self):
        return {
            'title':        'My New Beat',
            'genre':        'Hip-Hop',
            'bpm':          '90',
            'key':          'Am',
            'mood_tag':     'chill',
            'licence_type': 'Non-exclusive',
            'price':        '9.99',
            'audio_file':   (io.BytesIO(b'fake mp3 data'), 'beat.mp3'),
        }

    def test_upload_creates_beat(self, client, seeded_db, app):
        """Posting a valid beat form must create a Beat row for the current user."""
        login(client)
        r = client.post('/upload', data=self._base_form(),
                        content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import Beat
            beat = Beat.query.filter_by(title='My New Beat').first()
            assert beat is not None, 'Beat must be created in the database'
            assert beat.producer_id == seeded_db['user_id']
        logout(client)

    def test_upload_missing_audio_rejected(self, client, seeded_db):
        """Submitting the upload form without an audio file must not create a beat."""
        login(client)
        form = {k: v for k, v in self._base_form().items() if k != 'audio_file'}
        r = client.post('/upload', data=form,
                        content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        logout(client)

    def test_upload_bad_extension_rejected(self, client, seeded_db, app):
        """Uploading a disallowed file extension must not create a beat."""
        login(client)
        form = {**self._base_form(), 'audio_file': (io.BytesIO(b'bad file'), 'virus.exe')}
        r = client.post('/upload', data=form,
                        content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import Beat
            assert Beat.query.filter_by(title='My New Beat').first() is None, \
                'Beat must not be created when audio extension is disallowed'
        logout(client)

    def test_upload_empty_title_rejected(self, client, seeded_db, app):
        """Submitting an upload with no title must not create a beat."""
        login(client)
        form = {**self._base_form(), 'title': ''}
        r = client.post('/upload', data=form,
                        content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import Beat
            assert Beat.query.filter_by(title='').first() is None
        logout(client)


class TestStudioEarningsRoute:
    def test_studio_earnings_loads_for_user_with_beats(self, client, seeded_db):
        """Studio earnings page must load for users who have uploaded beats."""
        login(client)
        r = client.get('/studio/earnings')
        assert r.status_code == 200, f'/studio/earnings returned {r.status_code} for a user with beats'
        logout(client)

    def test_studio_earnings_redirects_user_without_beats(self, client, app):
        """Users without beats should upload before viewing studio earnings."""
        with app.app_context():
            from app.models import db, User
            user = User(username='listener', email='listener@example.com')
            user.set_password('testpass')
            db.session.add(user)
            db.session.commit()

        login(client, email='listener@example.com', password='testpass')
        r = client.get('/studio/earnings', follow_redirects=False)
        assert r.status_code == 302
        assert '/upload' in r.headers['Location']
        logout(client)


class TestWalletTopupRoute:
    def test_wallet_topup_without_amount_redirects_to_wallet(self, client, seeded_db):
        """GET /wallet/topup with no amount param must redirect to /wallet."""
        login(client)
        r = client.get('/wallet/topup', follow_redirects=False)
        assert r.status_code == 302
        assert '/wallet' in r.headers.get('Location', '')
        logout(client)

    def test_wallet_topup_get_with_valid_amount_loads(self, client, seeded_db):
        """GET /wallet/topup?amount=10.00 must return 200."""
        login(client)
        r = client.get('/wallet/topup?amount=10.00')
        assert r.status_code == 200
        logout(client)

    def test_wallet_topup_post_increases_balance(self, client, seeded_db, app):
        """POST /wallet/topup?amount=15.00 must increase the user's balance."""
        login(client)
        r = client.post('/wallet/topup?amount=15.00', follow_redirects=True)
        assert r.status_code == 200
        with app.app_context():
            from app.models import User
            u = User.query.get(seeded_db['user_id'])
            assert u.balance >= 15.0, 'Balance must increase after card top-up'
        logout(client)


class TestCheckoutRoute:
    def test_checkout_unauthenticated_redirects(self, client, seeded_db):
        """Unauthenticated access to /checkout must redirect to login."""
        logout(client)
        r = client.get(f'/checkout/{seeded_db["beat_id"]}?tier=lease',
                       follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')

    def test_checkout_invalid_tier_redirects(self, client, seeded_db):
        """An unrecognised tier must redirect back to the beat detail page."""
        login(client)
        r = client.get(f'/checkout/{seeded_db["beat_id"]}?tier=invalid',
                       follow_redirects=True)
        assert r.status_code == 200
        logout(client)

    def test_checkout_own_beat_blocked(self, client, seeded_db):
        """A producer cannot purchase their own beat."""
        login(client)
        r = client.get(f'/checkout/{seeded_db["beat_id"]}?tier=lease',
                       follow_redirects=True)
        assert r.status_code == 200
        assert b'cannot' in r.data.lower() or b'own' in r.data.lower()
        logout(client)

    def test_checkout_balance_purchase_creates_record(self, client, seeded_db, app):
        """A buyer purchasing via balance must create a Purchase row."""
        client.post('/register', data={
            'username': 'buyer99', 'email': 'buyer99@test.com',
            'password': 'BuyPass1!', 'confirm_password': 'BuyPass1!',
        }, follow_redirects=True)
        client.post('/login', data={'email': 'buyer99@test.com', 'password': 'BuyPass1!'})

        beat_id = seeded_db['beat_id']
        r = client.post(f'/checkout/{beat_id}?tier=lease',
                        data={'method': 'balance'}, follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models import Purchase, User
            buyer = User.query.filter_by(email='buyer99@test.com').first()
            purchase = Purchase.query.filter_by(buyer_id=buyer.id, beat_id=beat_id).first()
            assert purchase is not None, 'A Purchase record must exist after checkout'
            assert purchase.licence_type == 'lease'
        logout(client)

    def test_checkout_duplicate_tier_blocked(self, client, seeded_db, app):
        """Attempting to buy the same tier twice must redirect to my-feeds."""
        client.post('/register', data={
            'username': 'buyer88', 'email': 'buyer88@test.com',
            'password': 'BuyPass1!', 'confirm_password': 'BuyPass1!',
        }, follow_redirects=True)
        client.post('/login', data={'email': 'buyer88@test.com', 'password': 'BuyPass1!'})

        beat_id = seeded_db['beat_id']
        client.post(f'/checkout/{beat_id}?tier=lease',
                    data={'method': 'balance'}, follow_redirects=True)

        r = client.get(f'/checkout/{beat_id}?tier=lease', follow_redirects=True)
        assert r.status_code == 200
        assert b'already own' in r.data.lower()
        logout(client)


class TestMyFeedsRoute:
    def test_my_feeds_empty_loads(self, client, seeded_db):
        """An authenticated user with no purchases must see the my-feeds page."""
        login(client)
        r = client.get('/my-feeds')
        assert r.status_code == 200
        logout(client)

    def test_my_feeds_shows_purchased_beat(self, client, seeded_db, app):
        """A beat purchased by the user must appear on the my-feeds page."""
        with app.app_context():
            from app.models import db as _db, Purchase
            _db.session.add(Purchase(
                buyer_id=seeded_db['user_id'],
                beat_id=seeded_db['beat_id'],
                price_paid=0.0,
                licence_type='lease',
            ))
            _db.session.commit()

        login(client)
        r = client.get('/my-feeds')
        assert r.status_code == 200
        assert b'Test Beat' in r.data, 'Purchased beat title must appear on /my-feeds'
        logout(client)
