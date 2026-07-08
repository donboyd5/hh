"""Map theater performance events to productions and analyze day-of-run attendance.

Each Neon event is a single performance (one title + date + time). This module groups those
events into productions via a manually curated title-pattern list, splits a title's
performances into runs (a new run starts after a gap of more than RUN_GAP_DAYS), and counts
true headcount: ticket attendees with registrationStatus SUCCEEDED (a registration averages
about two attendees, so registration counts understate headcount).

Events that were not real public performances are excluded before mapping: canceled or moved
dates, test events, open rehearsals, online productions, and weekday 10am school shows.
"""
from __future__ import annotations

import re

import pandas as pd

RUN_GAP_DAYS = 45

# Events that never happened as scheduled or are not regular public performances.
EXCLUDE_PATTERNS = [
    r"TO BE DELETED",
    r"Test Group tickets",
    r"cancel+ed",  # CANCELLED / Cancelled / CANCELED
    r"NOW IN OCTOBER",  # May 2020 dates moved to October
    r"Online Production",
    r"Open Rehearsal",
    r"at 10am",  # weekday school-time shows (Edwin Drood)
]

# Manually curated: every theater performance event name matches exactly one production title.
# Recurring titles (Winter Carnival, Whispering Bones, Bread & Puppet) are split into runs by
# performance-date gaps, not by pattern.
PRODUCTION_PATTERNS = [
    (r"Theater: Ondine", "Ondine"),
    (r"Theater: Parallel Lives", "Parallel Lives"),
    (r"Theater: King Lear", "King Lear"),
    (r"Theater: Of Mice and Men", "Of Mice and Men"),
    (r"25th Annual Putnam County Spelling Bee", "The 25th Annual Putnam County Spelling Bee"),
    (r"Winter Carnival of New Work", "Winter Carnival of New Work"),
    (r"Theater: Tartuffe", "Tartuffe"),
    (r"Theater: An Iliad", "An Iliad"),
    (r"Love's Labour's Lost", "Love's Labour's Lost"),
    (r"Really Rosie", "Really Rosie"),
    (r"The Year of Magical Thinking", "The Year of Magical Thinking"),
    (r"Hubbard Hall Hits", "Hubbard Hall Hits!"),
    (r"Travels With a Masked Man", "Travels With a Masked Man"),
    (r"The Crucible", "The Crucible"),
    (r"^Othello", "Othello"),
    (r"Peter and the Starcatcher", "Peter and the Starcatcher"),
    (r"My Journey to the Center of the Earth", "My Journey to the Center of the Earth"),
    (r"The Book Club Play", "The Book Club Play"),
    (r"The Glass Menagerie", "The Glass Menagerie"),
    (r"Whispering Bones", "Whispering Bones"),
    (r"The Mystery of Edwin Drood", "The Mystery of Edwin Drood"),
    (r"The Tarnation of Russell Colvin", "The Tarnation of Russell Colvin"),
    (r"The Velocity of Autumn", "The Velocity of Autumn"),
    (r"Neo-Futurists", "The New York Neo-Futurists"),
    (r"A Walk in the Woods", "A Walk in the Woods"),
    (r"I Am My Own Wife", "I Am My Own Wife"),
    (r"A Box Of Monkeys", "A Box of Monkeys"),
    (r"HAMLET performed by The Will Kempe Players", "Hamlet (Will Kempe's Players)"),
    (r"Faith Healer", "Faith Healer"),
    (r"Stupid F\*%king Bird", "Stupid F*%king Bird"),
    (r"The Susan B\. Anthony Project", "The Susan B. Anthony Project"),
    (r"All's Well That Ends Well", "All's Well That Ends Well"),
    (r"Much Ado About Nothing", "Much Ado About Nothing (Will Kempe's Players)"),
    (r"As You Like It", "As You Like It (Will Kempe's Players)"),
    (r"My Witch", "My Witch: The Margaret Hamilton Stories"),
    (r"The Wizard of Oz", "The Wizard of Oz (youth)"),
    (r"The Comedy of Errors", "The Comedy of Errors (Will Kempe's Players)"),
    (r"Titus Andronicus", "Titus Andronicus (Will Kempe's Players)"),
    (r"Grant's Ghost", "Grant's Ghost"),
    (r"Fun Home", "Fun Home"),
    (r"The Taming of the Shrew", "The Taming of the Shrew (Will Kempe's Players)"),
    (r"The Two Gentlemen of Verona", "The Two Gentlemen of Verona (Will Kempe's Players)"),
    (r"What The Constitution Means To Me", "What the Constitution Means to Me"),
    (r"Valley Song", "Valley Song"),
    (r"Bread & Puppet Theater", "Bread & Puppet Theater"),
    (r"Dancing at Lughnasa", "Dancing at Lughnasa"),
    (r"Starla & the Stone Angel", "Starla & the Stone Angel"),
    (r"Artists-in-Residence Sharing", "Artists-in-Residence Sharing"),
    (r"Eurydice", "Eurydice"),
    (r"Fefu and Her Friends", "Fefu and Her Friends"),
    (r"Sunday in The Park with George", "Sunday in the Park with George"),
]


def _normalize(name: str) -> str:
    """Straighten typographic quotes/dashes so patterns match plain ASCII."""
    return (
        name.replace("’", "'")
        .replace("‘", "'")
        .replace("“", '"')
        .replace("”", '"')
    )


def is_excluded(event_name: str) -> bool:
    name = _normalize(str(event_name))
    return any(re.search(p, name, re.IGNORECASE) for p in EXCLUDE_PATTERNS)


def match_production(event_name: str) -> str | None:
    """First matching production title, or None if the name matches no pattern."""
    name = _normalize(str(event_name))
    for pattern, title in PRODUCTION_PATTERNS:
        if re.search(pattern, name, re.IGNORECASE):
            return title
    return None


def time_slot(event_name: str) -> str:
    """Classify a performance as matinee (2pm or 'matinee' in the name) or evening."""
    name = _normalize(str(event_name)).lower()
    if re.search(r"\b2(:00)?\s*pm|matinee", name):
        return "matinee"
    return "evening"


def count_succeeded_attendees(tickets) -> int:
    """Headcount for one registration: attendees with registrationStatus SUCCEEDED."""
    if tickets is None:
        return 0
    n = 0
    for ticket in tickets:
        attendees = ticket.get("attendees")
        if attendees is None:
            continue
        n += sum(1 for a in attendees if a.get("registrationStatus") == "SUCCEEDED")
    return n


def theater_performances(regs: pd.DataFrame) -> pd.DataFrame:
    """One row per theater performance: production, run label, date, weekday, attendees.

    Input is the enriched registrations table; output aggregates registrations to the
    performance (event) level, drops excluded events, and labels each performance with its
    production run ("<title> (<year of run's first performance>)").
    """
    theater = regs[
        (regs["event_majorcat"] == "performance") & (regs["event_minorcat"] == "theater")
    ].copy()
    theater = theater[~theater["event_name"].map(is_excluded)]
    theater["production"] = theater["event_name"].map(match_production)
    theater["attendees"] = theater["tickets"].map(count_succeeded_attendees)

    perf = (
        theater.groupby(["production", "swept_event_id", "event_name", "starts_on"], dropna=False)
        .agg(attendees=("attendees", "sum"), registrations=("registration_id", "count"))
        .reset_index()
        .sort_values(["production", "starts_on"])
    )
    perf["weekday"] = perf["starts_on"].dt.day_name()

    # Split each title's performances into runs at gaps > RUN_GAP_DAYS.
    gap = perf.groupby("production")["starts_on"].diff().dt.days
    new_run = (gap.isna() | (gap > RUN_GAP_DAYS)).astype(int)
    perf["run_seq"] = new_run.groupby(perf["production"]).cumsum()
    run_year = perf.groupby(["production", "run_seq"])["starts_on"].transform("min").dt.year
    perf["production_run"] = perf["production"] + " (" + run_year.astype(str) + ")"
    return perf.sort_values("starts_on").reset_index(drop=True)


def full_weekend_runs(perf: pd.DataFrame) -> pd.DataFrame:
    """Performances of production runs that played all three of Friday, Saturday, Sunday."""
    days = perf.groupby("production_run")["weekday"].agg(set)
    qualifying = days[days.map(lambda s: {"Friday", "Saturday", "Sunday"} <= s)].index
    return perf[perf["production_run"].isin(qualifying)].copy()
