# F4. Telemetry and the Network

To say a limit is in the client you must show the client was busy, core by
core, and that its network was not full.

## Per-core CPU from mpstat

```bash
mpstat -P ALL 5
```

prints, every 5 seconds, one row for `all` and one per core:

```
18:59:25     CPU    %usr   %nice    %sys %iowait    %irq   %soft  %steal  %guest  %gnice   %idle
18:59:30     all    9.73    0.00    0.76    0.00    0.00    0.40    0.00    0.00    0.00   89.11
18:59:30       0    9.86    0.00    0.80    0.00    0.00    0.40    0.00    0.00    0.00   88.93
```

Busy time is everything that is neither idle nor waiting for I/O:

```
busy = 100 - %idle - %iowait
```

(`%iowait` is idle time with I/O outstanding; counting it as busy would make a
waiting client look saturated.) From the rows of one run compute:

```python
import re, statistics as st
from collections import defaultdict
samples, hdr = defaultdict(dict), None
for line in open("run.mpstat.txt"):
    parts = line.split()
    if "%idle" in parts: hdr = parts; continue
    if hdr and len(parts) == len(hdr) and parts[0] != "Average:":
        busy = 100 - float(parts[hdr.index("%idle")]) - float(parts[hdr.index("%iowait")])
        samples[parts[0]][parts[hdr.index("CPU")]] = busy
all_core = st.mean(d["all"] for d in samples.values())
busiest  = st.mean(max(v for k, v in d.items() if k != "all") for d in samples.values())
hot      = sum(max(v for k, v in d.items() if k != "all") >= 90 for d in samples.values()) / len(samples)
```

`all_core` is what the earlier campaign recorded. `busiest` answers the
reviewer's question whether one core saturated while the mean stayed low
(in our data, never: where the mean was 50% or more, the busiest core was
within 1.6 points of it). `hot` is the share of samples with any core at 90% or
more.

## Network capacity with iperf3

On host 2: `iperf3 -s -D`. On host 1:

```bash
iperf3 -c $H2P -P 4 -t 30 -J > send.json        # host 1 -> host 2
iperf3 -c $H2P -P 4 -t 30 -R -J > recv.json     # host 2 -> host 1
iperf3 -c $H2P -P 4 -t 600 -J > sustained.json  # 10 minutes
python3 -c "import json;e=json.load(open('send.json'))['end'];print(e['sum_received']['bits_per_second']/1e9,'Gbit/s')"
```

Four parallel streams avoid measuring a single TCP connection's limit. The
600-second run exposes burst credits: compare the first and the last minute of
its `intervals`. Azure caps outbound traffic only, so on Azure the "send"
figure is the binding one for writes.

To compare with storage throughput: 1 Gbit/s is about 119 MiB/s, so a host
reading 341 MiB/s is moving about 2.9 Gbit/s.

*Automated by* the `PerCoreTelemetry` class in `sweep/run_rerun_v21.py`
(starts `mpstat -P ALL 5` with the measurement and stops it after),
`sweep/netbaseline.sh` (the 30-second runs), and `mpstat()` in
`sweep/analyze_v21.py` (the computation above).

Next: [Two Clients and the Runner Test](F5-two-clients-and-runner.md)
