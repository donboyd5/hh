"""Hubbard Hall board roster, keyed by Neon household rollup id.

One shared roster so every list that treats the board specially (the reception draft drops
them; the campaign-prospect list drops them because Judy's tracker lumps their gifts into a
single "Board Donations" line) stays in step when the board changes.
Values: (role, member name, first name). Board as of 2026-09-15 (Don).
"""
from __future__ import annotations

BOARD_MEMBERS: dict[str, tuple[str, str, str]] = {
    "53": ("Chair", "Don Boyd", "Don"),
    "595": ("Past Chair", "Margaret Surowka", "Margaret"),
    "8": ("Vice Chair", "Sue Sanderson", "Sue"),
    "723": ("Treasurer", "Judy Pate", "Judy"),
    "4488": ("Secretary", "Allie Scoville", "Allie"),
    "58": ("board member", "Terry Dansin", "Terry"),
    "318": ("board member", "Alix Jones", "Alix"),
    "270": ("board member", "Kelvin Keraga", "Kelvin"),
    "1462": ("board member", "Elyssa Macura", "Elyssa"),
    "3": ("Emeritus", "Andrew Pate", "Andrew"),
}
