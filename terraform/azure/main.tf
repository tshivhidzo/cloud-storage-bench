terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
    random  = { source = "hashicorp/random",  version = "~> 3.0" }
  }
}

# Runs ON the benchmark host using its user-assigned managed identity.
# Requires env: ARM_USE_MSI=true, ARM_SUBSCRIPTION_ID, ARM_TENANT_ID,
# ARM_CLIENT_ID (the identity's client id). No az CLI, no long-lived keys.
provider "azurerm" {
  features {}
}

resource "random_string" "s" {
  length  = 8
  upper   = false
  special = false
}

# The host's resource group already exists (created by hosts/azure); the
# managed identity is Contributor there and cannot create new RGs.
data "azurerm_resource_group" "rg" {
  name = var.resource_group
}

data "azurerm_virtual_machine" "host" {
  name                = var.host_vm_name
  resource_group_name = data.azurerm_resource_group.rg.name
}

# ===================== OBJECT (Blob container; azure_blob_runner.py) =========
resource "azurerm_storage_account" "sa" {
  count                    = var.paradigm == "object" ? 1 : 0
  name                     = "csb${random_string.s.result}"
  resource_group_name      = data.azurerm_resource_group.rg.name
  location                 = data.azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
resource "azurerm_storage_container" "obj" {
  count                 = var.paradigm == "object" ? 1 : 0
  name                  = "bench"
  storage_account_name  = azurerm_storage_account.sa[0].name
  container_access_type = "private"
}

# ===================== BLOCK (Managed Disk) ==================================
resource "azurerm_managed_disk" "block" {
  count                = var.paradigm == "block" ? 1 : 0
  name                 = "csb-bench-block"
  location             = data.azurerm_resource_group.rg.location
  resource_group_name  = data.azurerm_resource_group.rg.name
  storage_account_type = "StandardSSD_LRS" # nearest general-purpose SSD tier
  create_option        = "Empty"
  disk_size_gb         = var.volume_gb
}
resource "azurerm_virtual_machine_data_disk_attachment" "block" {
  count              = var.paradigm == "block" ? 1 : 0
  managed_disk_id    = azurerm_managed_disk.block[0].id
  virtual_machine_id = data.azurerm_virtual_machine.host.id
  lun                = 10
  caching            = "None" # measure the disk, not the host cache

  # Azure udev rules expose the disk at a stable LUN path.
  provisioner "local-exec" {
    command = <<-CMD
      set -e
      DEV=""
      for i in $(seq 1 60); do
        CAND="/dev/disk/azure/scsi1/lun10"
        if [ -e "$CAND" ]; then DEV="$(readlink -f "$CAND")"; break; fi
        sleep 2
      done
      [ -n "$DEV" ] && [ -b "$DEV" ] || { echo "data disk at lun10 not found"; exit 1; }
      sudo blkid "$DEV" || sudo mkfs.ext4 -F "$DEV"
      sudo mkdir -p ${var.mount_block}
      sudo umount ${var.mount_block} 2>/dev/null || true
      sudo mount "$DEV" ${var.mount_block}
      sudo chmod 777 ${var.mount_block}
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_block default
    command = "sudo umount /mnt/block || true"
  }
}

# ===================== FILE (Azure Files, SMB) ===============================
# Standard Azure Files is SMB-native (NFS needs Premium + VNet integration).
# SMB 3.1.1 with cache=none supports O_DIRECT. Disclose the protocol difference
# vs AWS EFS (NFS) in the thesis -- it is a real paradigm-implementation gap.
resource "azurerm_storage_account" "safile" {
  count                    = var.paradigm == "file" ? 1 : 0
  name                     = "csbf${random_string.s.result}"
  resource_group_name      = data.azurerm_resource_group.rg.name
  location                 = data.azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}
resource "azurerm_storage_share" "file" {
  count                = var.paradigm == "file" ? 1 : 0
  name                 = "bench"
  storage_account_name = azurerm_storage_account.safile[0].name
  quota                = var.volume_gb

  provisioner "local-exec" {
    command = <<-CMD
      set -e
      command -v mount.cifs >/dev/null || sudo apt-get install -y cifs-utils
      sudo mkdir -p ${var.mount_file}
      printf 'username=%s\npassword=%s\n' \
        '${azurerm_storage_account.safile[0].name}' \
        '${azurerm_storage_account.safile[0].primary_access_key}' \
        | sudo tee /root/.csb-smbcred >/dev/null
      sudo chmod 600 /root/.csb-smbcred
      sudo umount ${var.mount_file} 2>/dev/null || true
      sudo mount -t cifs \
        //${azurerm_storage_account.safile[0].name}.file.core.windows.net/bench \
        ${var.mount_file} \
        -o credentials=/root/.csb-smbcred,vers=3.1.1,cache=none,serverino,nosharesock,actimeo=30,dir_mode=0777,file_mode=0777
    CMD
  }
  provisioner "local-exec" {
    when = destroy
    # destroy provisioners cannot reference var.*; path matches mount_file default
    command = "sudo umount /mnt/file || true; sudo rm -f /root/.csb-smbcred"
  }
}
