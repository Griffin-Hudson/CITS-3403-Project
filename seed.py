"""
TuneFeed — Sample database seeder.
Run from the project root:  python seed.py

Creates sample producers, beats, likes,
comments, and replies so every feed feature can be tested immediately.
Drops and recreates all tables on each run.
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timedelta
import random

from app import create_app
from app.models import db, User, Beat, Like, Comment, Transaction
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
        "bio": "Producer.",
        "avatar_url": "https://api.dicebear.com/9.x/avataaars/svg?seed=producedbykyle",
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
}

BEATS = [
    # (title, prod, genre, bpm, key, mood, dur, licence, lease, premium, excl, plays, trending, days_ago)

    # ── ProducedByU — Trap ───────────────────────────────────────────────────
    ("DRIVER",    0, "Trap", 130, "C# Min", "dark,melodic,cinematic",            "3:00", "Non-exclusive",  24.99,  59.99, 229.99,   10, True,   1),
    ("THE CITY",  0, "Trap", 126, "C# Min", "atmospheric,smooth,moody",          "3:10", "Non-exclusive",  22.99,  54.99, 219.99,    8, False,  3),
    ("POISON",    0, "Trap", 136, "C# Min", "eerie,emotional,melodic",           "2:50", "Non-exclusive",  24.99,  64.99, 249.99,    9, False,  2),
    ("ENEMY",     0, "Trap", 126, "G Min",  "rage,aggressive,distorted,energetic","3:05", "Non-exclusive",  19.99,  49.99, 199.99,    7, False,  5),

    # ── ProducedByKyle — (beats coming) ──────────────────────────────────────

    # ── Swayy — Dancehall ────────────────────────────────────────────────────
    ("Don't Be Shy",   2, "Dancehall",  98, "Bb Min", "dancehall,smooth,melodic",     "3:10", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Reflection",     2, "Dancehall", 100, "G# Min", "tropical,emotional,melodic",   "3:15", "Non-exclusive",  18.99,  44.99, 179.99,    7, False,  4),
    ("Psyched",        2, "Dancehall", 140, "A Min",  "psychedelic,atmospheric,melodic","3:00","Non-exclusive", 22.99,  54.99, 219.99,    8, False,  3),
    ("ROLLERCOASTER",  2, "Dancehall", 137, "B Min",  "energetic,bouncy,uplifting",   "2:55", "Non-exclusive",  19.99,  49.99, 199.99,   10, True,   2),

    # ── VocaVoice — Vocal Sample ─────────────────────────────────────────────
    ("IN THE RAIN",       3, "Trap",    154, "G Min",  "emotional,vocal sample,cinematic",   "3:05", "Non-exclusive",  24.99,  59.99, 229.99,   10, True,   1),
    ("Angels Singing",    3, "R&B",     106, "F# Min", "soulful,uplifting,melodic",          "3:20", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("Feelings",          3, "Soul",     96, "F Min",  "sad,emotional,minimal",              "2:45", "Non-exclusive",  16.99,  39.99, 159.99,    7, False,  6),
    ("ABUNDANT IN MERCY", 3, "Gospel",  140, "F# Min", "gospel,soulful,uplifting,cinematic", "3:15", "Non-exclusive",  22.99,  54.99, 219.99,    9, False,  2),

    # ── TenTens — Afrobeat ───────────────────────────────────────────────────
    ("Don't Worry",     4, "Afrobeat",  104, "Gb Maj", "chill,uplifting,smooth,atmospheric",  "3:20", "Non-exclusive",  18.99,  44.99, 179.99,   10, False,  2),
    ("Me & You",        4, "Afrobeat",   98, "F Min",  "chill,emotional,melodic,nocturnal",   "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    7, False,  5),
    ("Rosas",           4, "Afrobeat",   96, "G Min",  "chill,tropical,smooth,warm",          "3:25", "Non-exclusive",  19.99,  44.99, 179.99,    8, False,  4),
    ("All My Trust",    4, "Afrobeat",  128, "C Min",  "energetic,rhythmic,melodic,vibrant",  "3:10", "Non-exclusive",  22.99,  54.99, 219.99,   11, True,   1),

    # ── Jazzzed — Jazz / Boom Bap ────────────────────────────────────────────
    ("Chemistry",   5, "Jazz",     123, "Eb Min", "chill,jazzy,smooth",            "3:10", "Non-exclusive",  19.99,  49.99, 199.99,    9, False,  2),
    ("CALL ME",     5, "Jazz",      98, "F# Min", "nostalgic,soulful,retro",       "2:55", "Non-exclusive",  18.99,  44.99, 179.99,    7, False,  4),
    ("BALANCE",     5, "Boom Bap",  87, "G Min",  "boom bap,jazzy,laid-back",      "3:00", "Non-exclusive",  17.99,  44.99, 179.99,    8, True,   1),
    ("Shy2",        5, "Jazz",     132, "C# Min", "melodic,atmospheric,smooth",    "2:50", "Non-exclusive",  22.99,  54.99, 219.99,    6, False,  5),

    # ── FakeTech — Electronic ────────────────────────────────────────────────
    ("Boombox",   6, "Electronic", 195, "F# Min", "aggressive,bass-heavy,club",       "2:50", "Non-exclusive",  24.99,  59.99, 229.99,    8, False,  2),
    ("Spin",      6, "Electronic", 104, "F Min",  "dark,rhythmic,bounce",              "3:05", "Non-exclusive",  19.99,  49.99, 199.99,    6, False,  5),
    ("Jasmine",   6, "Electronic", 105, "F# Min", "melodic,atmospheric,hypnotic",     "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Camomile",  6, "Electronic", 118, "G# Min", "dreamy,nostalgic,atmospheric",     "3:20", "Non-exclusive",  22.99,  54.99, 219.99,    7, False,  4),

    # ── YoungTiller — R&B ────────────────────────────────────────────────────
    ("In My Head",   7, "R&B",  98, "F Min",  "late night,melodic,smooth,atmospheric",  "3:20", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("One Night",    7, "R&B",  90, "F# Min", "smooth,atmospheric,nocturnal,emotional", "3:10", "Non-exclusive",  17.99,  44.99, 179.99,    6, False,  6),
    ("Mind Games",   7, "R&B", 135, "Bb Min", "dark,emotional,melodic,moody",           "2:55", "Non-exclusive",  22.99,  54.99, 219.99,    9, True,   2),
    ("I Know",       7, "R&B",  80, "Gb Min", "slow,intimate,moody,ambient",            "3:30", "Premium Lease",  19.99,  49.99, 199.99,    5, False,  8),

    # ── DaysNoTrace — Alternative Rock ───────────────────────────────────────
    ("No More Pain",              8, "Alternative Rock", 195, "F# Min", "alternative rock,emotional,aggressive,intense",   "3:00", "Non-exclusive",  24.99,  64.99, 249.99,    6, False,  3),
    ("Unbroken",                  8, "Alternative Rock", 130, "C Min",  "alternative rock,sad,emotional,dark",             "3:15", "Non-exclusive",  19.99,  49.99, 199.99,    9, True,   1),
    ("Too Late",                  8, "Alternative Rock", 148, "C Min",  "alternative rock,melancholic,heavy,emotional",    "2:55", "Non-exclusive",  22.99,  54.99, 219.99,    7, False,  4),
    ("Leave Me",                  8, "Alternative Rock", 140, "A Min",  "alternative rock,sad,emotional,dark",             "3:10", "Non-exclusive",  17.99,  44.99, 179.99,    5, False,  6),

    # ── VelvetPeril — Indie Rock ─────────────────────────────────────────────
    ("Last Summer",          9, "Indie Rock", 114, "B Min",  "indie rock,melancholic,guitar,emotional",    "3:30", "Non-exclusive",  19.99,  49.99, 199.99,    8, False,  3),
    ("Summer Girl",          9, "Indie Rock", 163, "Ab Min", "indie rock,upbeat,emotional,summer vibe",    "2:58", "Non-exclusive",  19.99,  49.99, 199.99,   10, True,   2),
    ("Overdue",              9, "Indie Rock", 176, "Eb Maj", "indie rock,fast tempo,emotional,atmospheric","3:05", "Non-exclusive",  22.99,  59.99, 229.99,    7, False,  4),
    ("Endings",              9, "Indie Rock", 171, "D Min",  "indie rock,cinematic,emotional,ambient",     "3:20", "Non-exclusive",  17.99,  44.99, 179.99,    5, False,  6),
]

# ---------------------------------------------------------------------------
# Sample comments and replies — tests the full comment system
# ---------------------------------------------------------------------------

COMMENTS = [
    # (beat_title, author_username, body, replies: [(username, body)])
    ("DRIVER", "DemoUser", "The C# Minor on this is haunting. Absolute cinema production 🎬",
     [("ProducedByU", "Appreciate it, that's exactly the energy 🙏"),
      ("FakeTech",      "Bro the mix on this is crazy clean")]),
    ("Chemistry", "DemoUser", "This is exactly the late night study energy I needed. Pure jazz magic 🎷",
     [("Jazzzed", "Glad it hit right, that's the vibe 🙏"),
      ("ProducedByU", "The sample flip on this is cold")]),
    ("IN THE RAIN", "YoungTiller", "The vocal chops on this are insane. Emotional and cinematic at the same time",
     [("VocaVoice", "That's everything I was going for 🎤"),
      ("DemoUser",  "Been on repeat all morning no cap")]),
    ("Don't Be Shy", "DemoUser", "This dancehall energy is infectious. Smooth and melodic 🌴",
     [("Swayy",        "Appreciate that, more vibes coming 🙏"),
      ("TenTens",      "The groove on this is unreal")]),
    ("Leave Me", "DaysNoTrace", "Rock on! Finally some raw emotional guitar-driven beats on here",
     [("Swayy",    "Different lane but I respect the energy 💪"),
      ("DemoUser", "This goes hard in the whip no cap")]),
    ("Jasmine", "TenTens", "Put this on at a house party last week, the floor went CRAZY",
     [("FakeTech", "That's what I make it for 🔊 let's collab sometime")]),
    ("Don't Worry", "DemoUser", "Pure vibes all day, this is exactly what I needed 🌊",
     [("TenTens", "Means everything, glad it hit right 🙏"),
      ("ProducedByKyle", "The atmosphere on this is incredible")]),
    ("In My Head", "ProducedByU", "Trap soul production is next level on this. Emotional and hard at the same time",
     [("YoungTiller", "That's exactly the sound I was chasing 🎧"),
      ("DemoUser",    "Been on repeat since yesterday no cap")]),
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
        # role='producer' here mirrors the upgrade routes.py performs on first upload —
        # without it, seeded producers would still look like plain listeners.
        producer_objs = []
        for p in PRODUCERS:
            u = User(
                username=p["username"],
                email=p["email"],
                bio=p["bio"],
                avatar_url=p["avatar_url"],
                role='producer',
            )
            u.set_password(p["password"])
            db.session.add(u)
            producer_objs.append(u)

        db.session.flush()  # assigns IDs before creating beats

        # ── Create beats ──
        beat_map = {}  # title → Beat object (for linking comments)
        for row in BEATS:
            (title, prod_idx, genre, bpm, key, mood_tag,
             duration, licence, price, premium_price, exclusive_price,
             plays, is_trending, days_ago) = row

            # Spread upload dates across the last month for algorithm freshness testing
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

        # ── Seed likes — spread across beats and users so algorithm has signal ──
        all_users = [demo] + producer_objs
        max_plays = max(b.play_count for b in beat_map.values()) or 1
        for beat in beat_map.values():
            # Scale like probability 0.10–0.70 relative to the most-played beat
            # so popular beats still receive proportionally more likes.
            like_rate = 0.10 + (beat.play_count / max_plays) * 0.60
            for user in all_users:
                if user.id != beat.producer_id and random.random() < like_rate:
                    db.session.add(Like(user_id=user.id, beat_id=beat.id))

        db.session.flush()

        # ── Seed follows — create a social graph ──
        for i, producer in enumerate(producer_objs):
            # Each producer follows 3 other producers
            others = [p for j, p in enumerate(producer_objs) if j != i]
            for followed in random.sample(others, min(3, len(others))):
                producer.follow(followed)
            # Demo user follows everyone
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

        # ── Seed wallet activity ──
        # Demo listener: a couple of top-ups so the wallet page has activity to show.
        for amount, days_ago in [(50, 12), (25, 5), (100, 1)]:
            tx = top_up(demo, amount, note='Card ending 4242')
            tx.created_at = now - timedelta(days=days_ago, hours=random.randint(0, 23))

        # Producers: a handful of synthetic sales each so the studio page is meaningful.
        # We only seed earnings for a subset of beats per producer to keep numbers varied.
        for producer in producer_objs:
            producer_beats = [b for b in beat_map.values() if b.producer_id == producer.id]
            if not producer_beats:
                continue
            for beat in random.sample(producer_beats, min(len(producer_beats), 3)):
                # 1-4 sales per featured beat at the beat's lease price
                for _ in range(random.randint(1, 4)):
                    tx = record_earning(producer, beat.price,
                                        note=f'Sale: {beat.title}')
                    tx.created_at = now - timedelta(days=random.randint(0, 25),
                                                    hours=random.randint(0, 23))

        db.session.commit()

        print("\nDatabase seeded successfully!")
        print("\n   Demo accounts:")
        print("   demo@tunefeed.io             / password123  (listener)")
        print("   prodbyu@tunefeed.io          / password123  (ProducedByU)")
        print("   producedbykyle@tunefeed.io   / password123  (ProducedByKyle)")
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
