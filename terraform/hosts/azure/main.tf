terraform {
  required_providers {
    azurerm = { source = "hashicorp/azurerm", version = "~> 3.0" }
    random  = { source = "hashicorp/random", version = "~> 3.0" }
  }
}
provider "azurerm" {
  features {}
}

data "azurerm_subscription" "current" {}

resource "random_string" "s" {
  length  = 6
  upper   = false
  special = false
}
resource "azurerm_resource_group" "csb" {
  name     = var.resource_group
  location = var.region
}

# ---------------------- Dedicated VNet ----------------------
resource "azurerm_virtual_network" "csb" {
  name                = "csb-bench-vnet"
  address_space       = ["10.43.0.0/16"]
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
}
resource "azurerm_subnet" "csb" {
  name                 = "csb-bench-subnet"
  resource_group_name  = azurerm_resource_group.csb.name
  virtual_network_name = azurerm_virtual_network.csb.name
  address_prefixes     = ["10.43.1.0/24"]
  service_endpoints    = ["Microsoft.Storage"]
}
resource "azurerm_network_security_group" "csb" {
  name                = "csb-bench-nsg"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
  security_rule {
    name                       = "SSHFromOperator"
    priority                   = 100
    direction                  = "Inbound"
    access                     = "Allow"
    protocol                   = "Tcp"
    source_port_range          = "*"
    destination_port_range     = "22"
    source_address_prefix      = var.operator_cidr
    destination_address_prefix = "*"
  }
}
resource "azurerm_subnet_network_security_group_association" "csb" {
  subnet_id                 = azurerm_subnet.csb.id
  network_security_group_id = azurerm_network_security_group.csb.id
}
resource "azurerm_public_ip" "csb" {
  name                = "csb-bench-pip"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
  allocation_method   = "Static"
  sku                 = "Standard"
}
resource "azurerm_network_interface" "csb" {
  name                = "csb-bench-nic"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
  ip_configuration {
    name                          = "internal"
    subnet_id                     = azurerm_subnet.csb.id
    private_ip_address_allocation = "Dynamic"
    public_ip_address_id          = azurerm_public_ip.csb.id
  }
}

# ------------- Managed identity (no long-lived keys on the host) -------------
resource "azurerm_user_assigned_identity" "csb" {
  name                = "csb-bench-identity"
  location            = azurerm_resource_group.csb.location
  resource_group_name = azurerm_resource_group.csb.name
}
# Scoped to the benchmark resource group only -- not the subscription.
resource "azurerm_role_assignment" "rg_contributor" {
  scope                = azurerm_resource_group.csb.id
  role_definition_name = "Contributor" # create/delete disks + file shares in this RG
  principal_id         = azurerm_user_assigned_identity.csb.principal_id
}
resource "azurerm_role_assignment" "blob_data" {
  scope                = azurerm_resource_group.csb.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.csb.principal_id
}

# ------------------------------ The host -------------------------------------
resource "azurerm_linux_virtual_machine" "host" {
  name                  = "csb-bench-host-azure"
  location              = azurerm_resource_group.csb.location
  resource_group_name   = azurerm_resource_group.csb.name
  size                  = var.vm_size
  admin_username        = "ubuntu"
  network_interface_ids = [azurerm_network_interface.csb.id]
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
  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.csb.id]
  }
  custom_data = base64encode(templatefile(
    "${path.module}/../../../scripts/cloudinit/bootstrap_host.sh", {
      AUTO_SHUTDOWN_HOURS = var.auto_shutdown_hours
      ELBENCHO_VERSION    = var.elbencho_version
  }))
  tags = { Project = "cloud-storage-bench" }
}
