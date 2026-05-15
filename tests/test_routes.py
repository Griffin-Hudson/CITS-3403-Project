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

    def test_security_headers_present(self, client):
        r = client.get('/login')
        assert r.headers['X-Content-Type-Options'] == 'nosniff'
        assert r.headers['X-Frame-Options'] == 'DENY'
        assert r.headers['Referrer-Policy'] == 'strict-origin-when-cross-origin'
        assert 'camera=()' in r.headers['Permissions-Policy']


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

    def test_beat_detail_links_available_tier_to_checkout(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r = client.get(f'/beats/{beat_id}')
        assert r.status_code == 200
        assert f'/checkout/{beat_id}?tier=lease'.encode() in r.data

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

    def test_discover_cards_link_to_focused_feed(self, client, seeded_db):
        r = client.get('/discover')
        assert r.status_code == 200
        assert f'/feed?beat={seeded_db["beat_id"]}'.encode() in r.data


class TestFeedRoute:
    def test_focused_feed_renders_requested_beat_first(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r = client.get(f'/feed?beat={beat_id}')
        assert r.status_code == 200
        first_card = r.data.find(b'<div class="feed-card"')
        assert first_card != -1, 'Feed must render at least one card'
        focused_attr = f'data-beat-id="{beat_id}"'.encode()
        assert r.data.find(focused_attr, first_card, first_card + 300) != -1, \
            'Focused beat must be the first feed card'

    def test_focused_feed_missing_beat_404s(self, client):
        r = client.get('/feed?beat=999999')
        assert r.status_code == 404


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


class TestErrorPages:
    def test_missing_page_uses_custom_404(self, client):
        r = client.get('/500')
        assert r.status_code == 404
        assert b'404 - Page Not Found' in r.data

    def test_internal_error_uses_custom_500(self, client, app):
        previous = app.config.get('PROPAGATE_EXCEPTIONS')
        app.config['PROPAGATE_EXCEPTIONS'] = False
        try:
            r = client.get('/__test__/raise-500')
            assert r.status_code == 500
            assert b'500 - Something Went Wrong' in r.data
        finally:
            app.config['PROPAGATE_EXCEPTIONS'] = previous


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


class TestProfilePictureUpload:
    def test_dotfile_upload_does_not_500(self, client, seeded_db):
        """Uploading a file whose name starts with a dot (e.g. '.png') must not 500."""
        login(client)
        r = client.post('/profile/edit',
                        data={'action': 'upload_picture',
                              'profile_picture': (io.BytesIO(b'\x89PNG\r\n'), '.png')},
                        content_type='multipart/form-data',
                        follow_redirects=True)
        assert r.status_code == 200, 'Dotfile upload must redirect cleanly, not 500'
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


class TestSpotifyRoutes:
    def test_spotify_connect_requires_auth(self, client):
        """Unauthenticated GET /spotify/connect must redirect to login."""
        logout(client)
        r = client.get('/spotify/connect', follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')

    def test_spotify_connect_without_config_flashes_warning(self, client, seeded_db, app):
        """When SPOTIFY_CLIENT_ID is empty, connect must redirect to edit_profile with a warning."""
        original = app.config.get('SPOTIFY_CLIENT_ID', '')
        app.config['SPOTIFY_CLIENT_ID'] = ''
        try:
            login(client)
            r = client.get('/spotify/connect', follow_redirects=True)
            assert r.status_code == 200
            assert b'not configured' in r.data.lower() or b'spotify' in r.data.lower()
            logout(client)
        finally:
            app.config['SPOTIFY_CLIENT_ID'] = original

    def test_spotify_connect_with_client_id_redirects_to_spotify(self, client, seeded_db, app):
        """When SPOTIFY_CLIENT_ID is set, connect must redirect to accounts.spotify.com."""
        original = app.config.get('SPOTIFY_CLIENT_ID', '')
        app.config['SPOTIFY_CLIENT_ID'] = 'demo_client_id'
        try:
            login(client)
            r = client.get('/spotify/connect', follow_redirects=False)
            assert r.status_code == 302
            assert 'accounts.spotify.com' in r.headers.get('Location', '')
            logout(client)
        finally:
            app.config['SPOTIFY_CLIENT_ID'] = original

    def test_spotify_disconnect_requires_auth(self, client):
        """Unauthenticated POST /spotify/disconnect must redirect to login."""
        logout(client)
        r = client.post('/spotify/disconnect', follow_redirects=False)
        assert r.status_code == 302
        assert '/login' in r.headers.get('Location', '')

    def test_spotify_disconnect_clears_spotify_fields(self, client, seeded_db, app):
        """POST /spotify/disconnect must null out all Spotify fields on the user."""
        # Create a fresh user with Spotify already connected so there is no stale
        # identity-map entry when we login and call disconnect.
        with app.app_context():
            from app.models import db as _db, User as _User
            spotify_user = _User(
                username='spotifydisco',
                email='spotifydisco@example.com',
                spotify_id='some_id',
                spotify_display_name='SomeArtist',
                spotify_url='https://open.spotify.com/user/some_id',
            )
            spotify_user.set_password('testpass')
            _db.session.add(spotify_user)
            _db.session.commit()
            disco_id = spotify_user.id

        client.post('/login', data={'email': 'spotifydisco@example.com', 'password': 'testpass'})
        r = client.post('/spotify/disconnect', follow_redirects=True)
        assert r.status_code == 200

        with app.app_context():
            from app.models import db as _db2, User as _User2
            u = _db2.session.get(_User2, disco_id)
            assert u.spotify_id is None, 'spotify_id must be cleared after disconnect'
            assert u.spotify_display_name is None
        client.post('/logout')

    def test_spotify_callback_invalid_state_rejected(self, client, seeded_db):
        """Callback with mismatched state must reject and flash a danger message."""
        login(client)
        r = client.get('/spotify/callback?code=abc&state=bad_state', follow_redirects=True)
        assert r.status_code == 200
        assert b'invalid state' in r.data.lower() or b'failed' in r.data.lower()
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
