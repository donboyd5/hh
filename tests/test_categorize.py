import pandas as pd

from hh.categorize import add_major_minor, assign_major, assign_minor, categorize_event

# (category, event_name, expected_major)
MAJOR_CASES = [
    (None, "Whispering Bones", "performance"),  # exact-name rule
    ("Performances", "Hamlet", "performance"),
    ("Performances", "Dance Mob", "class"),  # class exception overrides performance category
    ("Dance Performances", "The Nutcracker", "performance"),
    ("Dance Performances", "Young Dancer Recital", "class"),  # dance exception
    ("Theater Performances", "Hamlet", "performance"),
    ("Theater Performances", "Teen Theater Spring", "class"),  # theater exception
    ("Music Performances", "Symphony", "performance"),
    ("Shakespeare", "x", "performance"),
    ("Opera Performances", "x", "performance"),
    ("Ballet", "x", "class"),
    ("Tap Dance", "x", "class"),
    ("Pilates/Yoga", "x", "class"),
    ("Martial Arts", "x", "class"),  # category substring rule
    ("Children's Theater", "x", "class"),
    ("Chorale", "x", "class"),
    (None, "Morning Yoga", "class"),  # NA category + class_patterns_na
    (None, "Teen Showcase Night", "class"),  # NA + Teen & Showcase
    ("Community Events", "x", "community"),
    ("Home & Garden", "x", "community"),
    (None, "Holiday Breakfast With Santa", "community"),  # community pattern in name
    ("Fundraising Events", "x", "other"),
    ("Auditions", "x", "other"),
    (None, "Random Unmatched Event", "other"),  # NA -> other
    ("Mystery Category", "Spring Gala", "other"),  # Gala in name
    ("Mystery Category", "Plain Name", "ERROR"),  # tripwire
]


def test_assign_major():
    for category, name, expected in MAJOR_CASES:
        got = assign_major(category, name)
        assert got == expected, f"{category!r}/{name!r} -> {got!r}, expected {expected!r}"


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
