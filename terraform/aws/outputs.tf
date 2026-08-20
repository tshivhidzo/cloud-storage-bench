output "region" { value = var.region }
output "target" {
  description = "bucket name (object) or POSIX mount path (block/file)"
  value = var.paradigm == "object" ? (
            length(aws_s3_bucket.obj) > 0 ? aws_s3_bucket.obj[0].bucket : ""
          ) : var.paradigm == "block" ? var.mount_block : var.mount_file
}
