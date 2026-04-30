output "bucket_name" {
  value = aws_s3_bucket.project_bucket.bucket
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_a" {
  value = aws_subnet.public_a.id
}

output "public_subnet_b" {
  value = aws_subnet.public_b.id
}

output "ec2_security_group_id" {
  value = aws_security_group.ec2_sg.id
}

output "emr_security_group_id" {
  value = aws_security_group.emr_sg.id
}

output "emr_service_role" {
  value = aws_iam_role.emr_service_role.name
}

output "emr_ec2_instance_profile" {
  value = aws_iam_instance_profile.emr_instance_profile.name
}

output "emr_cluster_id" {
  value = aws_emr_cluster.spark_cluster.id
}

output "emr_cluster_name" {
  value = aws_emr_cluster.spark_cluster.name
}

output "emr_master_public_dns" {
  value = aws_emr_cluster.spark_cluster.master_public_dns
}