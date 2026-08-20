# elbencho tooling notes

The harness drives block, file and object storage through **elbencho** so all
three paradigms share one command path and one CSV output schema. FIO is kept
only as a cross-check on block runs; Azure Blob (non-S3) uses the SDK runner.

## Install (on each Ubuntu benchmark host)
elbencho must be built/installed **with S3 support**:
```
# Debian/Ubuntu package (check https://github.com/breuner/elbencho/releases):
wget https://github.com/breuner/elbencho/releases/download/vX.Y.Z/elbencho-X.Y.Z-ubuntu.deb
sudo apt install -y ./elbencho-X.Y.Z-ubuntu.deb
elbencho --version    # confirm S3 support is compiled in
```

## Flag names vary by version — verify against your build
`scripts/runners.py` builds the command lines. If your elbencho version renames
a flag, adjust the templates there (or here) rather than the parser. Key flags
used: `-r`/`-w` (read/write), `-t` threads, `-b` block size, `-s` file size,
`-n`/`-N` dirs/files (metadata), `--direct`, `--lat --latpercent` (latency),
`--csvfile <path>` (machine-readable output), S3 mode via `--s3endpoint
--s3key --s3secret`.

## Why one tool
The pilot used FIO (block/file) + COSBench (object) and produced two output
formats that were hard to reconcile. elbencho removes that split. See SKILL.md.
