#!/usr/bin/env python3
"""
compare_r2.py EXPECTED_DIR REPRODUCED_DIR -- verification contract for the
outputs of review_r2.py (tag sweep-v2.1-r2).

Contract (numerical reproduction):
  * .tex and .json outputs (the values printed in the manuscript, and the
    accounting): byte-identical.
  * .csv outputs: identical header, row count, row order and every
    non-numeric field (identifiers, labels, level lists); numeric fields equal
    within rel. tol. 1e-8 and abs. tol. 1e-10. Full-precision floats can differ
    in their last digits between Python/NumPy/SciPy builds; that is not treated
    as a failure.
  * figures (.png): identical decoded pixels. PNG file bytes may differ between
    plotting-library builds and are reported for information only.
Exit status 0 if every output meets the contract, 1 otherwise.
"""
from __future__ import annotations
import csv, math, sys
from pathlib import Path

RTOL, ATOL = 1e-8, 1e-10


def as_float(x):
    try:
        v = float(x)
    except ValueError:
        return None
    return v


def csv_equal(a: Path, b: Path):
    ra = list(csv.reader(open(a, newline="")))
    rb = list(csv.reader(open(b, newline="")))
    if ra[:1] != rb[:1]:
        return False, "header differs"
    if len(ra) != len(rb):
        return False, f"row count {len(ra)} vs {len(rb)}"
    nnum = 0
    for i, (x, y) in enumerate(zip(ra, rb)):
        if len(x) != len(y):
            return False, f"row {i}: field count differs"
        for j, (u, v) in enumerate(zip(x, y)):
            if u == v:
                continue
            fu, fv = as_float(u), as_float(v)
            if fu is None or fv is None:
                return False, f"row {i}, field {ra[0][j]!r}: {u!r} vs {v!r}"
            if math.isnan(fu) and math.isnan(fv):
                continue
            if not math.isclose(fu, fv, rel_tol=RTOL, abs_tol=ATOL):
                return False, f"row {i}, field {ra[0][j]!r}: {u} vs {v} beyond tolerance"
            nnum += 1
    return True, (f"{nnum} numeric fields differ in text only, within tolerance" if nnum else "byte-identical")


def png_equal(a: Path, b: Path):
    import numpy as np
    from matplotlib import image
    pa, pb = image.imread(str(a)), image.imread(str(b))
    same_px = pa.shape == pb.shape and bool(np.array_equal(pa, pb))
    same_bytes = a.read_bytes() == b.read_bytes()
    return same_px, ("identical pixels" + (", identical bytes" if same_bytes else ", PNG bytes differ")) if same_px else "pixels differ"


def main():
    exp, rep = Path(sys.argv[1]), Path(sys.argv[2])
    fail = 0
    for f in sorted(exp.glob("*")):
        if f.is_dir() or f.name == "manifest.sha256":
            continue
        g = rep / f.name
        if not g.exists():
            print(f"MISSING   {f.name}"); fail = 1; continue
        if f.suffix in (".tex", ".json"):
            ok, note = f.read_bytes() == g.read_bytes(), "byte-identical"
            note = note if ok else "bytes differ"
        elif f.suffix == ".csv":
            ok, note = csv_equal(f, g)
        else:
            continue
        print(f"{'ok' if ok else 'FAIL':9} {f.name}: {note}")
        fail |= not ok
    for f in sorted((exp / "figures").glob("*.png")):
        g = rep / "figures" / f.name
        if not g.exists():
            print(f"MISSING   figures/{f.name}"); fail = 1; continue
        ok, note = png_equal(f, g)
        print(f"{'ok' if ok else 'FAIL':9} figures/{f.name}: {note}")
        fail |= not ok
    print("CONTRACT MET: tables and macros byte-identical, CSVs within tolerance, figures pixel-identical"
          if not fail else "CONTRACT NOT MET")
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
