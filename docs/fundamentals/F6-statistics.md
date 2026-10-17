# F6. The Statistics

Every number in the paper's results comes from three ideas: a phase rate, a
log-log slope, and a ratio. Here they are computed from the raw files.

## 1. A phase rate

elbencho's CSV has one row per phase. Throughput is data moved divided by time,
using the values for the slowest thread (`[last]`):

```python
import csv
rows = list(csv.DictReader(open("aws-object-balanced-c16-r1.elbencho.csv")))
for r in rows:
    mib, secs = float(r["MiB [last]"]), float(r["time ms [last]"]) / 1000
    print(r["operation"], mib / secs, "MiB/s")
```

Retries append to the same CSV, so take the last `READ` row and the `WRITE` row
just before it. Never add the two phase rates: they ran one after the other,
so a combined rate is total MiB over total seconds. p99 comes from the
`IO lat % us` line of the stdout log, per phase.

## 2. The scaling exponent

If throughput grows as `T = a * c^beta`, then `log T = log a + beta * log c`,
a straight line whose slope is `beta`. Fit it by ordinary least squares over
the twelve runs of a cell (four thread levels x three repetitions):

```python
import math, numpy as np
c = np.array([1,1,1, 4,4,4, 16,16,16, 64,64,64], float)
T = np.array([...])                                 # twelve write-phase MiB/s values
x, y = np.log10(c), np.log10(T)
beta, a = np.polyfit(x, y, 1)
resid = y - (a + beta * x)
se = math.sqrt(resid @ resid / (len(x) - 2) / ((x - x.mean()) ** 2).sum())
t = 2.228                                           # t(0.975, df = 10)
print(beta, beta - t * se, beta + t * se)           # run-level 95% interval
```

`beta = 1` means throughput doubled when threads doubled; `beta = 0` means it
did not change. It is a description of the tested range, not a law.

## 3. The second interval

The run-level interval treats the twelve runs as independent. Repetitions of
the same level can be correlated, so also fit the four level means (mean of
`log T` per level) and use `t(0.975, df = 2) = 4.303`. With only three levels
(when the 64-thread read is missing) df = 1 and `t = 12.71`, which makes that
interval uninformative.

For AWS object writes this gives beta = 0.9765 (0.976 to three decimals)
with run-level interval [0.955, 0.998] and level-mean interval
[0.941, 1.012]: both exclude zero, so
the conclusion does not depend on the choice. For most file cells only the
run-level interval excludes zero, and the paper says so.

Check your result against the archive:

```bash
grep '^aws,object,write' v21-output/exponents.csv
```

## 4. Ratios for the client-versus-service test

```
ratio_128   = mean T(128 threads, 1 host) / mean T(64 threads, 1 host)
ratio_2host = mean T(2 hosts x 64)        / mean T(64 threads, 1 host)
```

and for the Azure test, also host 1's throughput with host 2 running divided
by host 1's throughput alone (1.00 means the service did not slow it). Read
them with the table in F5.

## 5. Latency growth

The p99 "fold" is the median, across providers, of each provider's ratio
`p99(16 threads) / p99(1 thread)`, per phase and paradigm (a median of ratios,
not a ratio of medians). Block writes: about 15-fold; object storage: about 1.

*Automated by* `sweep/analyze_v21.py` (rates, exponents, both intervals, CPU,
ratios, network) and `sweep/make_v21_paper.py` (tables, figures and the macro
file of values the manuscript prints).

Next: [Provenance and Release](F7-provenance.md)
