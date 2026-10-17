# F7. Provenance and Release

A result is only as good as a stranger's ability to check it. Four mechanisms
make the archive checkable, and each is a few commands.

## Hash what ran

```bash
sha256sum $(which elbencho) sweep/azure_blob_runner_v2.py
```

Each run record stores these, so a reader can see that every run used the same
instrument (one elbencho hash across all 228 runs; one runner hash on Azure).

## A manifest of what was kept

```bash
cd results-rerun-v21
find . -type f ! -name manifest.sha256 | sort | sed 's#^\./##' | xargs -d '\n' sha256sum > manifest.sha256
sha256sum -c --quiet manifest.sha256 && echo ok      # anyone can re-check later
```

## Remove secrets without changing data

Replace only the values after the three credential flags, then prove no metric
moved by rerunning the analysis and comparing outputs byte for byte:

```python
import re, glob
pat = re.compile(r'("--s3(?:key|secret|sessiontoken)" ")[^"]*(")')
for f in glob.glob("results-rerun-v21/**/*.elbencho.csv", recursive=True):
    t = open(f).read()
    open(f, "w", newline="").write(pat.sub(r"\1REDACTED\2", t))
```

Write text with explicit line endings (`newline="\n"` or `newline=""`): on
Windows the default is CRLF, which breaks byte-for-byte comparison with files
made on Linux.

## An archive that is the tag

```bash
git tag -a sweep-v2.1 -m "..."
TZ=Africa/Johannesburg git archive --format=zip --prefix=cloud-storage-bench-thesis-v1/ sweep-v2.1 > sweep-v2.1.zip
unzip -z sweep-v2.1.zip | tail -1          # the commit, stored in the zip comment
sha256sum sweep-v2.1.zip
```

`git archive` writes only committed files, so nothing untracked (Terraform
state, keys) can slip in. Zip entries store local times, so fix the time zone
to make the bytes repeatable. Publish the SHA-256 in the record's description;
it cannot be stored inside the archive it hashes.

## Reserve, then publish

Reserve the DOI first, write it into the files and the manuscript, then tag,
archive, upload and publish. The order matters: the DOI inside the archive must
be the DOI of the record that holds it.

*Automated by* `scripts/release_v21.sh`, which runs these steps with a gate
after each, and `VERIFICATION_GUIDE_V21.md`, which gives a reader the commands
to check them.

Back to [Fundamentals](README.md) or the [labs](../../README.md).
