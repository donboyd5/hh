import pandas as pd

from hh.categorize import add_major_minor, assign_major, assign_minor, categorize_event

# (category, event_name, expected_major)
MAJOR_CASES = [
    # exact-name list (mostly past events with no Neon category)
    (None, "Whispering Bones", "performance"),
    ("Mystery Category", "Whispering Bones", "performance"),  # exact name wins
    # concert-shaped fundraisers are performances (principle 5's exception)
    ("Fundraising Events", "Brews & Blues Night", "performance"),
    (None, "A Christmas Carol", "performance"),
    # performance categories
    ("Performances", "Hamlet", "performance"),
    ("Theater Performances", "Hamlet", "performance"),
    ("Music Performances", "Symphony", "performance"),
    ("Shakespeare", "x", "performance"),
    ("Opera Performances", "x", "performance"),
    ("Dance Performances", "The Nutcracker", "performance"),
    # our call (principle 3): a screening people buy tickets to is a performance
    ("Film Screenings", "Manhattan Short Film Festival", "performance"),
    # principle 2: youth-program showcases are classes, in any performance category
    ("Performances", "Dance Mob", "class"),
    ("Performances", "Playing Shakespeare - Teen Theater Showcase", "class"),
    ("Theater Performances", "Teen Theatre Spring", "class"),
    ("Music Performances", "Hubbard Hall Youth Chorale Spring Sing", "class"),
    ("Dance Performances", "Young Dancer Recital", "class"),
    ("Dance Performances", "Dance Showcase", "class"),
    # class categories — including the two that were ERROR before the 2026-08-31 rewrite
    ("Classes", "x", "class"),
    ("Weekly Classes", "x", "class"),
    ("Ballet", "x", "class"),
    ("Bollywood  Dance", "x", "class"),  # Neon's double-space spelling; _norm collapses
    ("Bollywood & BollyX", "x", "class"),
    ("Sword Fencing", "x", "class"),
    ("Martial Arts Karate", "x", "class"),
    ("Workshops - Children", "x", "class"),  # substring families cover future labels
    ("Pottery Classes", "x", "class"),
    ("Children's Theater", "x", "class"),
    # community
    ("Community Events", "x", "community"),
    ("Dinners", "x", "community"),
    ("Exhibits, Films & Lectures", "x", "community"),  # exhibits/lectures stay community
    ("Home & Garden", "x", "community"),
    ("Fundraising Events", "Community Potluck Fundraiser", "community"),  # name fallback
    (None, "Holiday Breakfast With Santa", "community"),
    # other
    ("Fundraising Events", "Spring Fundraiser", "other"),
    ("Auditions", "x", "other"),
    ("Special Events", "x", "other"),
    (None, "Random Unmatched Event", "other"),  # no category -> other
    (None, "Morning Yoga", "class"),  # no category + known class pattern
    (None, "Teen Showcase Night", "class"),  # no category + teen AND showcase
    ("Mystery Category", "Annual Gala", "other"),  # unknown category + gala name
    ("Mystery Category", "Plain Name", "ERROR"),  # tripwire
]


def test_assign_major():
    for category, name, expected in MAJOR_CASES:
        got = assign_major(category, name)
        assert got == expected, f"{category!r}/{name!r} -> {got!r}, expected {expected!r}"


def test_assign_major_is_case_insensitive():
    assert assign_major("FUNDRAISING EVENTS", "ANNUAL GALA") == "other"
    assert assign_major("music performances", "spring sing") == "performance"


# (category, event_name, major, expected_minor)
MINOR_CASES = [
    ("Dance Performances", "x", "performance", "dance"),
    (None, "Swan Dance", "performance", "dance"),  # case-insensitive Dance in name
    ("Music Performances", "x", "performance", "music"),
    (None, "music from salem listening", "performance", "music"),  # case-insensitive
    (None, "Cabaret Night", "performance", "music"),  # case-sensitive Cabaret
    (None, "cabaret night", "performance", "other"),  # lowercase -> NOT matched (case-sensitive)
    ("Theater Performances", "x", "performance", "theater"),
    (None, "The Crucible", "performance", "theater"),
    ("Opera Performances", "x", "performance", "opera"),
    (None, "An Opera House", "performance", "opera"),
    (None, "mystery show", "performance", "other"),
    (None, "x", "class", "other"),  # non-performance -> other
]


def test_assign_minor():
    for category, name, major, expected in MINOR_CASES:
        got = assign_minor(category, name, major)
        assert got == expected, f"{category!r}/{name!r}/{major!r} -> {got!r}, expected {expected!r}"


def test_categorize_event_theater():
    major, minor = categorize_event("Theater Performances", "Hamlet")
    assert (major, minor) == ("performance", "theater")


def test_add_major_minor_adds_columns():
    df = pd.DataFrame(
        {
            "category": ["Theater Performances", "Ballet", None, "Theater Performances"],
            "event_name": ["Hamlet", "Tap", "Teen Showcase", "The Crucible"],
        }
    )
    out = add_major_minor(df)
    assert list(out["event_majorcat"]) == ["performance", "class", "class", "performance"]
    assert list(out["event_minorcat"]) == ["theater", "other", "other", "theater"]
    # original df unchanged
    assert "event_majorcat" not in df.columns
