"""Find mailing addresses for Fort Salem sponsors not in Neon, from public assessment data.

Sources (all local under data/00_raw/external/assessment/, downloaded by hand/curl):
  2026/<Town>.txt            Washington County NY 2026 final rolls (pdftotext -layout)
  rensselaer2026/<Town>.txt  Rensselaer County NY 2026 final rolls (Hoosick)
  vermont/vt_parcels_border_towns.parquet   VCGI standardized parcels, 30 border towns

Writes data/10_interim/fst_contacts.parquet — the best hit per kept Fort Salem name with a
confidence label — which scripts/export_mailing_list.py folds into the mailing list.
Web-research notes live in data/30_external/fst-contact-notes.yaml (hand/AI maintained).

Usage: python scripts/research_fst_contacts.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from hh import config, io
from hh.external.assessment import load_rolls, match_names_to_owners, vt_parcels_as_rolls

ASSESS = config.layer_dir("raw") / "external" / "assessment"


def main() -> None:
    table = io.read_parquet("processed", "mailing_list.parquet")
    names = table.loc[table["needs_review"], ["household_name", "fst_best_tier", "fst_years"]]

    frames = []
    for folder, label in [(ASSESS / "2026", "Washington County NY 2026 roll"),
                          (ASSESS / "rensselaer2026", "Rensselaer County NY 2026 roll")]:
        if folder.exists():
            r = load_rolls(folder)
            r["source"] = label
            frames.append(r)
    vt_path = ASSESS / "vermont" / "vt_parcels_border_towns.parquet"
    if vt_path.exists():
        frames.append(vt_parcels_as_rolls(pd.read_parquet(vt_path)))
    parcels = pd.concat(frames, ignore_index=True)
    print(f"parcels: {len(parcels):,} from {parcels['source'].nunique()} sources")

    hits = match_names_to_owners(names, parcels)
    hits["confidence"] = pd.cut(hits["given_agreement"], [0, 90, 100.1], right=False,
                                labels=["probable", "strong"]).astype(str)
    hits = hits.rename(columns={"name": "household_name"})
    io.write_parquet(hits, "interim", "fst_contacts.parquet")
    top = hits.drop_duplicates("household_name")
    print(f"names with an address: {len(top)} of {len(names)} "
          f"(strong {int((top['confidence'] == 'strong').sum())}, probable "
          f"{int((top['confidence'] == 'probable').sum())})")
    unmatched = names[~names["household_name"].isin(top["household_name"])]
    print(f"unmatched: {len(unmatched)}")
    Path(config.layer_dir("interim") / "fst_contacts_unmatched.csv").write_text(
        unmatched.to_csv(index=False)
    )


if __name__ == "__main__":
    main()
