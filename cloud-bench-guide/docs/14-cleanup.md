# Cleaning Up

In this lab you destroy everything the campaign created, prove nothing is left
billing, and delete the campaign credentials.

## Teardown

**laptop**, with each provider's credentials loaded (lab 2) and SSH open to
your current address (lab 4):

```bash
./scripts/teardown_v21.sh --dry-run          # what would happen
./scripts/teardown_v21.sh                    # all five, asks per provider
./scripts/teardown_v21.sh azure alibaba      # or only some
```

Per provider the script:

1. skips the provider if its credentials are not usable (for Azure it requests
   fresh tokens for both scopes, because a cached account passes but an expired
   token fails later in Terraform);
2. refuses unless `rerun_<provider>.tgz` (and for Azure `rerun_azure_mc2.tgz`)
   is in the synced folder;
3. checks over SSH that no storage target is still in host 1's Terraform state;
4. finds leftover benchmark buckets (Alibaba through the host, GCP and AWS from
   the laptop) and removes them;
5. destroys both hosts, network and identity;
6. runs the leak check (AWS, Azure, GCP) or prints the console checklist
   (Huawei, Alibaba);
7. prints how to delete that provider's campaign key.

> If a host is unreachable, the script warns and cannot list Alibaba's buckets
> through it. In our teardown the orphan bucket therefore had to be deleted in
> the OSS console.

What our teardown destroyed: AWS 0 (already gone), Azure 15, GCP 13, Huawei
14, Alibaba 9 resources, with clean leak checks.

## Console checks

- **Huawei**, AF-Johannesburg: ECS, EVS, SFS Turbo (billed hourly), OBS
  (`csb-bench-*`), EIP and VPC empty.
- **Alibaba**, UAE (Dubai): ECS, disks, NAS, OSS (`csb-bench-*`), EIP and VPC
  empty.

## Delete the keys

```bash
gcloud storage hmac list --project=$GCP_PROJECT
gcloud storage hmac update <ACCESS_ID> --deactivate --project=$GCP_PROJECT
gcloud storage hmac delete <ACCESS_ID> --project=$GCP_PROJECT
```

Then the Huawei access key (My Credentials > Access Keys) and the Alibaba
AccessKey (RAM console > Users > csb-bench). Delete the CSV files and close
the Git Bash window. AWS and Azure need nothing: the hosts used a role and a
managed identity, destroyed with them.

## Done

You have a locked protocol, a complete and verified dataset with every attempt,
a paper whose numbers are all generated from it, a citable archive, and no
resources or credentials left behind.
