# 25dtg4 — Cybersecurity SOC Assistant
### CISC 886 Cloud Computing — Queen's University
**Student:** 25dtg4 | **Region:** us-east-1 | **Model:** TinyLlama-1.1B fine-tuned on cybersecurity SOC events

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Prerequisites](#prerequisites)
3. [Repository Structure](#repository-structure)
4. [Phase 1 — VPC & Networking Setup](#phase-1--vpc--networking-setup)
5. [Phase 2 — S3 Bucket Setup](#phase-2--s3-bucket-setup)
6. [Phase 3 — Data Preprocessing with EMR & Spark](#phase-3--data-preprocessing-with-emr--spark)
7. [Phase 4 — Model Fine-Tuning (Google Colab)](#phase-4--model-fine-tuning-google-colab)
8. [Phase 5 — Model Deployment on EC2](#phase-5--model-deployment-on-ec2)
9. [Phase 6 — Web Interface (OpenWebUI)](#phase-6--web-interface-openwebui)
10. [Cost Summary](#cost-summary)
11. [Resource Naming Reference](#resource-naming-reference)

---

## Project Overview

This project builds a complete end-to-end cloud-based cybersecurity SOC (Security Operations Centre) chat assistant on AWS. It covers:

- A custom **VPC** with public/private subnets, security groups, and routing
- A **dataset of 20M+ cybersecurity events** preprocessed with **Apache Spark on AWS EMR**
- **Parameter-efficient fine-tuning** (LoRA/QLoRA) of **TinyLlama-1.1B** using Unsloth on Google Colab
- Deployment of the fine-tuned model via **Ollama** on an **EC2 g4dn.xlarge** instance
- A live **OpenWebUI** chat interface accessible from a browser

---

## Prerequisites

### Tools Required
| Tool | Version | Purpose |
|------|---------|---------|
| AWS CLI | ≥ 2.x | Manage AWS resources from terminal |
| Python | ≥ 3.10 | PySpark scripts and fine-tuning |
| Git | ≥ 2.x | Clone this repository |
| Terraform | ≥ 1.5 | (Optional) VPC provisioning |
| Ollama | latest | LLM runner on EC2 |
| Google Colab | — | GPU environment for fine-tuning |
| pip | ≥ 23.x | Install Python packages |

### Accounts Required
- AWS account with access to **us-east-1** and permissions for: EC2, EMR, S3, VPC, IAM
- Google account (for Colab — free T4 GPU)
- HuggingFace account (to download base model)

### AWS Configuration
```bash
aws configure
# AWS Access Key ID:     <your-key>
# AWS Secret Access Key: <your-secret>
# Default region:        us-east-1
# Default output format: json
```

---

## Repository Structure

```text
Cyber-SOC-Chatbot/
├── README.md                                      # Main project documentation with setup, execution, and replication steps.
├── .gitignore                                     # Excludes virtual environments, caches, credentials, and large temporary files.
│
├── Cyber-Soc-Chatbot/                             # Main implementation folder for the AWS, Spark, fine-tuning, and deployment pipeline.
│   ├── README.md                                  # Additional project notes and execution details for the implementation folder.
│   │
│   ├── terraform/                                 # Terraform infrastructure-as-code for provisioning AWS resources.
│   │   ├── main.tf                                # Defines the custom VPC, subnets, security groups, S3 bucket, IAM roles, and EMR resources.
│   │   ├── variables.tf                           # Declares configurable variables such as netID, AWS region, key pair, and allowed IP CIDR.
│   │   └── outputs.tf                             # Prints useful AWS resource IDs and names after Terraform deployment.
│   │
│   ├── spark/                                     # Apache Spark preprocessing code used on AWS EMR.
│   │   ├── preprocess_witfoo.py                   # PySpark pipeline that converts the raw WitFoo cybersecurity dataset into instruction-tuning JSONL data.
│   │   └── generate_eda_figures.py                # Generates EDA figures such as label distribution, message length distribution, and split counts.
│   │
│   ├── finetuning/                                # Fine-tuning, model testing, and GGUF export scripts.
│   │   ├── finetune_tinyllama_qlora.py            # QLoRA fine-tuning script for the initial 10K training run.
│   │   ├── finetune_tinyllama_qlora_50K.py        # QLoRA fine-tuning script for the final 50K training run.
│   │   ├── GGUF_Script.py                         # Exports the fine-tuned LoRA adapter to GGUF format for Ollama deployment.
│   │   └── test_model.py                          # Tests the fine-tuned model locally using sample cybersecurity prompts.
│
├── cyber-soc-tinyllama-lora-10k/                  # LoRA adapter from the initial 10K-sample fine-tuning validation run.
│   ├── adapter_config.json                        # Configuration describing the LoRA adapter architecture and settings.
│   ├── adapter_model.safetensors                  # Fine-tuned LoRA adapter weights from the 10K run.
│   ├── chat_template.jinja                        # Chat template used by the tokenizer during inference.
│   ├── special_tokens_map.json                    # Mapping of special tokens required by the tokenizer.
│   ├── tokenizer.json                             # Tokenizer vocabulary and processing configuration.
│   ├── tokenizer.model                            # Tokenizer model file.
│   ├── tokenizer_config.json                      # Tokenizer metadata and settings.
│   └── README.md                                  # Auto-generated adapter metadata file.
│
└── cyber-soc-tinyllama-lora-50k/                  # Final LoRA adapter trained on the 50K dataset and used for deployment.
    ├── adapter_config.json                        # Configuration describing the final LoRA adapter.
    ├── adapter_model.safetensors                  # Final fine-tuned LoRA adapter weights.
    ├── chat_template.jinja                        # Chat formatting template used for the final model.
    ├── special_tokens_map.json                    # Special token mapping for the final tokenizer.
    ├── tokenizer.json                             # Tokenizer vocabulary and processing configuration.
    ├── tokenizer.model                            # Tokenizer model file.
    ├── tokenizer_config.json                      # Tokenizer metadata and settings.
    └── README.md                                  # Auto-generated metadata for the final adapter.
```

---

## Phase 1 — VPC & Networking Setup

### Option A: AWS Console
1. Go to **VPC → Create VPC**
2. Set CIDR: `10.0.0.0/16`, Name: `25dtg4-vpc`
3. Create **public subnet**: `10.0.1.0/24`, Name: `25dtg4-public-subnet`
4. Create **private subnet**: `10.0.2.0/24`, Name: `25dtg4-private-subnet`
5. Create **Internet Gateway**: `25dtg4-igw` → attach to `25dtg4-vpc`
6. Create **route table**: `25dtg4-rt-public` → add route `0.0.0.0/0 → 25dtg4-igw`
7. Associate public subnet with `25dtg4-rt-public`

### Option B: Terraform
```bash
cd vpc/
terraform init
terraform plan
terraform apply
```

### Security Groups
```bash
# Public security group (EC2, OpenWebUI, Ollama)
aws ec2 create-security-group \
  --group-name 25dtg4-sg-public \
  --description "Public SG for EC2" \
  --vpc-id <vpc-id>

# Allow SSH (your IP only)
aws ec2 authorize-security-group-ingress \
  --group-id <sg-id> --protocol tcp --port 22 \
  --cidr <your-ip>/32

# Allow OpenWebUI
aws ec2 authorize-security-group-ingress \
  --group-id <sg-id> --protocol tcp --port 3000 --cidr 0.0.0.0/0

# Allow Ollama API
aws ec2 authorize-security-group-ingress \
  --group-id <sg-id> --protocol tcp --port 11434 --cidr 0.0.0.0/0

# Private security group (EMR — no internet inbound)
aws ec2 create-security-group \
  --group-name 25dtg4-sg-private \
  --description "Private SG for EMR" \
  --vpc-id <vpc-id>
```

---

## Phase 2 — S3 Bucket Setup

```bash
# Create bucket
aws s3 mb s3://25dtg4-s3 --region us-east-1

# Create folder structure
aws s3api put-object --bucket 25dtg4-s3 --key raw-data/
aws s3api put-object --bucket 25dtg4-s3 --key preprocessed/
aws s3api put-object --bucket 25dtg4-s3 --key model-gguf/

# Upload raw dataset
aws s3 cp /path/to/your/dataset.csv s3://25dtg4-s3/raw-data/

# Upload base model (from HuggingFace)
# Download first: huggingface-cli download TinyLlama/TinyLlama-1.1B-Chat-v1.0
aws s3 cp ./TinyLlama-1.1B-Chat-v1.0/ s3://25dtg4-s3/raw-data/base-model/ --recursive
```

---

## Phase 3 — Data Preprocessing with EMR & Spark

### 3.1 Launch EMR Cluster

```bash
aws emr create-cluster \
  --name "25dtg4-emr" \
  --release-label emr-6.15.0 \
  --instance-type m5.xlarge \
  --instance-count 3 \
  --ec2-attributes SubnetId=<private-subnet-id>,KeyName=<your-keypair> \
  --use-default-roles \
  --applications Name=Spark \
  --region us-east-1
```

### 3.2 Upload PySpark Script

```bash
aws s3 cp preprocessing/25dtg4_pyspark_preprocessing.py \
  s3://25dtg4-s3/scripts/
```

### 3.3 Submit Spark Job

```bash
aws emr add-steps \
  --cluster-id <cluster-id> \
  --steps Type=Spark,Name="25dtg4-preprocessing",\
ActionOnFailure=CONTINUE,\
Args=[s3://25dtg4-s3/scripts/25dtg4_pyspark_preprocessing.py,\
--input,s3://25dtg4-s3/raw-data/,\
--output,s3://25dtg4-s3/preprocessed/]
```

### 3.4 Verify Output

```bash
aws s3 ls s3://25dtg4-s3/preprocessed/
```

### 3.5 Terminate Cluster (REQUIRED)

```bash
aws emr terminate-clusters --cluster-ids <cluster-id>

# Verify terminated state
aws emr describe-cluster --cluster-id <cluster-id> \
  --query 'Cluster.Status.State'
```

> ⚠️ **Critical:** Always terminate the EMR cluster after the job completes to avoid depleting the shared account budget.

---

## Phase 4 — Model Fine-Tuning (Google Colab)

### 4.1 Environment Setup

Open `fine_tuning/finetune_tinyllama_qlora_V2.py` in **Google Colab** with a **T4 GPU** runtime.

```bash
# Install dependencies
pip install unsloth trl datasets transformers bitsandbytes peft
```

### 4.2 Download Preprocessed Data from S3

```python
import boto3
s3 = boto3.client('s3')
s3.download_file('25dtg4-s3', 'preprocessed/train_50k.jsonl',  'train_50k.jsonl')
s3.download_file('25dtg4-s3', 'preprocessed/validation_5k.jsonl', 'validation_5k.jsonl')
```

### 4.3 Run Fine-Tuning

```bash
python finetune_tinyllama_qlora_V2.py
```

**Key hyperparameters:**

| Parameter | Value |
|-----------|-------|
| Base model | TinyLlama/TinyLlama-1.1B-Chat-v1.0 |
| Method | LoRA (PEFT) |
| LoRA rank (r) | 16 |
| LoRA alpha | 16 |
| Learning rate | 2e-4 |
| Batch size | 4 (effective: 16 with grad accum.) |
| Epochs | 1 |
| Quantisation | 4-bit NF4 |
| Optimiser | AdamW 8-bit |
| Max seq length | 1024 |

### 4.4 Export to GGUF

```python
# In Colab, after training completes:
model.save_pretrained_gguf(
    "cyber-soc-tinyllama-gguf",
    tokenizer,
    quantization_method="q4_k_m"
)
```

### 4.5 Upload GGUF to S3

```bash
aws s3 cp cyber-soc-tinyllama-gguf/ \
  s3://25dtg4-s3/model-gguf/ --recursive
```

---

## Phase 5 — Model Deployment on EC2

### 5.1 Launch EC2 Instance

```bash
aws ec2 run-instances \
  --image-id ami-0c02fb55956c7d316 \
  --instance-type g4dn.xlarge \
  --key-name <your-keypair> \
  --security-group-ids <25dtg4-sg-public-id> \
  --subnet-id <public-subnet-id> \
  --iam-instance-profile Name=25dtg4-ec2-s3-role \
  --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":100,"VolumeType":"gp3"}}]' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=25dtg4-ec2}]'
```

### 5.2 Allocate and Attach Elastic IP

```bash
ALLOC=$(aws ec2 allocate-address --domain vpc --query AllocationId --output text)
aws ec2 associate-address --instance-id <instance-id> --allocation-id $ALLOC
aws ec2 create-tags --resources $ALLOC --tags Key=Name,Value=25dtg4-eip
```

### 5.3 SSH into Instance

```bash
ssh -i <your-keypair.pem> ubuntu@<elastic-ip>
```

### 5.4 Install Ollama

```bash
curl -fsSL https://ollama.com/install.sh | sh
systemctl status ollama
```

### 5.5 Pull Model from S3

```bash
aws s3 cp s3://25dtg4-s3/model-gguf/ \
  ~/models/cyber-soc-tinyllama/ --recursive
```

### 5.6 Create Modelfile

```bash
cat > ~/models/cyber-soc-tinyllama/Modelfile << 'EOF'
FROM ./cyber-soc-tinyllama.gguf
PARAMETER temperature 0.1
PARAMETER num_ctx 1024
PARAMETER num_predict 120
SYSTEM "You are a cybersecurity SOC analyst assistant. Analyze security events and provide structured triage assessments."
EOF
```

### 5.7 Register Model with Ollama

```bash
cd ~/models/cyber-soc-tinyllama
ollama create 25dtg4-cyber-soc-assistant -f Modelfile
ollama list   # verify: 25dtg4-cyber-soc-assistant:latest should appear
```

### 5.8 Enable Ollama Auto-Start

```bash
sudo systemctl enable ollama
sudo systemctl start ollama
sudo systemctl status ollama
```

### 5.9 Test via curl

```bash
curl -s http://localhost:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "25dtg4-cyber-soc-assistant",
    "prompt": "### Instruction:\nAnalyze the following cybersecurity event and provide a SOC triage assessment.\n\n### Cybersecurity Event:\nSeverity: 8\nAction: deny\nLifecycle stage: credential_access\nMatched rules: repeated_failed_login\nMessage: Multiple failed login attempts from a single source to an admin account.\n\n### Response:\n",
    "stream": false,
    "options": { "num_predict": 120, "temperature": 0.1, "num_ctx": 1024 }
  }'
```

---

## Phase 6 — Web Interface (OpenWebUI)

### 6.1 Install OpenWebUI

```bash
pip install open-webui
```

### 6.2 Create systemd Service (auto-start on reboot)

```bash
sudo tee /etc/systemd/system/openwebui.service << 'EOF'
[Unit]
Description=OpenWebUI Chat Interface
After=network.target ollama.service

[Service]
ExecStart=/usr/local/bin/open-webui serve --host 0.0.0.0 --port 3000
Restart=always
User=ubuntu
Environment=OLLAMA_BASE_URL=http://localhost:11434

[Install]
WantedBy=multi-user.target
EOF
```

### 6.3 Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable openwebui
sudo systemctl start openwebui
sudo systemctl status openwebui
```

### 6.4 Access the Interface

Open your browser and navigate to:

```
http://<elastic-ip>:3000
```

1. Register an account on first visit
2. Select model: `25dtg4-cyber-soc-assistant:latest`
3. Start chatting with the fine-tuned SOC assistant

### 6.5 Verify Both Services Survive Reboot

```bash
sudo reboot
# After reboot:
sudo systemctl status ollama
sudo systemctl status openwebui
```

---

## Cost Summary

| AWS Service | Configuration | Est. Cost |
|-------------|--------------|-----------|
| **EC2** | g4dn.xlarge, ~10 hrs | ~$5.20 |
| **EMR** | 3× m5.xlarge, ~2 hrs | ~$1.40 |
| **S3** | ~5 GB storage + requests | ~$0.15 |
| **NAT Gateway** | ~2 hrs data processing | ~$0.20 |
| **Elastic IP** | Attached (no charge while in use) | $0.00 |
| **Data Transfer** | S3 ↔ EMR (same region) | $0.00 |
| **Total** | | **~$6.95** |

> 💡 Costs are approximate and based on on-demand us-east-1 pricing. EMR and EC2 clusters were terminated immediately after use to minimise spend.

---

## Resource Naming Reference

All AWS resources are prefixed with `25dtg4` per the course naming policy:

| Resource | Name |
|----------|------|
| VPC | `25dtg4-vpc` |
| Public subnet | `25dtg4-public-subnet` |
| Private subnet | `25dtg4-private-subnet` |
| Internet Gateway | `25dtg4-igw` |
| Route table | `25dtg4-rt-public` |
| Security group (public) | `25dtg4-sg-public` |
| Security group (private) | `25dtg4-sg-private` |
| EC2 instance | `25dtg4-ec2` |
| Elastic IP | `25dtg4-eip` |
| EMR cluster | `25dtg4-emr` |
| S3 bucket | `25dtg4-s3` |
| Ollama model | `25dtg4-cyber-soc-assistant` |
| IAM role (EC2) | `25dtg4-ec2-s3-role` |

---

## Troubleshooting

**Ollama not responding:**
```bash
sudo systemctl restart ollama
curl http://localhost:11434/api/tags
```

**OpenWebUI can't reach Ollama:**
```bash
# Check env variable
systemctl show openwebui | grep Environment
# Should show: OLLAMA_BASE_URL=http://localhost:11434
```

**EMR step failing:**
```bash
aws emr list-steps --cluster-id <cluster-id>
aws s3 cp s3://25dtg4-s3/logs/ ./logs/ --recursive
```

**Out of GPU memory during fine-tuning:**
- Reduce `per_device_train_batch_size` to `2`
- Reduce `MAX_SEQ_LENGTH` to `512`
- Ensure `load_in_4bit=True` is set

---

*CISC 886 — Cloud Computing | School of Computing, Queen's University, Kingston, Canada*