project_name          = "hams"
environment           = "prod"
location              = "eastus2"
aks_system_node_count = 5
aks_vm_size           = "Standard_D8s_v5"
acr_sku               = "Premium"
tags = {
  Environment = "Production"
  Project     = "Highly Available AI Microservices"
  Compliance  = "SOC2"
}
