#!/usr/bin/env python3
"""Verify that every file path the manuscript names exists in the archive.

Usage:
  python3 sweep/check_manuscript_paths.py <main.tex> [--zip <archive.zip>]

Without --zip, paths are checked against the current repository tree (run
from the repository root). With --zip, they are checked against the entry
list of a `git archive` zip (any single leading prefix directory is
stripped), which is how the release gate uses it: the manuscript must name
no file that the published deposit does not contain.

Detection rule: every \\texttt{...} token in the .tex that looks like a file
or directory path (contains a dot-extension or a slash), after undoing the
LaTeX escapes \\_ and \\%. Bare script names such as `foo.py` are resolved by
basename anywhere in the tree, because the manuscript may cite a script
without its directory; paths containing a slash must match exactly.
Exit status 1 if any named path is missing.
"""
import re
import sys
import zipfile
from pathlib import Path

EXT = re.compile(r"\.(py|csv|tex|txt|md|json|sh|png|jsonl|cff)$")


def named_paths(tex_text):
    out = set()
    for tok in re.findall(r"\\texttt\{([^}]*)\}", tex_text):
        s = tok.replace("\\_", "_").replace("\\%", "%").strip()
        if re.fullmatch(r"table_\w+", s):      # generated table inputs cited
            s = s + ".tex"                       # without their extension
        if "/" in s or EXT.search(s):
            if s.endswith("/"):
                s = s.rstrip("/")
            out.add(s)
    return sorted(out)


def tree_entries(root):
    root = Path(root)
    return {str(p.relative_to(root)).replace("\\", "/")
            for p in root.rglob("*")}


def zip_entries(zpath):
    names = zipfile.ZipFile(zpath).namelist()
    prefix = None
    if names and "/" in names[0]:
        first = names[0].split("/")[0]
        if all(n.startswith(first + "/") for n in names):
            prefix = first + "/"
    out = set()
    for n in names:
        n = n[len(prefix):] if prefix else n
        n = n.rstrip("/")
        if n:
            out.add(n)
    return out


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    tex = Path(argv[1]).read_text(errors="replace")
    entries = (zip_entries(argv[argv.index("--zip") + 1]) if "--zip" in argv
               else tree_entries("."))
    basenames = {e.rsplit("/", 1)[-1] for e in entries}
    missing = []
    for p in named_paths(tex):
        found = (p in entries) if "/" in p else (p in basenames or p in entries)
        print(("OK      " if found else "MISSING ") + p)
        if not found:
            missing.append(p)
    print(f"\n{len(missing)} missing of {len(named_paths(tex))} named paths")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
