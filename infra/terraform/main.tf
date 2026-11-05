terraform {
  required_version = ">= 1.5.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.80"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "rg" {
  name     = "${var.project_name}-${var.environment}-rg"
  location = var.location
  tags     = var.tags
}

module "networking" {
  source              = "./modules/networking"
  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

module "monitoring" {
  source              = "./modules/monitoring"
  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  tags                = var.tags
}

module "acr" {
  source              = "./modules/acr"
  project_name        = var.project_name
  environment         = var.environment
  location            = var.location
  resource_group_name = azurerm_resource_group.rg.name
  acr_sku             = var.acr_sku
  tags                = var.tags
}

module "aks" {
  source                     = "./modules/aks"
  project_name               = var.project_name
  environment                = var.environment
  location                   = var.location
  resource_group_name        = azurerm_resource_group.rg.name
  node_count                 = var.aks_system_node_count
  vm_size                    = var.aks_vm_size
  vnet_subnet_id             = module.networking.aks_subnet_id
  acr_id                     = module.acr.acr_id
  log_analytics_workspace_id = module.monitoring.workspace_id
  tags                       = var.tags
}
