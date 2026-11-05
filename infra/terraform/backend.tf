# Azure Blob Storage remote backend configuration for Terraform State
# terraform {
#   backend "azurerm" {
#     resource_group_name  = "hams-tfstate-rg"
#     storage_account_name = "hamstfstatestore"
#     container_name       = "tfstate"
#     key                  = "hams.terraform.tfstate"
#   }
# }
