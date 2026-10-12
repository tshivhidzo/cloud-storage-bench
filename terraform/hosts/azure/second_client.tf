# Second client host for the v2.1 rerun. On Azure it is used only as the
# iperf3 server for the network baseline (Azure object runs use the SDK
# runner, which has no multi-host mode). Intra-VNet traffic is allowed by
# Azure's default AllowVnetInBound rule, so no extra NSG rule is needed.
variable "second_client" {
  type    = bool
  default = false
}

resource "azurerm_public_ip" "csb2" {
  count               = var.second_client ? 1 : 0
  name                = "csb-bench-pip2"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_network_interface" "csb2" {
  count               = var.second_client ? 1 : 0
  name                = "csb-bench-nic2"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.csb.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.csb2[0].id
  }
}

resource "azurerm_linux_virtual_machine" "host2" {
  count                 = var.second_client ? 1 : 0
  name                  = "csb-bench-host2-azure"
  location              = azurerm_resource_group.csb.location
  resource_group_name   = azurerm_resource_group.csb.name
  size                  = var.vm_size
  admin_username        = "ubuntu"
  network_interface_ids = [azurerm_network_interface.csb2[0].id]
  admin_ssh_key {
    username   = "ubuntu"
    public_key = var.ssh_public_key
  }
  os_disk {
    caching              = "ReadWrite"
    storage_account_type = "Premium_LRS"
    disk_size_gb         = var.root_gb
  }
  source_image_reference {
    publisher = "Canonical"
    offer     = "0001-com-ubuntu-server-jammy"
    sku       = "22_04-lts-gen2"
    version   = "latest"
  }
  custom_data = base64encode(templatefile(
    "${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
      AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
      ELBENCHO_VERSION    = var.elbencho_version
  }))
  tags = { Project = "cloud-storage-bench" }
}

output "host_private_ip"  { value = azurerm_network_interface.csb.private_ip_address }
output "host2_ip"         { value = join("", azurerm_public_ip.csb2[*].ip_address) }
output "host2_private_ip" { value = join("", azurerm_network_interface.csb2[*].private_ip_address) }
