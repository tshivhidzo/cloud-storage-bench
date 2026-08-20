output "region" { value = var.region }

output "target" {
  description = "container name (object) or POSIX mount path (block/file)"
  value = var.paradigm == "object" ? (
    length(azurerm_storage_container.obj) > 0 ? azurerm_storage_container.obj[0].name : ""
    ) : var.paradigm == "block" ? var.mount_block : var.mount_file
}

# provision.py exports any output named env_* into the runner's environment.
# azure_blob_runner.py needs the connection string; the account (and its key)
# lives only for this run and is destroyed with the target.
output "env_AZURE_STORAGE_CONNECTION_STRING" {
  sensitive = true
  value = var.paradigm == "object" && length(azurerm_storage_account.sa) > 0 ? (
    azurerm_storage_account.sa[0].primary_connection_string
  ) : ""
}
