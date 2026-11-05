output "resource_group_name" {
  value = azurerm_resource_group.rg.name
}

output "acr_login_server" {
  value = module.acr.acr_login_server
}

output "aks_cluster_name" {
  value = module.aks.cluster_name
}

output "kube_config" {
  value     = module.aks.kube_config
  sensitive = true
}
