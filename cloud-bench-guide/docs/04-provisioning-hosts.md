# Provisioning the Client Hosts

In this lab you create two client hosts per provider in the same subnet, with
SSH open only to your own address.

## Create the hosts

**laptop**, with the provider's credentials loaded (lab 2):

```bash
cd ~/publish/cloud-storage-bench-thesis-v1
export AUTO_SHUTDOWN_HOURS=0     # the campaign outlives the default 8-hour timer
export SECOND_CLIENT=true
./scripts/host_up.sh <provider>  # gcp also needs GCP_PROJECT
```

Record the addresses:

```bash
H=$(terraform -chdir=terraform/hosts/<provider> output -raw host_ip)
H2=$(terraform -chdir=terraform/hosts/<provider> output -raw host2_ip)
H2P=$(terraform -chdir=terraform/hosts/<provider> output -raw host2_private_ip)
echo "H=$H H2=$H2 H2P=$H2P"
```

`H2P` is the address host 1 uses to reach host 2 inside the subnet. You cannot
reach it from the laptop.

## Huawei and Alibaba: create the ubuntu user

Their Ubuntu images log in as `root`, and `host_up.sh` then waits for
`ubuntu@` and either asks for a password (Huawei) or ends without "Bootstrap
complete" (Alibaba). Press Ctrl-C if it asks for a password; the hosts exist.
On each of the two hosts:

```bash
ssh root@<host public ip>
ls /var/lib/csb-bootstrap-complete            # wait if missing
id ubuntu || useradd -m -s /bin/bash ubuntu
mkdir -p /home/ubuntu/.ssh && cp /root/.ssh/authorized_keys /home/ubuntu/.ssh/
chown -R ubuntu:ubuntu /home/ubuntu/.ssh && chmod 700 /home/ubuntu/.ssh && chmod 600 /home/ubuntu/.ssh/authorized_keys
echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/90-csb-benchmark && chmod 440 /etc/sudoers.d/90-csb-benchmark
visudo -c && exit
```

## Verification

```bash
for h in $H $H2; do ssh -o ConnectTimeout=8 ubuntu@$h 'hostname; nproc; sudo -n true && echo sudo-ok'; done
```

Expected for each host: its hostname, `4`, `sudo-ok`.

## When things go wrong

**GCP: 409 "already exists".** Resources from an earlier campaign were still
there. Import them into the new state (`terraform import`) or delete them, then
apply again.

**Host key changed.** A new host reused an old address. Confirm the new key
(for example from the provider's serial console), then
`ssh-keygen -R <ip>`.

**Your laptop's IP changes.** SSH then times out on every host. Re-point only
the SSH rule, without touching the hosts:

```bash
SSH_CIDR_WIDTH=16 ./scripts/fix_ssh_ip.sh aws azure gcp huawei alibaba
```

Our connection's address changed three times in six days; a /24 was not wide
enough the third time, so the script also accepts /16. Login still requires
your SSH key. Expect `0 added, 1 changed, 0 destroyed` on AWS, Azure and GCP
and `1 added, 0 changed, 1 destroyed` on Huawei and Alibaba (the rule is
replaced). Azure needs both sign-ins from lab 2 for this; if Graph still
refuses, update the rule directly with `az network nsg rule update`.

Next: [Preparing the Hosts](05-preparing-hosts.md)
