"""Tests for the JSON API endpoints: like, save, follow, play, feed, spotify."""
import json
from tests.conftest import login, logout


class TestSpotifyStatusAPI:
    def test_spotify_status_requires_auth(self, client):
        """Unauthenticated request to /api/spotify/status must return 401."""
        logout(client)
        r = client.get('/api/spotify/status')
        assert r.status_code == 401
        data = json.loads(r.data)
        assert 'error' in data

    def test_spotify_status_not_connected_by_default(self, client, seeded_db):
        """A freshly seeded user has no Spotify connection."""
        login(client)
        r = client.get('/api/spotify/status')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['connected'] is False
        assert data['display_name'] == ''
        assert data['spotify_url'] == ''
        logout(client)

    def test_spotify_status_connected_after_db_set(self, client, seeded_db, app):
        """Status reflects True for a user whose spotify_id is set at creation time."""
        with app.app_context():
            from app.models import db as _db, User as _User
            # Create a brand-new user with Spotify already set so there is no stale
            # identity-map entry to work around across context boundaries.
            spotify_user = _User(
                username='spotifytest',
                email='spotifytest@example.com',
                spotify_id='test_id_42',
                spotify_display_name='TestArtist',
                spotify_url='https://open.spotify.com/user/test_id_42',
            )
            spotify_user.set_password('testpass')
            _db.session.add(spotify_user)
            _db.session.commit()

        client.post('/login', data={'email': 'spotifytest@example.com', 'password': 'testpass'})
        r = client.get('/api/spotify/status')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['connected'] is True
        assert data['display_name'] == 'TestArtist'
        assert 'spotify.com' in data['spotify_url']
        client.post('/logout')

    def test_spotify_status_shape(self, client, seeded_db):
        """Response must contain the documented keys regardless of connection state."""
        login(client)
        r = client.get('/api/spotify/status')
        data = json.loads(r.data)
        for key in ('connected', 'display_name', 'spotify_url', 'spotify_artist_url'):
            assert key in data, f'Missing key: {key}'
        logout(client)


class TestSearchAPI:
    def test_search_api_returns_json(self, client):
        r = client.get('/api/search')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'beats' in data
        assert 'producers' in data

    def test_search_api_finds_seeded_beat(self, client, seeded_db):
        r = client.get('/api/search?q=Test')
        assert r.status_code == 200
        data = json.loads(r.data)
        titles = [b['title'] for b in data['beats']]
        assert 'Test Beat' in titles

    def test_search_api_empty_query_returns_empty(self, client):
        r = client.get('/api/search?q=')
        data = json.loads(r.data)
        assert data['beats'] == []
        assert data['producers'] == []


class TestFollowAPI:
    def test_follow_toggle(self, client, seeded_db, app):
        """Follow and unfollow a producer; verify JSON shape and toggled state."""
        # Create a second user to follow — cannot follow self (seeded_db['user_id'])
        with app.app_context():
            from app.models import db as _db, User as _User
            other = _User(username='followtarget', email='followtarget@test.com')
            other.set_password('FollowPass1!')
            _db.session.add(other)
            _db.session.commit()
            other_id = other.id
        assert other_id != seeded_db['user_id'], 'Test user must be different from the follow target'

        login(client)
        r = client.post(f'/api/producers/{other_id}/follow')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'following' in data
        assert 'followers_count' in data
        first_following = data['following']

        r2 = client.post(f'/api/producers/{other_id}/follow')
        data2 = json.loads(r2.data)
        assert data2['following'] != first_following, 'Second call must toggle the follow state'
        logout(client)

    def test_cannot_follow_self(self, client, seeded_db):
        """A user must not be able to follow themselves."""
        login(client)
        user_id = seeded_db['user_id']
        r = client.post(f'/api/producers/{user_id}/follow')
        assert r.status_code == 400, 'Following yourself must return 400'
        logout(client)


class TestUnauthenticatedAPI:
    def test_like_requires_auth(self, client, seeded_db):
        logout(client)
        r = client.post(f'/api/beats/{seeded_db["beat_id"]}/like')
        assert r.status_code == 401
        data = json.loads(r.data)
        assert 'error' in data

    def test_save_requires_auth(self, client, seeded_db):
        logout(client)
        r = client.post(f'/api/beats/{seeded_db["beat_id"]}/save')
        assert r.status_code == 401

    def test_follow_requires_auth(self, client, seeded_db):
        logout(client)
        r = client.post(f'/api/producers/{seeded_db["user_id"]}/follow')
        assert r.status_code == 401


class TestLikeAPI:
    def test_like_toggle(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']

        r = client.post(f'/api/beats/{beat_id}/like')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'liked' in data
        assert 'likes_count' in data
        first_liked = data['liked']

        r2 = client.post(f'/api/beats/{beat_id}/like')
        data2 = json.loads(r2.data)
        assert data2['liked'] != first_liked  # toggled
        logout(client)

    def test_like_missing_beat(self, client, seeded_db):
        login(client)
        r = client.post('/api/beats/999999/like')
        assert r.status_code == 404
        logout(client)


class TestSaveAPI:
    def test_save_toggle(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']

        r = client.post(f'/api/beats/{beat_id}/save')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'saved' in data
        first_saved = data['saved']

        r2 = client.post(f'/api/beats/{beat_id}/save')
        data2 = json.loads(r2.data)
        assert data2['saved'] != first_saved
        logout(client)


class TestPlayAPI:
    def test_play_increments_count(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r = client.post(f'/api/beats/{beat_id}/play')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'play_count' in data
        assert 'counted' in data

    def test_play_deduplication(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r1 = client.post(f'/api/beats/{beat_id}/play')
        r2 = client.post(f'/api/beats/{beat_id}/play')
        d1, d2 = json.loads(r1.data), json.loads(r2.data)
        assert d1['counted'], 'First play must be counted'
        assert not d2['counted'], 'Second play within the dedup window must not be counted'


class TestFeedAPI:
    def test_feed_returns_json(self, client):
        r = client.get('/api/feed')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'beats' in data
        assert 'has_next' in data
        assert 'page' in data

    def test_feed_page_param(self, client):
        r = client.get('/api/feed?page=1')
        assert r.status_code == 200


class TestCommentsAPI:
    def test_get_comments_returns_list(self, client, seeded_db):
        beat_id = seeded_db['beat_id']
        r = client.get(f'/api/beats/{beat_id}/comments')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'comments' in data
        assert isinstance(data['comments'], list)

    def test_post_comment_requires_auth(self, client, seeded_db):
        logout(client)
        r = client.post(f'/api/beats/{seeded_db["beat_id"]}/comments',
                        json={'body': 'test comment'})
        assert r.status_code == 401

    def test_post_comment_creates_and_returns(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']
        r = client.post(f'/api/beats/{beat_id}/comments',
                        json={'body': 'Great beat!'})
        assert r.status_code == 201
        data = json.loads(r.data)
        assert data['body'] == 'Great beat!'
        assert data['beat_id'] == beat_id
        logout(client)

    def test_post_comment_empty_body_rejected(self, client, seeded_db):
        login(client)
        r = client.post(f'/api/beats/{seeded_db["beat_id"]}/comments',
                        json={'body': '   '})
        assert r.status_code == 400
        logout(client)

    def test_post_comment_too_long_rejected(self, client, seeded_db):
        login(client)
        r = client.post(f'/api/beats/{seeded_db["beat_id"]}/comments',
                        json={'body': 'x' * 501})
        assert r.status_code == 400
        logout(client)

    def test_like_comment_requires_auth(self, client, seeded_db):
        # Post a comment first so we have an ID to test against
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Like target'})
        comment_id = json.loads(rc.data)['id']
        logout(client)

        r = client.post(f'/api/comments/{comment_id}/like')
        assert r.status_code == 401

    def test_like_comment_toggle(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Like me'})
        comment_id = json.loads(rc.data)['id']

        r = client.post(f'/api/comments/{comment_id}/like')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert 'liked' in data
        assert 'likes_count' in data
        logout(client)

    def test_delete_comment_requires_auth(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Delete me'})
        comment_id = json.loads(rc.data)['id']
        logout(client)

        r = client.delete(f'/api/comments/{comment_id}')
        assert r.status_code == 401

    def test_delete_comment_by_author(self, client, seeded_db):
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Temporary'})
        comment_id = json.loads(rc.data)['id']

        r = client.delete(f'/api/comments/{comment_id}')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['deleted'] is True
        logout(client)

    def test_delete_comment_by_non_author_forbidden(self, client, seeded_db, app):
        """A logged-in user who is NOT the comment author must receive 403."""
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Owner comment'})
        comment_id = json.loads(rc.data)['id']
        logout(client)

        # Register + login as a different user, then attempt the delete
        client.post('/register', data={
            'username': 'attacker99', 'email': 'attacker99@test.com',
            'password': 'AttackPass1!', 'confirm_password': 'AttackPass1!',
        })
        client.post('/login', data={'email': 'attacker99@test.com', 'password': 'AttackPass1!'})
        r = client.delete(f'/api/comments/{comment_id}')
        assert r.status_code == 403, 'Non-author must not be allowed to delete another user\'s comment'
        data = json.loads(r.data)
        assert 'error' in data
        logout(client)

    def test_dislike_comment_toggle(self, client, seeded_db):
        """Dislike a comment, verify count increments; dislike again, verify it toggles off."""
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Dislike me'})
        comment_id = json.loads(rc.data)['id']

        r = client.post(f'/api/comments/{comment_id}/dislike')
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['disliked'] is True
        assert data['dislikes_count'] == 1

        r2 = client.post(f'/api/comments/{comment_id}/dislike')
        data2 = json.loads(r2.data)
        assert data2['disliked'] is False, 'Second dislike must toggle off'
        assert data2['dislikes_count'] == 0
        logout(client)

    def test_dislike_removes_existing_like(self, client, seeded_db):
        """Disliking a previously liked comment must remove the like (mutually exclusive)."""
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Like then dislike'})
        comment_id = json.loads(rc.data)['id']

        client.post(f'/api/comments/{comment_id}/like')
        r = client.post(f'/api/comments/{comment_id}/dislike')
        data = json.loads(r.data)
        assert data['disliked'] is True
        assert data['likes_count'] == 0, 'Like must be removed when dislike is applied'
        logout(client)

    def test_report_and_unreport_round_trip(self, client, seeded_db):
        """Reporting a comment increments count; un-reporting decrements it back."""
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Report target'})
        comment_id = json.loads(rc.data)['id']

        r = client.post(f'/api/comments/{comment_id}/report', json={'reason': 'spam'})
        assert r.status_code == 200
        data = json.loads(r.data)
        assert data['reported'] is True
        assert data['report_count'] == 1

        # Duplicate report must return 409
        r_dup = client.post(f'/api/comments/{comment_id}/report', json={'reason': 'spam'})
        assert r_dup.status_code == 409

        # Un-report must decrement back to 0
        r_del = client.delete(f'/api/comments/{comment_id}/report')
        assert r_del.status_code == 200
        data_del = json.loads(r_del.data)
        assert data_del['reported'] is False
        logout(client)

    def test_reply_to_reply_rejected(self, client, seeded_db):
        """Posting a reply to an existing reply must return 400 — one level deep only."""
        login(client)
        beat_id = seeded_db['beat_id']
        rc = client.post(f'/api/beats/{beat_id}/comments', json={'body': 'Top-level'})
        parent_id = json.loads(rc.data)['id']

        rc2 = client.post(f'/api/beats/{beat_id}/comments',
                          json={'body': 'First reply', 'parent_id': parent_id})
        reply_id = json.loads(rc2.data)['id']

        r = client.post(f'/api/beats/{beat_id}/comments',
                        json={'body': 'Nested reply', 'parent_id': reply_id})
        assert r.status_code == 400, 'Reply to a reply must be rejected'
        logout(client)
