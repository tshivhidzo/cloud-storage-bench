# Appendix: Lessons Learned

## Timeline of the research programme

| When (2026) | Stage | Event |
|---|---|---|
| May to July | MTech thesis | harness designed (architecture, runbook, hardware and access documents); Terraform modules and pipeline built |
| July to August | MTech thesis | thesis campaign at 16 threads on five clouds, with costs; thesis through supervisor and editor review, finalised for examination in August |
| August | Conferences | SAFER-TEA 2025 paper submitted, camera-ready prepared (not yet published); ICSSA 2026 paper accepted (10 August), copyright signed |
| 15 August | Journal paper | concurrency-scaling skeleton and analysis plan |
| August | Earlier campaign | 360-run sweep at 1 to 64 threads; 611 attempts; instrument corrections; audited Zenodo releases r3 to r13 |
| 20 to 24 August | Journal paper | manuscripts prepared for CCPE and ACM TOS (not submitted; awaiting co-author feedback); Future Internet manuscript prepared; methodology paper drafted and put on hold |
| 8 and 12 September | Journal paper | supervisor review rounds 1 and 2; archive r14 published (10.5281/zenodo.22681160) |
| September to October | Thesis | eSango dataset deposit prepared; repository access requested |
| 17 September | Conference | faculty declines the ICSSA registration-fee request |
| 23 September | Conference | ICSSA 2026 paper presented remotely (conference 22 to 23 September); formatting corrections and PDF eXpress by 29 September |
| 3 October | Journal paper | supervisor review round 3 |
| 5 October | Journal paper | submitted to Future Internet (futureinternet-4640878) |
| 10 October | Journal paper | major revision; rerun chosen; extension requested |
| 12 to 17 October | October campaign | the campaign in these labs (detail below) |
| by 30 October | Journal paper | supervisor review, then resubmission |

## Timeline of the October 2026 campaign

| Date | Event |
|---|---|
| 10 Oct | Major revision received; three reviewers ask for a uniform rerun, multi-client runs, measured network limits and a runner equivalence test; extension requested |
| 11 Oct | Rerun plan and costs sent to the supervisor and head of department; extension to 30 October granted shortly after |
| 12 Oct | Protocol tagged `protocol-v2.1-locked`; first run at 18:54 UTC |
| 12 to 13 Oct | AWS purge throttled (fixed); GCP leftovers imported; laptop IP changed |
| 13 Oct | Alibaba purge `MissingArgument`; Content-MD5 fix; deviation D1 |
| 14 Oct | Huawei two-client runs fail on `host2` (D2); Alibaba credential-less retry (D3) |
| 15 Oct | AWS and Azure complete and archived; analysis against reviewer comments starts |
| 16 Oct | Huawei and GCP complete; Alibaba fresh-bucket repeats; Azure two-host test designed (D5) |
| 17 Oct | Azure two-host test complete; teardown of all five clouds; dataset released (10.5281/zenodo.23434883); manuscript revised |

## Deviations

| | What happened | Treatment | Effect |
|---|---|---|---|
| D1 | OSS rejected bucket emptying; three Alibaba object runs used a reused bucket | kept and flagged; repeated on fresh buckets | writes 9 to 15% slower; exponent changed by 0.008 |
| D2 | Huawei two-client runs started with an unresolvable host name | retried with the address | none |
| D3 | Alibaba retry started without credentials | counted as an attempt | none |
| D4 | GCP teardown hit a transient 404 | none needed | none |
| D5 | Azure has no two-host mode | supplementary test, logged before running | located the Azure limit in the client |

## What the earlier work taught (and how the method answers it)

| Shortcoming in the thesis or earlier campaign | Where the method now handles it |
|---|---|
| One parallelism level (16 threads) in the thesis | thread sweep 1 to 128, two hosts (labs 3, 9) |
| 251 failed attempts; completion fell with concurrency | fixed retry limit, every attempt recorded, bucket emptying before deletion (labs 3, 7, 8) |
| Four mid-campaign procedure changes; three sizing rules | protocol tagged before the first run; one sizing rule (lab 3) |
| Runs in design order; correlated repetitions | shuffled order with a fixed seed (lab 3) |
| All-core CPU only; no second client | per-core telemetry; 128-thread and two-host levels (labs 7, 9, 11) |
| Network limits documented, not measured | iperf3 baseline, 30 s and 600 s (lab 6) |
| Azure measured with a different, untested tool | runner compared with elbencho on AWS S3; Azure two-host test (lab 9) |
| A batching Azure runner and a public Alibaba endpoint mimicked service limits | corrected runner; orchestrator refuses the public endpoint (lab 5) |
| Instrument versions not recorded per run | SHA-256 of elbencho and runner in every record (lab 7) |
| Results relied on text a reviewer could not check | every value generated from data; archive verified byte for byte (labs 12, 13) |

Beyond the measurements, two lessons from the publication side:

- **Conference support takes longer than the paper.** The ICSSA registration
  request went in three weeks before the conference and was declined; apply for
  faculty support as soon as a paper is accepted, with the ethics position
  settled in advance.
- **Agree the venue with the co-author before polishing for it.** The
  concurrency paper was formatted for three journals in four days; only the
  Future Internet version was submitted, and the other two still await
  co-author feedback. The analysis did not change, but the packaging was
  repeated.

## What we would do differently

1. **Test bucket emptying on every provider before the campaign.** The AWS
   throttling and the OSS checksum rejection both appeared mid-campaign, and
   the second cost three runs.
2. **Never type a variable name where a value belongs.** `H2P=host2` cost three
   attempts. Read addresses from `terraform output` and check them with
   `getent hosts` before launching.
3. **One shell holds the credentials.** Read-only windows for watching; every
   `--resume` from window 0, after `echo ${#S3_ACCESS_KEY}`.
4. **Check that a check really ran.** A silent SSH failure was once read as
   "no buckets"; the teardown script now says when it could not look.
5. **Expect the client to be the limit.** On 4 vCPU hosts, three of five object
   services were limited by the client at 64 threads. Plan a second client and
   per-core telemetry from the start.
6. **Size block datasets deliberately.** Short writes ran up to four times
   faster than sustained writes on three providers; a sizing rule changes block
   write exponents.
7. **Write deviations down first.** Every decision in the table above was
   recorded before its results were seen, which is what made them reportable.
8. **Make outputs platform-independent.** Write text files with explicit LF line
   endings if you promise byte-for-byte reproduction.
9. **Keep the synced working copy and the git clone in step.** The release
   script caught one stale README; checking before release is cheaper.
10. **Plan for sign-in expiry and changing IPs.** Institutional sign-in limits
    and residential addresses both interrupted access several times; the
    campaign itself kept running because it lived in tmux on the hosts.
