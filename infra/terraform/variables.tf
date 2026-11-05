variable "project_name" {
  type        = string
  default     = "hams"
  description = "Project prefix for resource naming"
}

variable "environment" {
  type        = string
  default     = "dev"
  description = "Target deployment environment (dev, staging, prod)"
}

variable "location" {
  type        = string
  default     = "eastus2"
  description = "Azure region"
}

variable "aks_system_node_count" {
  type        = number
  default     = 3
  description = "System node pool VM count"
}

variable "aks_vm_size" {
  type        = string
  default     = "Standard_D4s_v5"
  description = "VM size for Kubernetes nodes"
}

variable "acr_sku" {
  type        = string
  default     = "Premium"
  description = "SKU for Azure Container Registry"
}

variable "tags" {
  type        = map(string)
  default = {
    Project     = "Highly Available AI Microservices"
    ManagedBy   = "Terraform"
    Environment = "Production"
  }
}
