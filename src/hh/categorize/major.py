"""Major event category: performance / class / community / other.

Faithful port of ``R_hhfrc/get_convert_and_save_data.qmd`` lines 496-665. Rules are evaluated in
order; the first match wins (R ``case_when``). Events matching no rule return ``"ERROR"`` — a
deliberate tripwire so uncategorized events surface rather than hide.

All substring matching here is case-SENSITIVE, matching R's default ``str_detect`` / ``fixed()``
(the R patterns contain no regex metacharacters, so regex == literal substring).
"""
from __future__ import annotations

from ._match import contains_any, present

PERFORMANCE_NAMES = [
    "2nd Annual Hubbard Hall-oween Celebration (2016)",
    "An Unforgettable Crooner Cabaret",
    "Hubbard Hall-oween Celebration",
    "Hubbard Hall-O-Ween Monster Mash Ball; 7pm",
    "Hubbard Halloween Ball - Saturday, October 26th, 2019 at 6pm",
    "Miscast Cabaret -- Fundraiser",
    "Music From Salem Listening Club: Music About Nature",
    "Night of Duets Cabaret -- Fundraiser",
    "Songs for Scholarships Cabaret - Saturday July 28th at 7pm",
    "Special Event: A Day at the Opera, August 15",
    "TriBeCaStan: In Concert!",
    "Whispering Bones",
]
PERFORMANCE_PATTERNS = ["Brews & Blues", "Blues & Brews", "A Christmas Carol"]
PERFORMANCE_CATS = [
    "Music Performances",
    "Music from Salem Performances",
    "Opera Performances",
    "Shakespeare",
]
CLASS_EXCEPTIONS_PERFORMANCE = ["Dance Mob"]
CLASS_EXCEPTIONS_DANCE = [
    "Dance Ceili",
    "Dance Mob",
    "Dance Showcase",
    "Irish Ceili",
    "Russian Tea",
    "Young Dancer",
]
CLASS_EXCEPTIONS_THEATER = [
    "Drama Club",
    "Teen Theater",
    "Teen Theatre",
    "Youth Chorale",
    "Youth Theater",
    "Youth Theatre",
]
CLASS_CATS = [
    "Classes",
    "Ballet",
    "Bollywood & BollyX",
    "Dance Workshops",
    "Foil Fencing",
    "Hip Hop",
    "Irish Step Dance",
    "Pilates/Yoga",
    "Puppetry",
    "Tap Dance",
    "Visual Arts",
    "Visual Arts - Crafts",
    "Wellness",
    "Workshops",
]
CLASS_CATEGORY_SUBSTRINGS = ["Classes", "Martial Arts", "Workshops"]
COMMUNITY_CATS = [
    "Community Events",
    "Curiosity Forum",
    "Dinners",
    "Exhibits, Films & Lectures",
    "Film Screenings",
    "Home & Garden",
    "Literary",
]
COMMUNITY_PATTERNS = ["Community", "Garden Tour", "Holiday Breakfast"]
OTHER_CATS = ["Auditions", "Fundraising Events", "Special Events"]
CLASS_PATTERNS_NA = ["Drama Club", "Yoga"]


def assign_major(category, event_name) -> str:
    """Return the major event category for one event."""
    cat = present(category)
    name = present(event_name) or ""

    # ---- PERFORMANCE ----
    if name in PERFORMANCE_NAMES:
        return "performance"
    if contains_any(name, PERFORMANCE_PATTERNS):
        return "performance"
    if cat == "Performances" and not contains_any(name, CLASS_EXCEPTIONS_PERFORMANCE):
        return "performance"
    if cat == "Dance Performances" and not contains_any(name, CLASS_EXCEPTIONS_DANCE):
        return "performance"
    if cat == "Theater Performances" and not contains_any(name, CLASS_EXCEPTIONS_THEATER):
        return "performance"
    if cat in PERFORMANCE_CATS:
        return "performance"

    # ---- CLASS ----
    if cat == "Performances" and contains_any(name, CLASS_EXCEPTIONS_PERFORMANCE):
        return "class"
    if cat == "Dance Performances" and contains_any(name, CLASS_EXCEPTIONS_DANCE):
        return "class"
    if cat == "Theater Performances" and contains_any(name, CLASS_EXCEPTIONS_THEATER):
        return "class"
    if cat in CLASS_CATS:
        return "class"
    if contains_any(cat, CLASS_CATEGORY_SUBSTRINGS):
        return "class"
    if cat == "Children's Theater":
        return "class"
    if cat == "Chorale":
        return "class"
    if cat is None and contains_any(name, CLASS_PATTERNS_NA):
        return "class"
    if cat is None and "Teen" in name and "Showcase" in name:
        return "class"

    # ---- COMMUNITY ----
    if cat in COMMUNITY_CATS:
        return "community"
    if contains_any(name, COMMUNITY_PATTERNS):
        return "community"

    # ---- OTHER ----
    if cat in OTHER_CATS or cat is None:
        return "other"
    if "Gala" in name:
        return "other"

    return "ERROR"
