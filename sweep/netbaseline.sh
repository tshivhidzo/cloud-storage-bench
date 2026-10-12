#!/usr/bin/env bash
# netbaseline.sh <provider> <host2-private-ip>
# Measured client network baseline for the v2.1 rerun (amendment section D).
# Run on the FIRST client host after `iperf3 -s -D` has been started on the
# second client host. 4 parallel streams, 30 s, both directions, 3 repetitions.
# Output: results-rerun-v21-<provider>/netbaseline_<provider>.json
set -euo pipefail
PROVIDER="${1:?usage: netbaseline.sh <provider> <host2-private-ip>}"
H2="${2:?usage: netbaseline.sh <provider> <host2-private-ip>}"
OUT="results-rerun-v21-${PROVIDER}"
mkdir -p "$OUT/netbaseline"
command -v iperf3 >/dev/null || sudo apt-get install -y iperf3
for rep in 1 2 3; do
  iperf3 -c "$H2" -P 4 -t 30 -J > "$OUT/netbaseline/send_r${rep}.json"
  sleep 5
  iperf3 -c "$H2" -P 4 -t 30 -R -J > "$OUT/netbaseline/recv_r${rep}.json"
  sleep 5
done
python3 - "$OUT" "$PROVIDER" <<'EOF'
import json, sys, glob, statistics, os, datetime
out, prov = sys.argv[1], sys.argv[2]
res = {"provider": prov, "measured_utc": datetime.datetime.utcnow().isoformat() + "Z",
       "nproc": os.cpu_count(), "runs": []}
for f in sorted(glob.glob(f"{out}/netbaseline/*.json")):
    d = json.load(open(f))
    bps = d["end"]["sum_received"]["bits_per_second"]
    res["runs"].append({"file": os.path.basename(f),
                        "direction": "send" if "send" in f else "receive",
                        "gbit_s": round(bps / 1e9, 3),
                        "mib_s": round(bps / 8 / 2**20, 1)})
for dirn in ("send", "receive"):
    v = [r["mib_s"] for r in res["runs"] if r["direction"] == dirn]
    if v:
        res[f"{dirn}_median_mib_s"] = statistics.median(v)
json.dump(res, open(f"{out}/netbaseline_{prov}.json", "w"), indent=2)
print(json.dumps({k: v for k, v in res.items() if k != "runs"}, indent=2))
EOF
