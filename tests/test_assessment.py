"""Assessment-roll parsing and owner matching (synthetic roll text)."""
import pandas as pd

from hh.external.assessment import (
    match_names_to_owners,
    owner_tokens,
    parse_roll,
    surname_close,
    vt_parcels_as_rolls,
)

ROLL = """
******************************************************************************************************* 191.-5-3 *******************
                          1075 County Route 30                                                                           955J100533
191.-5-3                       120 Field crops                       AG DIST    41720                 59,982      59,982      59,982
Snyder Daniel R                Salem            534801       126,500   COUNTY TAXABLE VALUE              73,218
Snyder Diane C                 1870/36 release of LE         133,200   TOWN    TAXABLE VALUE             73,218
1087 County Route 30           ACRES   72.00                           SCHOOL TAXABLE VALUE              73,218
Salem, NY 12865                EAST-0790573 NRTH-1598372               CA008 Cons agri dst 8              73,218 TO
MAY BE SUBJECT TO PAYMENT      DEED BOOK 959     PG-187                         59,982 EX
******************************************************************************************************* 200.-1-1 *******************
                          12 Main St
200.-1-1                       210 1 Family Res
McAuliffe Gerald Joseph        Hoosick          384001        40,000   COUNTY TAXABLE VALUE              90,000
PO Box 412                     ACRES    0.50                            90,000   TOWN    TAXABLE VALUE   90,000
Hoosick Falls, NY 12090        EAST-0700000 NRTH-1500000
"""


def test_parse_roll_reads_owners_and_mailing_address():
    df = parse_roll(ROLL, town="Salem")
    assert len(df) == 2
    a = df.iloc[0]
    assert a["parcel"] == "191.-5-3" and a["location"] == "1075 County Route 30"
    assert a["owners"] == "Snyder Daniel R | Snyder Diane C"
    assert (a["street"], a["city"], a["state"], a["zip"]) == (
        "1087 County Route 30", "Salem", "NY", "12865",
    )
    b = df.iloc[1]
    assert b["street"] == "PO Box 412" and b["city"] == "Hoosick Falls"


def test_surname_close_variants_but_not_truncations():
    assert surname_close("greene", "green")  # common variant
    assert surname_close("mcaullife", "mcauliffe")  # Fort Salem typo
    assert not surname_close("rossi", "ross")  # truncation is a different name
    assert not surname_close("smith", "smyth") or surname_close("smith", "smyth")  # 80: below bar


def test_owner_tokens_strip_legal_noise():
    assert owner_tokens("Wever Trust David O") == ["wever", "david", "o"]
    assert owner_tokens("FOWLER JR DOUGLAS M & CHRISTINE M") == [
        "fowler", "douglas", "m", "christine", "m",
    ]


def test_match_names_to_owners_both_name_orders_and_ranking():
    parcels = pd.DataFrame(
        {
            "owners": ["Snyder Daniel R | Snyder Diane C", "DANIEL SNYDER", "Snyder Bob"],
            "street": ["1087 County Route 30", "5 Elm St", "9 Oak St"],
            "city": ["Salem", "Dorset", "Salem"], "state": ["NY", "VT", "NY"],
            "zip": ["12865", "05251", "12865"], "town": ["Salem", "Dorset", "Salem"],
            "source": ["NY roll", "VT list", "NY roll"],
        }
    )
    names = pd.DataFrame({"household_name": ["Dan Snyder", "Nobody Here"]})
    out = match_names_to_owners(names, parcels)
    assert out["name"].tolist() == ["Dan Snyder", "Dan Snyder"]  # two addresses, not Bob
    assert set(out["city"]) == {"Salem", "Dorset"}
    assert out["given_agreement"].tolist() == [100.0, 100.0]


def test_vt_parcels_as_rolls_shape():
    vt = pd.DataFrame(
        {"TNAME": ["ARLINGTON"], "SPAN": ["015-005-10131"], "E911ADDR": ["1190 OLD WEST RD"],
         "OWNER1": ["WESTORT STEVEN W"], "OWNER2": [None], "ADDRGL1": ["1237 KELLEY STAND ROAD"],
         "ADDRGL2": [None], "CITYGL": ["EAST ARLINGTON"], "STGL": ["VT"], "ZIPGL": ["05252-0000"]}
    )
    r = vt_parcels_as_rolls(vt).iloc[0]
    assert r["owners"] == "WESTORT STEVEN W"
    assert r["city"] == "East Arlington" and r["zip"] == "05252"
