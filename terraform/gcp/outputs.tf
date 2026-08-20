output "region" { value = var.region }

output "target" {
  description = "bucket name (object) or POSIX mount path (block/file)"
  value = var.paradigm == "object" ? (
    length(google_storage_bucket.obj) > 0 ? google_storage_bucket.obj[0].name : ""
    ) : var.paradigm == "block" ? var.mount_block : var.mount_file
}
