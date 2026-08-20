output "host_ip"  { value = azurerm_public_ip.csb.ip_address }
output "region"   { value = var.region }
output "locality" { value = "local" } # southafricanorth is in South Africa
output "ssh"      { value = "ssh ubuntu@${azurerm_public_ip.csb.ip_address}" }
output "ready_check" {
  value = "ssh ubuntu@${azurerm_public_ip.csb.ip_address} 'ls /var/lib/csb-bootstrap-complete && elbencho --version'"
}

# For MSI auth on the host: paste into the host shell (see host_env_setup).
output "host_env_setup" {
  description = "run this ON the host so terraform + the runners use the managed identity"
  value       = <<-EOT
    cat >> ~/.bashrc <<'ENV'
    export ARM_USE_MSI=true
    export ARM_SUBSCRIPTION_ID=${data.azurerm_subscription.current.subscription_id}
    export ARM_TENANT_ID=${data.azurerm_subscription.current.tenant_id}
    export ARM_CLIENT_ID=${azurerm_user_assigned_identity.csb.client_id}
    ENV
    source ~/.bashrc
  EOT
}
