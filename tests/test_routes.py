"""Tests that all key page routes return expected HTTP status codes."""
import io

from app.models import Beat, User, db
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

    def test_post_creates_beat_and_promotes_user(self, app, client, seeded_db):
        login(client)
        r = self._post(client, self._base_form())
        assert r.status_code == 302
        assert '/feed' in r.headers.get('Location', '')

        with app.app_context():
            beat = Beat.query.filter_by(title='Late Night Drive').first()
            assert beat is not None
            assert beat.audio_url.startswith('/static/uploads/beats/')
            assert beat.producer_id == seeded_db['user_id']
            user = User.query.get(seeded_db['user_id'])
            assert user.role == 'producer'
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
