variable "netid" {
  description = "Queen's netID prefix for all resources"
  type        = string
}

variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "my_ip_cidr" {
  description = "Your public IP address in CIDR format, e.g. 142.1.2.3/32"
  type        = string
}

variable "key_name" {
  description = "Existing EC2 key pair name"
  type        = string
}