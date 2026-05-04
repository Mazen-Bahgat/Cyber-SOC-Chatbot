# CISC 886 Cybersecurity SOC Chatbot

## Project Overview

This project builds a cloud-based cybersecurity SOC alert triage chatbot. The system processes the WitFoo Precinct6 Cybersecurity 100M dataset using Apache Spark on AWS EMR, converts structured security events into instruction-tuning examples, fine-tunes a lightweight LLM using QLoRA, and deploys the model on AWS EC2 using Ollama and OpenWebUI.

## Resource Naming

All AWS resources are prefixed with my Queen's netID:

- q1abc-vpc
- q1abc-cisc886-cyber-soc
- q1abc-emr-sg
- q1abc-ec2-sg
- q1abc-llm-ec2

## Architecture

1. Raw dataset is stored in S3.
2. EMR Spark reads the raw Parquet files.
3. Spark filters, balances, and converts records into instruction-tuning JSONL.
4. Processed train/validation/test files are written back to S3.
5. A lightweight model is fine-tuned using QLoRA.
6. The model is exported to GGUF and uploaded to S3.
7. EC2 runs Ollama as the LLM runner.
8. OpenWebUI provides the browser chat interface.

## Prerequisites

- AWS CLI configured
- Terraform installed
- Python 3.10+
- Hugging Face account/token
- EC2 key pair
- Docker for deployment

## AWS Setup

```bash
export NETID="q1abc"
export AWS_REGION="us-east-1"
export BUCKET="${NETID}-cisc886-cyber-soc"
export KEY_NAME="${NETID}-cisc886-key"
export MY_IP="YOUR_PUBLIC_IP/32"