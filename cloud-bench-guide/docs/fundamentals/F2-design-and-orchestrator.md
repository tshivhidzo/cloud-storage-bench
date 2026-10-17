# F2. The Design and the Orchestrator

The campaign is five rules applied to a grid. Once you can write the plan down
yourself, the orchestrator is only a loop around F1.

## Derive the plan

```python
import random
providers = ["aws", "azure", "gcp", "huawei", "alibaba"]
paradigms = ["block", "file", "object"]
levels, reps = [1, 4, 16, 64], [1, 2, 3]
PER_THREAD_MIB = 1280                      # 1.25 GiB per thread

def run_id(p, para, c, r, suffix=""):
    return f"{p}-{para}-balanced-c{c:02d}-r{r}" + (f"-{suffix}" if suffix else "")

plan = []
for p in providers:
    runs = [dict(id=run_id(p, para, c, r), para=para, c=c, mib=PER_THREAD_MIB * c,
                 stage=1 if para in ("block", "object") else 2)
            for para in paradigms for c in levels for r in reps]
    runs += [dict(id=run_id(p, "object", 128, r), para="object", c=128,
                  mib=PER_THREAD_MIB * 128, stage=2) for r in reps]          # 128-thread level
    if p != "azure":
        runs += [dict(id=run_id(p, "object", 64, r, "mc2"), para="object", c=64,
                      hosts=2, stage=2) for r in reps]                       # two clients
    ordered = []
    for stage in (1, 2):                                                     # shuffle per stage
        part = [x for x in runs if x["stage"] == stage]
        random.Random(43).shuffle(part)
        ordered += part
    plan += ordered
```

That gives 24 stage-1 runs per provider and 18 stage-2 runs (15 on Azure,
which has no two-client runs): 207. AWS adds 12 runner-comparison and 6
reservoir runs (225), and the three fresh-bucket repeats of deviation D1 make
228. A fixed seed means the order can be regenerated and checked; this sketch
illustrates the rules, and `sweep/sweep_design_v21.py` reproduces the exact
order that was run (`--dry-run` prints it).

Why each rule:

| Rule | Reason |
|---|---|
| weak scaling, 1.25 GiB per thread | constant work per thread at every level; the earlier campaign mixed three sizing rules, and sizing changes block write exponents |
| stages | the runs the main findings rest on finish first, whatever happens later |
| shuffled order | time-of-day and drift do not line up with thread count |
| fixed seed | the order is reproducible and checkable |
| stopping date | the campaign cannot quietly extend to rescue a result |

## The loop

For each planned run, the orchestrator does F1 and appends exactly one record:

```python
for run in plan:
    if now() > STOP_AT: break                    # stopping rule
    rec = {"run_id": run["id"], "ts_start": now(), ...}
    try:
        target = provision(provider, run["para"])
        rec.update(execute(run, target))         # warm-up, measure, mpstat, hashes
    except Exception as e:
        rec.update(status="failed", error=str(e))
    finally:
        empty_bucket_if_object(target)
        teardown(provider, run["para"])          # always, even after a failure
    rec["ts_end"] = now()
    manifest.write(json.dumps(rec) + "\n")       # append-only
```

## Resume and the retry limit

`--resume` reads the manifest, counts attempts per run ID, skips runs that have
an `ok` record, and skips runs with three attempts (reported as blanks). Nothing
is ever deleted from the manifest, so every attempt remains visible:

```python
tries, done = {}, set()
for line in open("run_manifest.jsonl"):
    r = json.loads(line)
    tries[r["run_id"]] = tries.get(r["run_id"], 0) + 1
    if r["status"] == "ok":
        done.add(r["run_id"])
todo = [x for x in plan if x["id"] not in done and tries.get(x["id"], 0) < 3]
```

`rerun_status.py` prints this per stage, and its gates check each accepted run
for a non-empty CSV, per-core mpstat rows, a recorded hash and a clean teardown.

## Supplementary runs

A repeat ordered by a deviation (D1) is not a retry: it gets its own run ID
(`-fb`) and its own record, so the original stays in the data and both can be
reported. That is what the `--fb` option builds.

Next: [Object Storage Over the S3 API](F3-object-storage.md)
