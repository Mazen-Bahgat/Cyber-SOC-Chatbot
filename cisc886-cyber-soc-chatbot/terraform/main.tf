terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_s3_bucket" "project_bucket" {
  bucket = "${var.netid}-cisc886-cyber-soc"

  tags = {
    Name    = "${var.netid}-cisc886-cyber-soc"
    Project = "CISC886"
  }
}

resource "aws_s3_bucket_versioning" "versioning" {
  bucket = aws_s3_bucket.project_bucket.id

  versioning_configuration {
    status = "Suspended"
  }
}

resource "aws_vpc" "main" {
  cidr_block           = "10.86.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.netid}-vpc"
  }
}

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.netid}-igw"
  }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.86.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.netid}-public-subnet-a"
  }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.86.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.netid}-public-subnet-b"
  }
}

resource "aws_route_table" "public_rt" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.netid}-public-rt"
  }
}

resource "aws_route" "public_internet_route" {
  route_table_id         = aws_route_table.public_rt.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

resource "aws_route_table_association" "public_a_assoc" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_route_table_association" "public_b_assoc" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public_rt.id
}

resource "aws_security_group" "ec2_sg" {
  name        = "${var.netid}-ec2-sg"
  description = "Security group for LLM EC2 deployment"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH from my IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "OpenWebUI from my IP only"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "Ollama API from my IP only for testing"
    from_port   = 11434
    to_port     = 11434
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  egress {
    description = "Allow outbound internet access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.netid}-ec2-sg"
  }
}

resource "aws_security_group" "emr_sg" {
  name        = "${var.netid}-emr-sg"
  description = "Security group for EMR cluster"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "SSH to EMR from my IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }

  ingress {
    description = "Allow internal traffic inside VPC"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.86.0.0/16"]
  }

  egress {
    description = "Allow EMR outbound internet and S3 access"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.netid}-emr-sg"
  }
}

resource "aws_iam_role" "emr_service_role" {
  name = "${var.netid}-emr-service-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "elasticmapreduce.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_service_policy" {
  role       = aws_iam_role.emr_service_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceRole"
}

resource "aws_iam_role" "emr_ec2_role" {
  name = "${var.netid}-emr-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = {
        Service = "ec2.amazonaws.com"
      },
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "emr_ec2_policy" {
  role       = aws_iam_role.emr_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonElasticMapReduceforEC2Role"
}

resource "aws_iam_role_policy_attachment" "emr_ec2_s3_policy" {
  role       = aws_iam_role.emr_ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

resource "aws_iam_instance_profile" "emr_instance_profile" {
  name = "${var.netid}-emr-ec2-instance-profile"
  role = aws_iam_role.emr_ec2_role.name
}

# -----------------------------
# EMR Spark Cluster
# -----------------------------

resource "aws_emr_cluster" "spark_cluster" {
  name          = "${var.netid}-emr-cluster"
  release_label = "emr-7.13.0"
  applications  = ["Hadoop", "Spark"]

  service_role = aws_iam_role.emr_service_role.arn

  ec2_attributes {
    subnet_id                         = aws_subnet.public_a.id
    emr_managed_master_security_group = aws_security_group.emr_sg.id
    emr_managed_slave_security_group  = aws_security_group.emr_sg.id
    instance_profile                  = aws_iam_instance_profile.emr_instance_profile.arn
    key_name                          = var.key_name
  }

  master_instance_group {
    name           = "${var.netid}-emr-master"
    instance_type  = "m5.xlarge"
    instance_count = 1
  }

  core_instance_group {
    name           = "${var.netid}-emr-core"
    instance_type  = "m5.xlarge"
    instance_count = 1

    ebs_config {
      size                 = 30
      type                 = "gp3"
      volumes_per_instance = 1
    }
  }

  ebs_root_volume_size = 30

  log_uri = "s3://${aws_s3_bucket.project_bucket.bucket}/logs/emr/"

  keep_job_flow_alive_when_no_steps = true
  termination_protection            = false
  visible_to_all_users              = true

  tags = {
    Name    = "${var.netid}-emr-cluster"
    Project = "CISC886"
  }

  depends_on = [
    aws_iam_role_policy_attachment.emr_service_policy,
    aws_iam_role_policy_attachment.emr_ec2_policy,
    aws_iam_role_policy_attachment.emr_ec2_s3_policy,
    aws_route_table_association.public_a_assoc
  ]
}