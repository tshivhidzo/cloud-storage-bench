#!/usr/bin/env bash
# release_v21.sh <reserved-zenodo-doi> -- build the sweep-v2.1 release in the
# git clone, with gates, and produce the byte-literal Zenodo deposit.
#
#   cd ~/publish/cloud-storage-bench-thesis-v1
#   ./scripts/release_v21.sh 10.5281/zenodo.NNNNNNNN
#
# Steps (stops at the first failed gate):
#   1. copy the release files from the OneDrive working copy into the clone
#   2. fill in the reserved DOI and today's date
#   3. gates: no credentials, data/output manifests verify, results reproduce
#   4. show the change summary and ask before committing
#   5. commit, annotated tag sweep-v2.1, push main and the tag
#   6. TZ=Africa/Johannesburg git archive -> sweep-v2.1-<sha>.zip + SHA-256
set -euo pipefail

DOI="${1:-}"
[[ "$DOI" =~ ^10\.5281/zenodo\.[0-9]+$ ]] || { echo "usage: $0 10.5281/zenodo.NNNNNNNN (the DOI reserved in the Zenodo draft)"; exit 2; }
ONE="${ONE:-/c/Users/Tshivhidzo/OneDrive - Cape Peninsula University of Technology/Thesis/2026/cloud-storage-bench}"
TAG=sweep-v2.1
TODAY=$(date +%F)
cd "$(git rev-parse --show-toplevel)"
say(){ printf '\n== %s\n' "$*"; }
die(){ printf 'STOP: %s\n' "$*"; exit 1; }

git diff --quiet && git diff --cached --quiet || die "the clone has uncommitted changes; commit or stash them first"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"
git pull --ff-only origin main

say "1. copying release files from OneDrive"
for d in results-rerun-v21 v21-output paper-v21; do
  rm -rf "$d"; cp -r "$ONE/$d" "$d"; echo "   $d/"
done
# README and VERIFICATION_GUIDE: the OneDrive copies add one block each; refuse
# if the clone has other changes that the OneDrive copy would overwrite
strip_block() {   # print file $1 without the sweep-v2.1 block
  case "$1" in
    README.md) awk '/^## Release sweep-v2.1/{skip=1} /^## Start here/{skip=0} !skip' "$2" ;;
    VERIFICATION_GUIDE.md) awk 'NR>1 && /^> /{prev=$0; next} NR>1 && prev ~ /^> / && /^$/{prev=$0; next} {print; prev=$0}' "$2" ;;
  esac
}
for f in README.md VERIFICATION_GUIDE.md; do
  if ! diff -q <(strip_block "$f" "$ONE/$f") <(strip_block "$f" "$f") >/dev/null; then
    diff <(strip_block "$f" "$ONE/$f") <(strip_block "$f" "$f") | head -20
    die "$f in the clone differs from the OneDrive copy beyond the sweep-v2.1 block; merge by hand, then rerun"
  fi
done
for f in VERIFICATION_GUIDE_V21.md VERIFICATION_GUIDE.md README.md CITATION.cff \
         sweep/analyze_v21.py sweep/make_v21_paper.py sweep/run_rerun_v21.py sweep/rerun_status.py \
         sweep/purge_s3.py sweep/azure_mc2.py sweep/DEVIATIONS_V21.md \
         scripts/teardown_v21.sh scripts/fix_ssh_ip.sh scripts/release_v21.sh; do
  cp "$ONE/$f" "$f"; echo "   $f"
done
# files that must be identical to the versions that ran the campaign
for f in sweep/sweep_design_v21.py sweep/s3_equiv_runner.py sweep/azure_blob_runner_v2.py; do
  cmp -s "$ONE/$f" "$f" || die "$f differs between OneDrive and the clone; the clone holds the version that ran -- investigate"
done
grep -qx 'teardown_v21_\*.log' .gitignore 2>/dev/null || echo 'teardown_v21_*.log' >> .gitignore

say "2. filling in DOI $DOI and date $TODAY"
for f in README.md CITATION.cff VERIFICATION_GUIDE_V21.md; do
  sed -i "s#@@V21_DOI@@#$DOI#g; s#@@V21_DATE@@#$TODAY#g" "$f"
done
! grep -rn '@@V21_' README.md CITATION.cff VERIFICATION_GUIDE_V21.md || die "placeholder left"

say "3a. gate: no credential identifiers"
n=$( { grep -rlE 'LTAI[0-9A-Za-z]{8}|GOOG1[0-9A-Z]{8}|ASIA[0-9A-Z]{12}|AKIA[0-9A-Z]{12}' results-rerun-v21 v21-output paper-v21 sweep scripts || true; } | wc -l)
[ "$n" = "0" ] || die "$n file(s) contain a credential identifier"
echo "   none found"

say "3b. gate: manifests"
(cd results-rerun-v21 && sha256sum -c --quiet manifest.sha256) || die "results-rerun-v21 manifest"
(cd v21-output && sha256sum -c --quiet manifest.sha256)        || die "v21-output manifest"
(cd paper-v21 && sha256sum -c --quiet manifest.sha256)         || die "paper-v21 manifest"
echo "   all three verify"

say "3c. gate: results reproduce from the archived data"
PY=$(command -v python3 || command -v python || true)
if [ -n "$PY" ] && "$PY" -c "import numpy, matplotlib" 2>/dev/null; then
  T=$(mktemp -d)
  "$PY" sweep/analyze_v21.py --root results-rerun-v21 --out "$T/out" >/dev/null
  for f in v21-output/*.csv; do cmp -s "$f" "$T/out/$(basename "$f")" || die "$(basename "$f") does not reproduce"; done
  "$PY" sweep/make_v21_paper.py --v21 "$T/out" --d5 results-rerun-v21/azure-mc2 --v1 recompute-output \
        --manifests results-rerun-v21 --out "$T/paper" >/dev/null
  for f in paper-v21/*.tex; do cmp -s "$f" "$T/paper/$(basename "$f")" || die "$(basename "$f") does not reproduce"; done
  echo "   v21-output and paper-v21 reproduce byte for byte"
else
  echo "   (python with numpy/matplotlib not found on this laptop -- skipped; checked in the sandbox before release)"
fi

say "4. change summary"
git add -A results-rerun-v21 v21-output paper-v21 sweep scripts VERIFICATION_GUIDE_V21.md VERIFICATION_GUIDE.md README.md CITATION.cff .gitignore
git status --short | awk '{print $2}' | cut -d/ -f1 | sort | uniq -c
git diff --cached --stat -- README.md VERIFICATION_GUIDE.md CITATION.cff | tail -4
read -r -p "Commit, tag $TAG and push? [y/N] " r; [[ "$r" =~ ^[Yy]$ ]] || die "not confirmed; nothing committed (git reset to undo the staging)"

say "5. commit, tag, push"
git commit -q -m "sweep-v2.1: locked-protocol campaign data (redacted), deviations log, analysis and paper outputs, verification guide"
git tag -a "$TAG" -m "sweep-v2.1: data and analysis for the revised Future Internet manuscript (futureinternet-4640878); DOI $DOI"
git push origin main "$TAG"
git ls-remote --tags origin | grep "$TAG" || die "tag not on GitHub"

say "6. Zenodo deposit"
SHORT=$(git rev-parse --short=8 "$TAG^{commit}")
OUT="$HOME/publish/$TAG-$SHORT.zip"
TZ=Africa/Johannesburg git archive --format=zip --prefix=cloud-storage-bench-thesis-v1/ "$TAG" > "$OUT"
SHA=$(sha256sum "$OUT" | cut -d' ' -f1)
echo "   file:    $OUT"
echo "   commit:  $(git rev-parse "$TAG^{commit}")"
echo "   SHA-256: $SHA"
echo "   files:   $(unzip -l "$OUT" | tail -1 | awk '{print $2}')"
cat <<EOF

Upload $OUT to the Zenodo draft whose DOI is $DOI, set Version to $TAG,
and put this line in the description:
  Deposit = TZ=Africa/Johannesburg git archive of tag $TAG (commit $(git rev-parse --short=12 "$TAG^{commit}")); SHA-256 $SHA
Then publish, and send me the SHA-256 above.
EOF
