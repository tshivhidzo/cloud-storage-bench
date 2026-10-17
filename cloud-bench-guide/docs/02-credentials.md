# Credentials

In this lab you load the credentials for each provider into a laptop shell,
check them without printing them, and learn how they reach a host without
touching its disk.

Each provider authenticates differently, and three of them caused trouble in
the October 2026 campaign. Do this lab in a fresh Git Bash window for each
working session.

## AWS

Use your normal profile. The hosts use an instance role, so no AWS key ever
goes to a host.

```bash
aws sts get-caller-identity --query Account --output text
```

## Azure

Azure needs two sign-ins: Resource Manager for most operations, and Microsoft
Graph, which the Terraform `azurerm` provider also requests.

```bash
az login --tenant <tenant-id> --scope https://management.core.windows.net//.default
az login --tenant <tenant-id> --scope https://graph.microsoft.com//.default
az account show --query "{sub:name, state:state}" -o tsv
az account get-access-token --resource-type ms-graph --query expiresOn -o tsv
```

> Our institution's conditional access limits a sign-in to 12 hours. An
> expired token shows up as `AADSTS70043` (refresh token expired) or
> `AADSTS50076` (MFA required for Graph). `az account show` still succeeds from
> its cache, so test with `get-access-token`, as above.

The Azure hosts use a managed identity (lab 5); no Azure key goes to a host.

## GCP

```bash
gcloud auth login && gcloud auth application-default login
export GCP_PROJECT=<project-id>
gcloud config set project $GCP_PROJECT
```

elbencho reaches Cloud Storage through its S3 interoperability API, which
needs an HMAC key. Create it on the laptop (the host's service account is not
allowed to create HMAC keys):

```bash
gcloud storage hmac create <service-account-email> --project=$GCP_PROJECT
```

Note the access ID and secret once; you will pass them to the host in lab 5.

## Huawei and Alibaba

Create a fresh access key for the campaign (Huawei: My Credentials > Access
Keys; Alibaba: a RAM user with ECS, VPC, NAS and OSS permissions, then
AccessKey). Each console offers a CSV download. Keep the CSV outside any synced
folder and load the key from it, never by pasting:

```bash
F=~/Downloads/credentials.csv                      # Huawei
export HW_ACCESS_KEY=$(tail -n 1 "$F" | tr -d '\r"' | awk -F, '{print $(NF-1)}')
export HW_SECRET_KEY=$(tail -n 1 "$F" | tr -d '\r"' | awk -F, '{print $NF}')

F=~/Downloads/<alibaba-accesskey>.csv              # Alibaba
export ALICLOUD_ACCESS_KEY=$(tail -n 1 "$F" | tr -d '\r"' | awk -F, '{print $(NF-1)}')
export ALICLOUD_SECRET_KEY=$(tail -n 1 "$F" | tr -d '\r"' | awk -F, '{print $NF}')

echo "${#HW_ACCESS_KEY} ${#HW_SECRET_KEY} ${#ALICLOUD_ACCESS_KEY} ${#ALICLOUD_SECRET_KEY}"
```

Expected: `20 40 24 30`.

> Typing or pasting keys failed three times during the campaign: clipboard
> artefacts made an Alibaba ID 27 and then 25 characters long, and arrow keys
> inserted `[D` into a Huawei ID. Loading from the CSV avoids all of these.
> Check lengths with `${#VAR}`; the form `${#!v}` fails in an interactive shell
> because `!` triggers history expansion.

## Passing a key to a host

A key reaches a host through ssh standard input into RAM (`/dev/shm`), is
sourced in the shell that needs it, and is deleted at once:

```bash
printf 'export S3_ACCESS_KEY=%s\nexport S3_SECRET_KEY=%s\n' "$ID" "$SK" \
  | ssh ubuntu@$H 'umask 077; cat > /dev/shm/s3.env'
# then, on the host, in the shell that runs the campaign:
source /dev/shm/s3.env && rm /dev/shm/s3.env
```

The variables then exist only in that shell. A new tmux window does not
inherit them, which matters in lab 7.

Next: [Locking the Protocol](03-locking-the-protocol.md)
