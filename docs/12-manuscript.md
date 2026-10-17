# Tables, Figures and the Manuscript

In this lab you generate every table, figure and in-text value of the paper
from the analysis outputs, so that no result is typed by hand, and build the
manuscript.

## Generate

```bash
python3 sweep/make_v21_paper.py --v21 v21-output --d5 results-rerun-v21/azure-mc2 \
  --v1 recompute-output --manifests results-rerun-v21 --out paper-v21
```

This writes:

- `v21_macros.tex`: about 250 values the text uses, such as `\bAwsObjectW`
  (an exponent) or `\vDfiveWratio` (the Azure two-host ratio);
- `tab_v21_*.tex`: completion, exponents with both intervals, client vs
  service, runner comparison, reservoir, block vs documented limits, network,
  earlier vs present;
- `figures/fig_v21_*.png` at 600 dpi.

Tables and the macro file are written with LF line endings on every platform,
so they compare byte for byte on Windows and Linux.

## Build the manuscript

Put the generated files next to `main.tex` (with the MDPI `Definitions/`
folder) and compile:

```bash
pdflatex main && bibtex main && pdflatex main && pdflatex main
grep -cE '^!|undefined' main.log      # 0
```

## Documented limits

Values that are not measurements, such as provider performance limits, are
cited to the provider documentation, checked on the date of writing:

| Product | Documented limit | Measured read |
|---|---|---|
| AWS gp3 | 125 MiB/s baseline, non-bursting | 126 to 128 MiB/s |
| Azure Standard SSD E10 | 500 IOPS (burst 600), so 31 to 38 MiB/s at 64 KiB | 38 MiB/s |
| GCP pd-ssd | 240 MiB/s per-instance baseline | 240 MiB/s |
| Huawei EVS ultra-high I/O | 170 MiB/s by size, 350 MiB/s type maximum | 348 to 353 MiB/s |
| Alibaba ESSD PL1 | min(120 + 0.5 x 100, 350) = 170 MB/s | 170 MiB/s |

## Writing it up

What the paper had to do, following the reviewers:

- present the method as the contribution, and the results as what it showed;
- summarise the unpublished earlier campaign, its findings and limitations,
  with a table mapping each limitation to its fix (readers cannot look it up);
- report both interval constructions, and say which conclusions depend on the
  choice;
- state each interpretation with its evidence, in measured language;
- keep a deviations table, and a threats table that maps threats to claims;
- add abbreviations and open research directions.

Next: [Releasing the Dataset](13-release.md)
