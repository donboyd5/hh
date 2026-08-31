"""Major event category: performance / class / community / other — Hubbard Hall's own scheme.

History: the first Python cut was a faithful port of the R project's rules
(``R_hhfrc/get_convert_and_save_data.qmd``). As of 2026-08-31 we own the rules: still
informed by R's decisions (especially the youth-program exceptions), but written for our
data, case-insensitive, and robust to Neon's category-name quirks.

Principles, in evaluation order (first match wins):

1. **Neon's own ``category`` field is the primary signal.** Category strings are
   normalized (casefolded, internal whitespace collapsed) before matching — Neon values
   arrive with irregular spacing ("Bollywood  Dance" has a double space).
2. **Youth-program showcases and recitals are CLASSES**, even when Neon files them under
   a performance category: a Teen Theatre camp's ticketed performances are the camp's
   product, not mainstage programming (R made the same call via its exception lists).
3. **Ticketed public programming — including film screenings — is PERFORMANCE.** R filed
   film under community; we treat a screening people buy tickets to as a performance.
   Exhibits and lectures stay community.
4. **Community gatherings are COMMUNITY** — breakfasts, dinners, forums, garden tours,
   exhibits and lectures, plus fundraising events whose name says community.
5. **Galas, fundraisers, auditions, and uncategorized miscellany are OTHER** — except
   fundraisers that are essentially concerts (Brews & Blues, the cabaret fundraisers),
   which are performance.
6. **Anything that matches no rule returns ``"ERROR"``** — a deliberate tripwire so new
   event types surface instead of hiding. The goal is that only test records ever land
   there; after the 2026-08-31 rewrite the known real categories (Bollywood dance,
   fencing) are covered.
"""
from __future__ import annotations

import re

from ._match import contains_any, present

# ---- normalisation --------------------------------------------------------------
# Neon category values carry irregular casing and spacing ("Bollywood  Dance",
# "Weekly Classes"); names carry stray capitals. Everything matches on the normalized form.
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", s.strip().casefold())


# ---- rule data ------------------------------------------------------------------
# Specific past events (mostly with no Neon category) that R classified by exact name.
EXACT_PERFORMANCE_NAMES = [
    _norm(n)
    for n in [
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
]
# Fundraiser names that are concerts first (principle 5's exception).
CONCERT_PERFORMANCE_PATTERNS = ["brews & blues", "blues & brews", "a christmas carol"]

# Principle 2: youth-program showcases and recitals. Substring match on the name; applies
# whatever the Neon category says (they usually sit under a performance category).
YOUTH_SHOWCASE_PATTERNS = [
    "dance mob", "dance showcase", "dance ceili", "irish ceili", "russian tea",
    "young dancer", "drama club", "teen theater", "teen theatre",
    "youth theater", "youth theatre", "youth chorale", "teen showcase",
]

# Principle 4: community by name (covers fundraising events that are community parties).
COMMUNITY_NAME_PATTERNS = ["community", "garden tour", "holiday breakfast"]

# Principle 5: galas by name.
GALA_NAME_PATTERNS = ["gala"]

# Neon category -> major. Keys are normalized; look up with _norm(category).
PERFORMANCE_CATS = {
    "performances",
    "theater performances",
    "music performances",
    "music from salem performances",
    "opera performances",
    "shakespeare",
    "dance performances",
    "film screenings",  # our call (principle 3); R filed these under community
}
CLASS_CATS = {
    "weekly classes",
    "ballet",
    "pilates/yoga",
    "irish step dance",
    "visual arts",
    "visual arts - crafts",
    "children's theater",
    "theater/acting classes",
    "children's art classes",
    "fitness & movement classes",
    "martial arts",
    "martial arts karate",
    "tap dance",
    "hip hop",
    "music classes",
    "dance classes - contemporary",
    "dance workshops",
    "bollywood dance",  # Neon's spelling has a double space; _norm collapses it
    "bollywood & bollyx",  # the label Neon used in earlier years
    "sword fencing",  # both were ERROR before the 2026-08-31 rewrite
    "foil fencing",
    "puppetry",
    "chorale",
    "wellness",
}
CLASS_CAT_SUBSTRINGS = ["classes", "workshops", "martial arts", "fencing"]
COMMUNITY_CATS = {
    "community events",
    "curiosity forum",
    "dinners",
    "exhibits, films & lectures",
    "home & garden",
    "literary",
}
OTHER_CATS = {"auditions", "fundraising events", "special events"}

# Events with no Neon category at all: a few known class patterns (R's rules, kept).
CLASS_NAME_PATTERNS_NA = ["drama club", "yoga"]
CLASS_NAME_PATTERNS_NA_BOTH = ["teen", "showcase"]  # class when BOTH appear


def assign_major(category, event_name) -> str:
    """Return the major event category (performance / class / community / other / ERROR)."""
    cat = _norm(present(category) or "")
    name = _norm(present(event_name) or "")

    # known events and concert-shaped fundraisers -> performance (whatever the category)
    if name in EXACT_PERFORMANCE_NAMES:
        return "performance"
    if contains_any(name, CONCERT_PERFORMANCE_PATTERNS):
        return "performance"

    # Neon's category decides; the one override is principle 2 — a youth-program
    # showcase or recital filed under a performance category is a class
    if cat in PERFORMANCE_CATS:
        if contains_any(name, YOUTH_SHOWCASE_PATTERNS):
            return "class"
        return "performance"
    if cat in CLASS_CATS or contains_any(cat, CLASS_CAT_SUBSTRINGS):
        return "class"
    if cat in COMMUNITY_CATS:
        return "community"

    # community by name — the fallback for fundraising/special events that are
    # community parties ("... Community ..."); a class or performance category
    # has already been handled above
    if contains_any(name, COMMUNITY_NAME_PATTERNS):
        return "community"

    if cat in OTHER_CATS:
        return "other"

    # no category: the few known class patterns, else other
    if cat == "" and (
        contains_any(name, CLASS_NAME_PATTERNS_NA)
        or all(contains_any(name, [p]) for p in CLASS_NAME_PATTERNS_NA_BOTH)
    ):
        return "class"
    if cat == "":
        return "other"

    # galas by name — only for categories that matched nothing above
    if contains_any(name, GALA_NAME_PATTERNS):
        return "other"

    return "ERROR"
