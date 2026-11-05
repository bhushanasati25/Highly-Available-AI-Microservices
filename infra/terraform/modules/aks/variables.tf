variable "project_name" { type = string }
variable "environment" { type = string }
variable "location" { type = string }
variable "resource_group_name" { type = string }
variable "node_count" { type = number default = 3 }
variable "vm_size" { type = string default = "Standard_D4s_v5" }
variable "vnet_subnet_id" { type = string }
variable "acr_id" { type = string }
variable "log_analytics_workspace_id" { type = string }
variable "tags" { type = map(string) }
