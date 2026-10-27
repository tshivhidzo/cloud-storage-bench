#!/usr/bin/env bash
# release_v21_r2.sh [<reserved-zenodo-doi>] -- publish the reanalysis of the
# Future Internet revision R1 as tag sweep-v2.1-r2, with gates.
#
#   cd ~/publish/cloud-storage-bench-thesis-v1
#   ./scripts/release_v21_r2.sh                          # tag + push only
#   ./scripts/release_v21_r2.sh 10.5281/zenodo.NNNNNNNN  # also record the DOI
#
# Adds no measurement data. Copies from the OneDrive working copy:
#   sweep/review_r2.py, sweep/compare_r2.py, sweep/make_v21_paper.py (edited: completion-table cause
#   text, Alibaba/Huawei limit labels, table width), v21-output/review-r2/,
#   paper-v21/ (two regenerated tables + manifest), scripts/release_v21_r2.sh
# Gates: no credentials; manifests verify; review_r2.py reproduces its outputs
# from the archived sweep-v2.1 inputs under the contract of sweep/compare_r2.py
# (tables and macros byte-identical, CSVs within tolerance, figures pixel-identical).
set -euo pipefail
DOI="${1:-}"
ONE="${ONE:-/c/Users/Tshivhidzo/OneDrive - Cape Peninsula University of Technology/Thesis/2026/cloud-storage-bench}"
TAG=sweep-v2.1-r2
cd "$(git rev-parse --show-toplevel)"
say(){ printf '\n== %s\n' "$*"; }
die(){ printf 'STOP: %s\n' "$*"; exit 1; }

git diff --quiet && git diff --cached --quiet || die "the clone has uncommitted changes; commit or stash them first (after a failed run: git checkout -- . && git clean -fd v21-output/review-r2)"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "check out main first (git checkout main)"
command -v python3 >/dev/null && python3 -c "import numpy, scipy, matplotlib" 2>/dev/null || die "python3 with numpy, scipy and matplotlib is required (the Windows Store python3 stub will not do)"
git rev-parse -q --verify "refs/tags/sweep-v2.1" >/dev/null || die "tag sweep-v2.1 not found in this clone"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && die "tag $TAG already exists"
git pull --ff-only origin main

say "1. copying files from OneDrive"
mkdir -p v21-output/review-r2
rm -rf v21-output/review-r2 && cp -r "$ONE/v21-output/review-r2" v21-output/review-r2
rm -rf paper-v21 && cp -r "$ONE/paper-v21" paper-v21
for f in sweep/review_r2.py sweep/compare_r2.py sweep/make_v21_paper.py; do cp "$ONE/$f" "$f"; echo "   $f"; done
# this script itself is committed as it is in the clone (not copied over while running)
# inputs of the reanalysis must be exactly those of sweep-v2.1
for d in results-rerun-v21 recompute-output; do
  git diff --quiet "sweep-v2.1" -- "$d" || die "$d differs from tag sweep-v2.1"
done
for f in v21-output/runs.csv v21-output/exponents.csv v21-output/manifest.sha256 sweep/analyze_v21.py; do
  git diff --quiet "sweep-v2.1" -- "$f" || die "$f differs from tag sweep-v2.1"
done
echo "   inputs identical to sweep-v2.1"

say "2a. gate: no credential identifiers"
n=$( { grep -rlE 'LTAI[0-9A-Za-z]{8}|GOOG1[0-9A-Z]{8}|ASIA[0-9A-Z]{12}|AKIA[0-9A-Z]{12}' v21-output/review-r2 paper-v21 sweep scripts || true; } | wc -l)
[ "$n" = "0" ] || die "$n file(s) contain a credential identifier"

say "2b. gate: manifests"
(cd paper-v21 && sha256sum -c --quiet manifest.sha256) || die "paper-v21 manifest"
(cd v21-output/review-r2 && sha256sum -c --quiet manifest.sha256) || die "review-r2 manifest"

say "2c. gate: review_r2.py reproduces its outputs (contract in sweep/compare_r2.py)"
T=$(mktemp -d)
python3 sweep/review_r2.py --root . --out "$T" >/dev/null
python3 sweep/compare_r2.py v21-output/review-r2 "$T" || die "outputs do not meet the verification contract"
rm -rf "$T"

say "3. commit and tag (review the summary first)"
git add sweep/review_r2.py sweep/compare_r2.py sweep/make_v21_paper.py scripts/release_v21_r2.sh v21-output/review-r2 paper-v21
git status --short
read -r -p "Commit and tag $TAG? [y/N] " ok; [ "$ok" = "y" ] || die "stopped before commit"
git commit -m "Reanalysis for Future Internet revision R1 (sweep-v2.1-r2): diagnostics, phase-aligned CPU, prespecified gated and 1-128 analyses, warm-up comparison${DOI:+; Zenodo $DOI}"
git tag -a "$TAG" -m "Reanalysis of archived sweep-v2.1 data for revision R1; no new measurements${DOI:+ (Zenodo $DOI)}"
git push origin main "$TAG"

say "4. byte-literal archive for Zenodo"
SHA=$(git rev-parse --short "$TAG^{commit}")
TZ=Africa/Johannesburg git archive --format=zip --prefix="cloud-storage-bench-$TAG/" -o "../$TAG-$SHA.zip" "$TAG"
sha256sum "../$TAG-$SHA.zip"
echo "Upload ../$TAG-$SHA.zip unchanged as a new version of concept DOI 10.5281/zenodo.22032835."
