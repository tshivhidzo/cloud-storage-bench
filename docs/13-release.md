# Releasing the Dataset

In this lab you publish the data, code and outputs as a new version of the
Zenodo record, as the byte-literal archive of a git tag, with a DOI that the
manuscript can cite before you publish.

## Remove credential identifiers

elbencho writes its command line into each result CSV. Replace the values after
`"--s3key"`, `"--s3secret"` and `"--s3sessiontoken"` with `REDACTED`, change
nothing else, and record the SHA-256 of each original archive in
`results-rerun-v21/PROVENANCE.md`. Then prove nothing measured changed: rerun
labs 11 and 12 on the redacted tree and compare every output byte for byte.

```bash
grep -rhoE '"--s3(key|secret|sessiontoken)" "[^"]*"' results-rerun-v21 | sort | uniq -c   # only "REDACTED"
grep -rlE 'LTAI[0-9A-Za-z]{8}|GOOG1[0-9A-Z]{8}|ASIA[0-9A-Z]{12}|AKIA[0-9A-Z]{12}' results-rerun-v21 | wc -l   # 0
```

We removed 186 values from 75 files.

## Reserve the DOI

On Zenodo, open the previous version, choose **New version**, delete the
carried-over file, choose **Get a DOI now**, and save the draft. Put the DOI
into the manuscript's Data Availability statement now.

## Tag and build the deposit

**laptop**

```bash
./scripts/release_v21.sh 10.5281/zenodo.<reserved>
```

The script stops at the first failed gate:

1. copies the release folders and files from the working copy, and refuses if
   the clone's README or guide holds edits the copy would overwrite;
2. fills in the DOI and date;
3. checks for credential patterns, verifies the three checksum manifests, and
   regenerates `v21-output/` and `paper-v21/` from the data, byte for byte;
4. shows the change summary and asks before committing;
5. commits, tags `sweep-v2.1`, pushes;
6. builds the deposit with
   `TZ=Africa/Johannesburg git archive --format=zip --prefix=cloud-storage-bench-thesis-v1/ sweep-v2.1`
   and prints its SHA-256, the commit and the file count.

> Both gates fired during our release, as intended. The README in the working
> copy was older than the clone's, and Windows Python wrote the tables with
> CRLF line endings, so they no longer matched the Linux-built copies byte for
> byte. The first was fixed in the working copy, the second in
> `make_v21_paper.py`.

Before uploading, confirm nothing sensitive went in:

```bash
git show --stat sweep-v2.1 | grep -c '^ terraform/'                                    # 0
unzip -l ~/publish/sweep-v2.1-*.zip | grep -ciE 'tfstate|\.tfvars|credentials\.csv'     # 0
unzip -z ~/publish/sweep-v2.1-*.zip | tail -1                                         # the commit
```

## Publish

In the draft: upload the zip unchanged, set Version to `sweep-v2.1`, paste the
description (purpose, campaign, contents, deposit identity with SHA-256, tag
object, commit, file count and git version, verification, credential hygiene),
and add related works: **Is new version of** the previous DOI (scheme DOI),
**Is supplement to** the GitHub tag URL (scheme URL, resource type Software).
After publishing, compare Zenodo's MD5 with `md5sum` of the local zip.

Our record: DOI 10.5281/zenodo.23434883, 3,208 files, deposit SHA-256
`da92f5eb6002561b3bd281475e628c1329ee67a140917fbc547de05d9b1ad244`.

Next: [Cleaning Up](14-cleanup.md)
