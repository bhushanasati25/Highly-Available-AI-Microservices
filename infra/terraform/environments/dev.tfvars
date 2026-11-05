project_name          = "hams"
environment           = "dev"
location              = "eastus2"
aks_system_node_count = 2
aks_vm_size           = "Standard_D4s_v5"
acr_sku               = "Standard"
tags = {
  Environment = "Development"
  Project     = "Highly Available AI Microservices"
}
