# Cyber-Soc-Chatbot

> **CISC 886 — Cloud Computing | Queen's University**
> End-to-end implementation of a cybersecurity SOC chat assistant — infrastructure, preprocessing, fine-tuning, and deployment.

---

## Folder Structure

```
Cyber-Soc-Chatbot/
├── README.md                          # This file
│
├── terraform/                         # AWS infrastructure as code
│   ├── main.tf                        # VPC, subnets, SGs, EC2, EMR, S3, IGW, NAT
│   ├── variables.tf                   # Configurable variables (netID, region, CIDRs)
│   └── outputs.tf                     # Prints resource IDs/names after apply
│
├── spark/                             # Apache Spark preprocessing (runs on AWS EMR)
│   ├── preprocess_witfoo.py           # PySpark pipeline — cleans & splits WitFoo dataset
│   └── generate_eda_figures.py        # Generates EDA figures (label dist., msg length, splits)
│
└── finetuning/                        # Fine-tuning, GGUF export, and model testing
    ├── finetune_tinyllama_qlora.py    # QLoRA fine-tuning — initial 10K training run
    ├── finetune_tinyllama_qlora_50K.py# QLoRA fine-tuning — final 50K training run
    ├── GGUF_Script.py                 # Exports fine-tuned LoRA adapter to GGUF format
    └── test_model.py                  # Tests fine-tuned model with sample cyber events
```

---

## Prerequisites

### Tools
| Tool | Version | Install |
|------|---------|---------|
| Python | ≥ 3.10 | [python.org](https://python.org) |
| AWS CLI | ≥ 2.x | `pip install awscli` |
| Terraform | ≥ 1.5 | [terraform.io](https://terraform.io) |
| Git | ≥ 2.x | [git-scm.com](https://git-scm.com) |
| Google Colab | — | [colab.research.google.com](https://colab.research.google.com) |

### AWS Setup
```bash
aws configure
# AWS Access Key ID:     <your-key>
# AWS Secret Access Key: <your-secret>
# Default region:        us-east-1
# Default output format: json
```

### Python Dependencies
```bash
pip install unsloth trl datasets transformers \
            bitsandbytes peft boto3 pyspark \
            matplotlib pandas numpy
```

---

## Module 1 — Terraform (Infrastructure)

Provisions the complete AWS infrastructure for the project using infrastructure-as-code.

**What it creates:**
- Custom VPC `25dtg4-vpc` (10.0.0.0/16) with public + private subnets
- Internet Gateway, NAT Gateway, route tables
- Security groups for EC2 (public) and EMR (private)
- S3 bucket `25dtg4-s3` with `/raw-data`, `/preprocessed`, `/model-gguf` folders
- EC2 instance `25dtg4-ec2` (g4dn.xlarge) with Elastic IP
- IAM roles for EC2 S3 access and EMR default roles

### Usage

```bash
cd terraform/

# 1. Initialise providers
terraform init

# 2. Preview changes
terraform plan -var="net_id=25dtg4" -var="region=us-east-1"

# 3. Apply infrastructure
terraform apply -var="net_id=25dtg4" -var="region=us-east-1"

# 4. Destroy when done (to avoid costs)
terraform destroy -var="net_id=25dtg4" -var="region=us-east-1"
```

### Key Variables (`variables.tf`)

| Variable | Default | Description |
|----------|---------|-------------|
| `net_id` | `25dtg4` | Queen's netID — prefixes all resource names |
| `region` | `us-east-1` | AWS deployment region |
| `vpc_cidr` | `10.0.0.0/16` | VPC CIDR block |
| `public_cidr` | `10.0.1.0/24` | Public subnet CIDR |
| `private_cidr` | `10.0.2.0/24` | Private subnet CIDR |
| `ec2_instance_type` | `g4dn.xlarge` | EC2 GPU instance type |
| `emr_instance_type` | `m5.xlarge` | EMR node instance type |
| `emr_node_count` | `3` | Number of EMR nodes (1 master + 2 core) |

### Outputs (`outputs.tf`)
After `terraform apply`, the following are printed:
- VPC ID, subnet IDs, security group IDs
- EC2 public IP (Elastic IP)
- S3 bucket name
- EMR cluster ID

---

## Module 2 — Spark Preprocessing

PySpark scripts designed to run as EMR steps on `25dtg4-emr`. Processes the raw WitFoo cybersecurity dataset into train/validation/test splits ready for fine-tuning.

### `preprocess_witfoo.py`

**Pipeline steps:**
1. Load raw CSV/JSON from `s3://25dtg4-s3/raw-data/`
2. Filter and clean records — drop nulls, normalise labels
3. Balance classes via undersampling (50K per class → 150K total)
4. Tokenise and format into instruction-tuning JSONL format:
   ```
   ### Instruction: ...
   ### Cybersecurity Event: ...
   ### Response: ...
   ```
5. Stratified train / validation / test split (90% / 5% / 5%)
6. Write output to `s3://25dtg4-s3/preprocessed/`

**Run locally:**
```bash
python spark/preprocess_witfoo.py \
  --input s3://25dtg4-s3/raw-data/ \
  --output s3://25dtg4-s3/preprocessed/
```

**Submit as EMR step:**
```bash
# Upload script
aws s3 cp spark/preprocess_witfoo.py s3://25dtg4-s3/scripts/

# Add step to running cluster
aws emr add-steps \
  --cluster-id <cluster-id> \
  --steps Type=Spark,Name="25dtg4-preprocess",\
ActionOnFailure=CONTINUE,\
Args=[s3://25dtg4-s3/scripts/preprocess_witfoo.py,\
--input,s3://25dtg4-s3/raw-data/,\
--output,s3://25dtg4-s3/preprocessed/]
```

---

### `generate_eda_figures.py`

Generates the 5 required EDA figures from the processed dataset and saves them as PNGs.

**Figures produced:**
| Figure | Description |
|--------|-------------|
| `fig1_label_before.png` | Label distribution before balancing (log scale) |
| `fig2_label_after.png` | Label distribution after balancing |
| `fig3_split_counts.png` | Train / validation / test sample counts per class |
| `fig4_msg_length.png` | Message length distribution (benign class) |
| `fig5_stratified_split.png` | Stacked horizontal bar — stratification confirmed |

**Run:**
```bash
python spark/generate_eda_figures.py \
  --input s3://25dtg4-s3/preprocessed/ \
  --output ./eda_figures/
```

---

## Module 3 — Fine-Tuning

All scripts use **Unsloth** for memory-efficient LoRA fine-tuning and are designed to run in **Google Colab with a T4 GPU**.

### `finetune_tinyllama_qlora.py` — Initial 10K Run

Exploratory training run on 10K samples to validate the pipeline and prompt format before scaling.

```bash
# In Colab:
python finetuning/finetune_tinyllama_qlora.py \
  --train_file train_10k.jsonl \
  --val_file validation_1k.jsonl \
  --output_dir outputs/cyber-soc-tinyllama-lora-10k
```

---

### `finetune_tinyllama_qlora_50K.py` — Final 50K Run

Full production training run. Trains TinyLlama-1.1B with QLoRA on 50K balanced cybersecurity SOC events.

```bash
# In Colab:
python finetuning/finetune_tinyllama_qlora_50K.py \
  --train_file train_50k.jsonl \
  --val_file validation_5k.jsonl \
  --output_dir outputs/cyber-soc-tinyllama-lora
```

**Hyperparameters:**

| Parameter | Value |
|-----------|-------|
| Base model | TinyLlama/TinyLlama-1.1B-Chat-v1.0 |
| LoRA rank (r) | 16 |
| LoRA alpha | 16 |
| LoRA dropout | 0.05 |
| Learning rate | 2e-4 |
| Batch size | 4 (effective 16 w/ grad accum.) |
| Epochs | 1 |
| Quantisation | 4-bit NF4 |
| Optimiser | AdamW 8-bit |
| Scheduler | Linear |
| Max seq length | 1024 |
| Final train loss | 0.2255 |
| Final val loss | 0.1658 |

---

### `GGUF_Script.py` — Export to GGUF

Converts the saved LoRA adapter into GGUF format for deployment with Ollama.

```bash
python finetuning/GGUF_Script.py \
  --adapter_path models/cyber-soc-tinyllama-lora \
  --output_path cyber-soc-tinyllama-gguf \
  --quantization q4_k_m
```

Then upload to S3:
```bash
aws s3 cp cyber-soc-tinyllama-gguf/ \
  s3://25dtg4-s3/model-gguf/ --recursive
```

---

### `test_model.py` — Local Model Testing

Tests the fine-tuned model against sample cybersecurity events before deploying to EC2. Runs inference locally using the saved LoRA adapter.

```bash
python finetuning/test_model.py \
  --adapter_path models/cyber-soc-tinyllama-lora \
  --prompt "Severity: 8\nAction: deny\nLifecycle stage: credential_access\nMatched rules: repeated_failed_login"
```

**Expected output format:**
```
Classification: Malicious
Risk level: High
Explanation: ...
Recommended action: ...
```

---

## Quick-Start: Full Pipeline

```bash
# 1. Clone repo
git clone https://github.com/25dtg4/cyber-soc-chatbot
cd Cyber-Soc-Chatbot

# 2. Provision infrastructure
cd terraform && terraform init && terraform apply -var="net_id=25dtg4"

# 3. Upload dataset to S3
aws s3 cp /path/to/dataset/ s3://25dtg4-s3/raw-data/ --recursive

# 4. Run preprocessing on EMR
aws s3 cp spark/preprocess_witfoo.py s3://25dtg4-s3/scripts/
aws emr add-steps --cluster-id <id> --steps ...   # see Module 2

# ⚠️ Terminate EMR cluster after step completes
aws emr terminate-clusters --cluster-ids <id>

# 5. Fine-tune in Colab (upload finetune_tinyllama_qlora_50K.py)
#    Then export GGUF and upload to S3

# 6. SSH to EC2 and deploy with Ollama
ssh -i keypair.pem ubuntu@<elastic-ip>
curl -fsSL https://ollama.com/install.sh | sh
aws s3 cp s3://25dtg4-s3/model-gguf/ ~/models/cyber-soc-tinyllama/ --recursive
cd ~/models/cyber-soc-tinyllama
ollama create 25dtg4-cyber-soc-assistant -f Modelfile
ollama list

# 7. Install and start OpenWebUI
pip install open-webui
sudo systemctl enable openwebui && sudo systemctl start openwebui
# Access at http://<elastic-ip>:3000
```

---

## Resource Naming

All AWS resources are prefixed with `25dtg4` per the CISC 886 naming policy:

| Resource | Name |
|----------|------|
| VPC | `25dtg4-vpc` |
| Public subnet | `25dtg4-public-subnet` |
| Private subnet | `25dtg4-private-subnet` |
| Internet Gateway | `25dtg4-igw` |
| Security group (public) | `25dtg4-sg-public` |
| Security group (private) | `25dtg4-sg-private` |
| EC2 instance | `25dtg4-ec2` |
| Elastic IP | `25dtg4-eip` |
| EMR cluster | `25dtg4-emr` |
| S3 bucket | `25dtg4-s3` |
| Ollama model | `25dtg4-cyber-soc-assistant` |
| IAM role | `25dtg4-ec2-s3-role` |

---

*CISC 886 — Cloud Computing | School of Computing, Queen's University, Kingston, Canada*