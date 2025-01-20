variable "pm_api_url" {
  description = "The Proxmox API URL"
  default     = "https://proxmox.laxdog.uk:8006/api2/json"
}

variable "pm_user" {
  description = "The Proxmox user"
  default     = "root@pam"
}

variable "pm_password" {
  description = "The Proxmox password"
}

variable "mac_pub_key" {
  description = "Public SSH key for M1 Mac"
  default     = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDssSyfnTaY3tROzt82F+jMxj8dgDcvezi0OKng56vjohiG6ntJYhq0hgzJRoJutPcAS0IikKcQOQcLLfoaocnVBU/pQG5hx4cJ4jAMcdz2HnBHPIIhgg7hLcdfWJqyqpP+bYZ3fmTo7RVxC6T6yftKLdWeoFHKm6SImKRRvZum0Hg4Bzrs2gh1mln8pCOJsUAmfPipBOzp18nWy8cnsJrWs4g6AUmHwaw6NACEPOZyy9EqX/vX16luEo08Ob70fBcFx1agBnM6dTWOfQIsK43Jk5pDcVhfIXbiD7kMe2tpzTCXDINlOsaFFI5Rxj+ire1/nLDP4BSPkqXsHJ8cApBl mrobinson@C02XF57UJG5J.corp.proofpoint.com"
}
