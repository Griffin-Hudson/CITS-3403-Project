"""
TuneFeed — Sample database seeder.
Run from the project root:  python seed.py

Creates sample producers, beats, likes,
comments, and replies so every feed feature can be tested immediately.
Drops and recreates all tables on each run.

MP3 beats in this seeder are purely for demonstration purposes.
Each file was hand-selected from producers who explicitly listed their
work as free-to-use. Proper licensing and royalty infrastructure are
identified as a future priority — see README for details.

ProducedByKyle's beats (WAV) are unreleased originals shared personally
by the artist for use in this project. Kyle is a Spotify-verified
professional producer who granted explicit permission for TuneFeed
to feature his work as a demonstration of the platform's capabilities.
This is a genuine commercial-grade producer endorsement, not stock audio.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import random

from app import create_app
from app.models import db, User, Beat, Like, Comment
from app.services.wallet_service import top_up, record_earning

random.seed(42)

# ---------------------------------------------------------------------------
# Producer accounts
# ---------------------------------------------------------------------------

PRODUCERS = [
    {
        "username": "ProducedByU",
        "email": "prodbyu@tunefeed.io",
        "password": "password123",
        "bio": "Trap & Dark Hip-Hop producer. Cinematic soundscapes, eerie melodies, and hard-hitting 808s.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=prodbyu",
    },
    {
        "username": "ProducedByKyle",
        "email": "producedbykyle@tunefeed.io",
        "password": "password123",
        "bio": "Boom Bap & Hip-Hop producer. Dusty samples, hard-hitting drums, and timeless sound. Available on Spotify.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=producedbykyle",
        # ProducedByKyle is a Spotify-verified professional producer who granted
        # explicit permission for TuneFeed to feature his unreleased beats.
        # Artist page: https://open.spotify.com/artist/34KLV4fA8n6XZyFrWs9iRx
        "spotify_id":           "34KLV4fA8n6XZyFrWs9iRx",
        "spotify_display_name": "ProducedByKyle",
        "spotify_url":          "https://open.spotify.com/artist/34KLV4fA8n6XZyFrWs9iRx",
        "spotify_artist_url":   "https://open.spotify.com/artist/34KLV4fA8n6XZyFrWs9iRx",
    },
    {
        "username": "Swayy",
        "email": "swayy@tunefeed.io",
        "password": "password123",
        "bio": "Dancehall & Tropical producer. Smooth melodies, bouncy rhythms, and feel-good energy.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=swayy",
    },
    {
        "username": "VocaVoice",
        "email": "vocavoice@tunefeed.io",
        "password": "password123",
        "bio": "Vocal sample producer. Chopped voices, flipped melodies, and soulful textures that breathe.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=vocavoice",
    },
    {
        "username": "TenTens",
        "email": "tentens@tunefeed.io",
        "password": "password123",
        "bio": "Afrobeat producer. Warm rhythms, breezy melodies, and sun-soaked vibes inspired by the continent's finest.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=tentens",
    },
    {
        "username": "Jazzzed",
        "email": "jazzzed@tunefeed.io",
        "password": "password123",
        "bio": "Jazz, boom-bap & soul. Dusty samples, smooth keys, and crate-digger energy.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=jazzzed",
    },
    {
        "username": "FakeTech",
        "email": "faketech@tunefeed.io",
        "password": "password123",
        "bio": "Electronic & Club producer. Heavy bass, hypnotic loops, and floor-shaking rhythms.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=faketech",
    },
    {
        "username": "YoungTiller",
        "email": "youngtiller@tunefeed.io",
        "password": "password123",
        "bio": "R&B & Trap Soul producer. Late-night melodies, moody atmospheres, and raw emotion.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=youngtiller",
    },
    {
        "username": "DaysNoTrace",
        "email": "daystrace@tunefeed.io",
        "password": "password123",
        "bio": "Alternative rock & emo producer. Heavy guitars, dark melodies, and raw emotion.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=daystrace",
    },
    {
        "username": "VelvetPeril",
        "email": "velvet@tunefeed.io",
        "password": "password123",
        "bio": "Indie rock & alternative producer. Guitar-driven instrumentals with raw emotional depth.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=velvet",
    },
]

# Demo listener account for testing interactions
DEMO_USER = {
    "username": "DemoUser",
    "email": "demo@tunefeed.io",
    "password": "password123",
    "bio": "Just here to discover fire beats.",
    "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=demo",
}

# ---------------------------------------------------------------------------
# Beat catalogue
# (title, prod_idx, genre, bpm, key, mood_tag, duration, licence,
#  lease_price, premium_price, exclusive_price, plays, is_trending, days_ago)
# ---------------------------------------------------------------------------

# Maps every beat title to its local static MP3 path in app/static/audio/
AUDIO_PATHS = {
    "Last Summer":                              "/static/audio/last_summer.mp3",
    "Summer Girl":                              "/static/audio/summer_girl.mp3",
    "Overdue":                                  "/static/audio/overdue.mp3",
    "Endings":                                  "/static/audio/endings.mp3",
    "No More Pain":                             "/static/audio/no_more_pain.mp3",
    "Unbroken":                                 "/static/audio/unbroken.mp3",
    "Too Late":                                 "/static/audio/too_late.mp3",
    "Leave Me":                                 "/static/audio/leave_me.mp3",
    "Don't Worry":                              "/static/audio/dont_worry.mp3",
    "Me & You":                                 "/static/audio/me_and_you.mp3",
    "Rosas":                                    "/static/audio/rosas.mp3",
    "All My Trust":                             "/static/audio/all_my_trust.mp3",
    "In My Head":                               "/static/audio/in_my_head.mp3",
    "One Night":                                "/static/audio/one_night.mp3",
    "Mind Games":                               "/static/audio/mind_games.mp3",
    "I Know":                                   "/static/audio/i_know.mp3",
    "Boombox":                                  "/static/audio/boombox.mp3",
    "Spin":                                     "/static/audio/spin.mp3",
    "Jasmine":                                  "/static/audio/jasmine.mp3",
    "Camomile":                                 "/static/audio/camomile.mp3",
    "DRIVER":                                   "/static/audio/driver.mp3",
    "THE CITY":                                 "/static/audio/the_city.mp3",
    "POISON":                                   "/static/audio/poison.mp3",
    "ENEMY":                                    "/static/audio/enemy.mp3",
    "Chemistry":                                "/static/audio/chemistry.mp3",
    "CALL ME":                                  "/static/audio/call_me.mp3",
    "BALANCE":                                  "/static/audio/balance.mp3",
    "Shy2":                                     "/static/audio/shy2.mp3",
    "IN THE RAIN":                              "/static/audio/in_the_rain.mp3",
    "Angels Singing":                           "/static/audio/angels_singing.mp3",
    "Feelings":                                 "/static/audio/feelings.mp3",
    "ABUNDANT IN MERCY":                        "/static/audio/abundant_in_mercy.mp3",
    "Don't Be Shy":                             "/static/audio/dont_be_shy.mp3",
    "Reflection":                               "/static/audio/reflection.mp3",
    "Psyched":                                  "/static/audio/psyched.mp3",
    "ROLLERCOASTER":                            "/static/audio/rollercoaster.mp3",

    # ProducedByKyle — unreleased originals shared personally for this project (WAV)
    "Escargot":                                  "/static/audio/escargot.wav",
    "Reverse Layup":                             "/static/audio/reverse_layup.wav",
    "Unknown":                                   "/static/audio/unknown.wav",
    "Word Magicc":                               "/static/audio/word_magicc.wav",
    "No Danger":                                 "/static/audio/no_danger.wav",
    "Sandro Jova":                               "/static/audio/sandro_jova.wav",
}

BEATS = [
    # (title, prod, genre, bpm, key, mood, dur, licence, lease, premium, excl, plays, trending, days_ago)

    # ── ProducedByU — Trap ───────────────────────────────────────────────────
    ("DRIVER",    0, "Trap", 130, "C# Min", "dark,melodic,cinematic",             "3:00", "Non-exclusive",  24.99,  59.99, 229.99,   10, True,   1),
    ("THE CITY",  0, "Trap", 126, "C# Min", "atmospheric,smooth,moody",           "3:10", "Non-exclusive",  22.99,  54.99, 219.99,    8, False,  3),
    ("POISON",    0, "Trap", 136, "C# Min", "eerie,emotional,melodic",            "2:50", "Non-exclusive",  24.99,  64.99, 249.99,    9, False,  2),
    ("ENEMY",     0, "Trap", 126, "G Min",  "rage,aggressive,energetic",          "3:05", "Non-exclusive",  19.99,  49.99, 199.99,    7, False,  5),

    # ── ProducedByKyle — Boom Bap (unreleased originals, WAV) ────────────────
    ("Escargot",     1, "Boom Bap",  88, "B Min",  "dusty,soulful,melodic",         "2:55", "Non-exclusive",  22.99,  54.99, 219.99,    8, True,   1),
    ("Reverse Layup",1, "Boom Bap",  90, "G Min",  "raw,energetic,boom bap",        "3:00", "Non-exclusive",  19.99,  49.99, 199.99,    6, False,  3),
    ("Unknown",      1, "Boom Bap",  80, "Ab Min", "atmospheric,dark,boom bap",     "2:45", "Non-exclusive",  17.99,  44.99, 179.99,    7, False,  5),
    ("Word Magicc",  1, "Boom Bap",  65, "C Min",  "slow,melodic,boom bap",         "3:10", "Non-exclusive",  22.99,  54.99, 219.99,    5, False,  6),
    ("No Danger",    1, "Boom Bap",  84, "D Min",  "smooth,laid-back,boom bap",     "2:50", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   2),
    ("Sandro Jova",  1, "Boom Bap",  85, "F Min",  "sample-driven,classic,boom bap","3:05", "Non-exclusive",  17.99,  44.99, 179.99,    6, False,  4),

    # ── Swayy — Dancehall ────────────────────────────────────────────────────
    ("Don't Be Shy",   2, "Dancehall",  98, "Bb Min", "dancehall,smooth,melodic",      "3:10", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Reflection",     2, "Dancehall", 100, "G# Min", "tropical,emotional,melodic",    "3:15", "Non-exclusive",  18.99,  44.99, 179.99,    7, False,  4),
    ("Psyched",        2, "Dancehall", 140, "A Min",  "psychedelic,atmospheric,melodic","3:00","Non-exclusive",  22.99,  54.99, 219.99,    8, False,  3),
    ("ROLLERCOASTER",  2, "Dancehall", 137, "B Min",  "energetic,bouncy,uplifting",    "2:55", "Non-exclusive",  19.99,  49.99, 199.99,   10, True,   2),

    # ── VocaVoice — Vocal Sample ─────────────────────────────────────────────
    ("IN THE RAIN",       3, "Trap",    154, "G Min",  "emotional,vocal sample,cinematic",   "3:05", "Non-exclusive",  24.99,  59.99, 229.99,   10, True,   1),
    ("Angels Singing",    3, "R&B",     106, "F# Min", "soulful,uplifting,melodic",          "3:20", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("Feelings",          3, "Soul",     96, "F Min",  "sad,emotional,minimal",              "2:45", "Non-exclusive",  16.99,  39.99, 159.99,    7, False,  6),
    ("ABUNDANT IN MERCY", 3, "Gospel",  140, "F# Min", "soulful,uplifting,cinematic",         "3:15", "Non-exclusive",  22.99,  54.99, 219.99,    9, False,  2),

    # ── TenTens — Afrobeat ───────────────────────────────────────────────────
    ("Don't Worry",     4, "Afrobeat",  104, "Gb Maj", "chill,uplifting,atmospheric",  "3:20", "Non-exclusive",  18.99,  44.99, 179.99,   10, False,  2),
    ("Me & You",        4, "Afrobeat",   98, "F Min",  "chill,emotional,nocturnal",    "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    7, False,  5),
    ("Rosas",           4, "Afrobeat",   96, "G Min",  "chill,tropical,warm",          "3:25", "Non-exclusive",  19.99,  44.99, 179.99,    8, False,  4),
    ("All My Trust",    4, "Afrobeat",  128, "C Min",  "energetic,rhythmic,vibrant",   "3:10", "Non-exclusive",  22.99,  54.99, 219.99,   11, True,   1),

    # ── Jazzzed — Jazz / Boom Bap ────────────────────────────────────────────
    ("Chemistry",   5, "Jazz",     123, "Eb Min", "chill,jazzy,smooth",         "3:10", "Non-exclusive",  19.99,  49.99, 199.99,    9, False,  2),
    ("CALL ME",     5, "Jazz",      98, "F# Min", "nostalgic,soulful,retro",    "2:55", "Non-exclusive",  18.99,  44.99, 179.99,    7, False,  4),
    ("BALANCE",     5, "Boom Bap",  87, "G Min",  "boom bap,jazzy,laid-back",   "3:00", "Non-exclusive",  17.99,  44.99, 179.99,    8, True,   1),
    ("Shy2",        5, "Jazz",     132, "C# Min", "melodic,atmospheric,smooth", "2:50", "Non-exclusive",  22.99,  54.99, 219.99,    6, False,  5),

    # ── FakeTech — Electronic ────────────────────────────────────────────────
    ("Boombox",   6, "Electronic", 195, "F# Min", "aggressive,bass-heavy,club",    "2:50", "Non-exclusive",  24.99,  59.99, 229.99,    8, False,  2),
    ("Spin",      6, "Electronic", 104, "F Min",  "dark,rhythmic,bounce",          "3:05", "Non-exclusive",  19.99,  49.99, 199.99,    6, False,  5),
    ("Jasmine",   6, "Electronic", 105, "F# Min", "melodic,atmospheric,hypnotic",  "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Camomile",  6, "Electronic", 118, "G# Min", "dreamy,nostalgic,atmospheric",  "3:20", "Non-exclusive",  22.99,  54.99, 219.99,    7, False,  4),

    # ── YoungTiller — R&B ────────────────────────────────────────────────────
    ("In My Head",   7, "R&B",  98, "F Min",  "late night,smooth,atmospheric",          "3:20", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("One Night",    7, "R&B",  90, "F# Min", "atmospheric,nocturnal,emotional",        "3:10", "Non-exclusive",  17.99,  44.99, 179.99,    6, False,  6),
    ("Mind Games",   7, "R&B", 135, "Bb Min", "dark,emotional,moody",                   "2:55", "Non-exclusive",  22.99,  54.99, 219.99,    9, True,   2),
    ("I Know",       7, "R&B",  80, "Gb Min", "intimate,moody,ambient",                 "3:30", "Premium Lease",  19.99,  49.99, 199.99,    5, False,  8),

    # ── DaysNoTrace — Alternative Rock ───────────────────────────────────────
    ("No More Pain",      8, "Alternative Rock", 195, "F# Min", "emotional,aggressive,intense",   "3:00", "Non-exclusive",  24.99,  64.99, 249.99,    6, False,  3),
    ("Unbroken",          8, "Alternative Rock", 130, "C Min",  "sad,emotional,dark",             "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Too Late",          8, "Alternative Rock", 148, "C Min",  "melancholic,heavy,emotional",    "2:55", "Non-exclusive",  22.99,  54.99, 219.99,    7, False,  4),
    ("Leave Me",          8, "Alternative Rock", 140, "A Min",  "sad,emotional,dark",             "3:10", "Non-exclusive",  17.99,  44.99, 179.99,    5, False,  6),

    # ── VelvetPeril — Indie Rock ─────────────────────────────────────────────
    ("Last Summer",  9, "Indie Rock", 114, "B Min",  "melancholic,guitar,emotional",   "3:30", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("Summer Girl",  9, "Indie Rock", 163, "Ab Min", "upbeat,emotional,summer vibe",  "2:58", "Non-exclusive",  19.99,  49.99, 199.99,   10, True,   2),
    ("Overdue",      9, "Indie Rock", 176, "Eb Maj", "driven,emotional,atmospheric",  "3:05", "Non-exclusive",  22.99,  59.99, 229.99,    7, False,  4),
    ("Endings",      9, "Indie Rock", 171, "D Min",  "cinematic,emotional,ambient",   "3:20", "Non-exclusive",  17.99,  44.99, 179.99,    5, False,  6),
]

# ---------------------------------------------------------------------------
# Sample comments and replies
# ---------------------------------------------------------------------------

COMMENTS = [
    ("DRIVER", "DemoUser", "The C# Minor on this is haunting. Absolute cinema production 🎬",
     [("ProducedByU", "Appreciate it, that's exactly the energy 🙏"),
      ("FakeTech",    "Bro the mix on this is crazy clean")]),
    ("Chemistry", "DemoUser", "This is exactly the late night study energy I needed. Pure jazz magic 🎷",
     [("Jazzzed",     "Glad it hit right, that's the vibe 🙏"),
      ("ProducedByU", "The sample flip on this is cold")]),
    ("IN THE RAIN", "YoungTiller", "The vocal chops on this are insane. Emotional and cinematic at the same time",
     [("VocaVoice", "That's everything I was going for 🎤"),
      ("DemoUser",  "Been on repeat all morning no cap")]),
    ("Don't Be Shy", "DemoUser", "This dancehall energy is infectious. Smooth and melodic 🌴",
     [("Swayy",   "Appreciate that, more vibes coming 🙏"),
      ("TenTens", "The groove on this is unreal")]),
    ("Leave Me", "DaysNoTrace", "Rock on! Finally some raw emotional guitar-driven beats on here",
     [("Swayy",    "Different lane but I respect the energy 💪"),
      ("DemoUser", "This goes hard in the whip no cap")]),
    ("Jasmine", "TenTens", "Put this on at a house party last week, the floor went CRAZY",
     [("FakeTech", "That's what I make it for 🔊 let's collab sometime")]),
    ("Don't Worry", "DemoUser", "Pure vibes all day, this is exactly what I needed 🌊",
     [("TenTens",       "Means everything, glad it hit right 🙏"),
      ("ProducedByKyle","The atmosphere on this is incredible")]),
    ("In My Head", "ProducedByU", "Trap soul production is next level on this. Emotional and hard at the same time",
     [("YoungTiller", "That's exactly the sound I was chasing 🎧"),
      ("DemoUser",    "Been on repeat since yesterday no cap")]),
    ("Escargot", "DemoUser", "This boom bap is too clean. That B Minor melody is haunting 🎯",
     [("ProducedByKyle", "Appreciate it 🙏 more originals dropping soon"),
      ("Jazzzed",        "The drum pattern on this is exactly how it should be done")]),
    ("No Danger", "Jazzzed", "Smooth as it gets. That D Minor key choice is doing something special",
     [("ProducedByKyle", "Glad you caught that — that was a deliberate choice"),
      ("DemoUser",       "Been bumping this on every drive this week no cap")]),
]


# ---------------------------------------------------------------------------
# Seed function
# ---------------------------------------------------------------------------

def seed():
    app = create_app()
    with app.app_context():
        print("Dropping and recreating all tables...")
        db.drop_all()
        db.create_all()

        now = datetime.utcnow()

        # ── Create demo listener ──
        demo = User(
            username=DEMO_USER["username"],
            email=DEMO_USER["email"],
            bio=DEMO_USER["bio"],
            avatar_url=DEMO_USER["avatar_url"],
        )
        demo.set_password(DEMO_USER["password"])
        db.session.add(demo)

        # ── Create producers ──
        producer_objs = []
        for p in PRODUCERS:
            u = User(
                username=p["username"],
                email=p["email"],
                bio=p["bio"],
                avatar_url=p["avatar_url"],
                spotify_id=p.get("spotify_id"),
                spotify_display_name=p.get("spotify_display_name"),
                spotify_url=p.get("spotify_url"),
                spotify_artist_url=p.get("spotify_artist_url"),
            )
            u.set_password(p["password"])
            db.session.add(u)
            producer_objs.append(u)

        db.session.flush()

        # ── Create beats ──
        beat_map = {}
        for row in BEATS:
            (title, prod_idx, genre, bpm, key, mood_tag,
             duration, licence, price, premium_price, exclusive_price,
             plays, is_trending, days_ago) = row

            uploaded = now - timedelta(days=days_ago, hours=random.randint(0, 23))
            audio_url = AUDIO_PATHS[title]

            beat = Beat(
                title=title,
                genre=genre,
                bpm=bpm,
                key=key,
                mood_tag=mood_tag,
                duration=duration,
                licence_type=licence,
                price=price,
                premium_price=premium_price,
                exclusive_price=exclusive_price,
                play_count=plays,
                is_trending=is_trending,
                uploaded_at=uploaded,
                producer_id=producer_objs[prod_idx].id,
                audio_url=audio_url,
            )
            db.session.add(beat)
            beat_map[title] = beat

        db.session.flush()

        # ── Seed likes ──
        all_users = [demo] + producer_objs
        max_plays = max(b.play_count for b in beat_map.values()) or 1
        for beat in beat_map.values():
            like_rate = 0.10 + (beat.play_count / max_plays) * 0.60
            for user in all_users:
                if user.id != beat.producer_id and random.random() < like_rate:
                    db.session.add(Like(user_id=user.id, beat_id=beat.id))

        db.session.flush()

        # ── Seed follows ──
        for i, producer in enumerate(producer_objs):
            others = [p for j, p in enumerate(producer_objs) if j != i]
            for followed in random.sample(others, min(3, len(others))):
                producer.follow(followed)
            demo.follow(producer)

        db.session.flush()

        # ── Seed comments and replies ──
        for (beat_title, commenter_name, body, replies) in COMMENTS:
            beat = beat_map.get(beat_title)
            commenter = User.query.filter_by(username=commenter_name).first()
            if not beat or not commenter:
                continue

            parent_comment = Comment(
                beat_id=beat.id,
                author_id=commenter.id,
                body=body,
                created_at=now - timedelta(hours=random.randint(1, 72)),
            )
            db.session.add(parent_comment)
            db.session.flush()

            for (reply_username, reply_body) in replies:
                reply_author = User.query.filter_by(username=reply_username).first()
                if not reply_author:
                    continue
                reply = Comment(
                    beat_id=beat.id,
                    author_id=reply_author.id,
                    parent_id=parent_comment.id,
                    body=reply_body,
                    created_at=now - timedelta(hours=random.randint(0, 48)),
                )
                db.session.add(reply)

        # ── Seed wallet activity so demo wallet/studio pages arent empty ──
        top_up(demo, 50.0, note='Welcome credit')
        for producer in producer_objs:
            record_earning(producer, round(random.uniform(15, 80), 2), note='Sample sale')

        db.session.commit()

        print("\nDatabase seeded successfully!")
        print("\n   Demo accounts:")
        print("   demo@tunefeed.io             / password123  (listener)")
        print("   prodbyu@tunefeed.io          / password123  (ProducedByU)")
        print("   producedbykyle@tunefeed.io   / password123  (ProducedByKyle — Spotify Verified)")
        print("   swayy@tunefeed.io            / password123  (Swayy)")
        print("   vocavoice@tunefeed.io        / password123  (VocaVoice)")
        print("   tentens@tunefeed.io          / password123  (TenTens)")
        print("   jazzzed@tunefeed.io          / password123  (Jazzzed)")
        print("   faketech@tunefeed.io         / password123  (FakeTech)")
        print("   youngtiller@tunefeed.io      / password123  (YoungTiller)")
        print("   daystrace@tunefeed.io        / password123  (DaysNoTrace)")
        print("   velvet@tunefeed.io           / password123  (VelvetPeril)")
        print(f"\n   {len(BEATS)} beats across {len(set(b[2] for b in BEATS))} genres")
        print(f"   Likes, follows, and comments seeded for algorithm testing\n")


if __name__ == '__main__':
    seed()
