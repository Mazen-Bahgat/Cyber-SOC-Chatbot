# Cyber-SOC-Chatbot

End-to-end cloud-based cybersecurity SOC chatbot for **CISC 886 – Cloud Computing**. This repository provisions AWS networking infrastructure, preprocesses a cybersecurity dataset with Apache Spark on AWS EMR, fine-tunes a lightweight LLM with QLoRA/PEFT, exports the tuned model to GGUF, serves it with Ollama on EC2, and exposes it through OpenWebUI.

## Repository Structure

```text
Cyber-Soc-Chatbot/
├── README.md                  # End-to-end replication guide
├── terraform/                                 # Terraform infrastructure-as-code for provisioning AWS resources.
│   ├── main.tf                                # Defines the custom VPC, subnets, security groups, S3 bucket, IAM roles, and EMR resources.
│   ├── variables.tf                           # Declares configurable variables such as netID, AWS region, key pair, and allowed IP CIDR.
│   └── outputs.tf                             # Prints useful AWS resource IDs and names after Terraform deployment.
│
├── spark/                                     # Apache Spark preprocessing code used on AWS EMR.
│   ├── preprocess_witfoo.py                   # PySpark pipeline that converts the raw WitFoo cybersecurity dataset into instruction-tuning JSONL data.
│   └── generate_eda_figures.py                # Generates EDA figures such as label distribution, message length distribution, and split counts.
│   
└── finetuning/                                # Fine-tuning, model testing, and GGUF export scripts.
    ├── finetune_tinyllama_qlora.py            # QLoRA fine-tuning script for the initial 10K training run.
    ├── finetune_tinyllama_qlora_50K.py        # QLoRA fine-tuning script for the final 50K training run.
    ├── GGUF_Script.py                         # Exports the fine-tuned LoRA adapter to GGUF format for Ollama deployment.
    └── test_model.py                          # Tests the fine-tuned model locally using sample cybersecurity prompts.
```

## System Overview

The project pipeline is:

```text
Raw cybersecurity dataset
        |
        v
Amazon S3 raw-data prefix
        |
        v
AWS EMR + PySpark preprocessing
        |
        v
Amazon S3 processed train/validation/test JSONL files
        |
        v
TinyLlama QLoRA/PEFT fine-tuning
        |
        v
Fine-tuned adapter + merged model artifacts
        |
        v
GGUF export
        |
        v
EC2 + Ollama model serving
        |
        v
OpenWebUI browser chat interface
```

## Prerequisites

### Required accounts and access

- AWS account access with permissions for VPC, EC2, EMR, S3, IAM, CloudWatch, and security groups.
- Hugging Face account and token if the selected model or dataset requires authentication.
- Queen's NetID for AWS resource naming.

### Required local tools

Install these on your local machine or development VM:

- Git
- AWS CLI v2
- Terraform 1.5+
- Python 3.10+
- Docker
- SSH client

Optional but recommended:

- Google Colab with GPU runtime for low-cost QLoRA fine-tuning.
- `jq` for reading AWS CLI JSON output.

## Required Environment Variables

Set these values before running the commands below. Replace `q1abc` with your Queen's NetID.

```bash
export NETID="q1abc"
export AWS_REGION="us-east-1"
export PROJECT_NAME="cyber-soc-chatbot"
export S3_BUCKET="${NETID}-${PROJECT_NAME}"
export KEY_NAME="${NETID}-${PROJECT_NAME}-key"
export BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
export LOCAL_DATA_DIR="./data"
export LOCAL_OUTPUT_DIR="./outputs"
```

All AWS resources created for this project should start with `${NETID}-`.

## 1. Clone the Repository

```bash
git clone https://github.com/<your-github-username>/Cyber-Soc-Chatbot.git
cd Cyber-Soc-Chatbot
```

Check the top-level structure:

```bash
ls -la
ls -la terraform spark finetuning
```

## 2. Configure AWS CLI

```bash
aws configure
aws sts get-caller-identity
aws configure set region "${AWS_REGION}"
```

Confirm the active region:

```bash
aws configure get region
```

## 3. Create the S3 Bucket

Create the project bucket:

```bash
aws s3 mb "s3://${S3_BUCKET}" --region "${AWS_REGION}"
```

Create the expected folder layout:

```bash
aws s3api put-object --bucket "${S3_BUCKET}" --key raw/
aws s3api put-object --bucket "${S3_BUCKET}" --key processed/
aws s3api put-object --bucket "${S3_BUCKET}" --key models/
aws s3api put-object --bucket "${S3_BUCKET}" --key logs/
```

Expected S3 layout:

```text
s3://${S3_BUCKET}/
├── raw/
├── processed/
├── models/
└── logs/
```

## 4. Upload the Raw Dataset to S3

Place the raw cybersecurity/SOC dataset locally under `data/raw/`, then upload it:

```bash
mkdir -p data/raw
aws s3 sync data/raw "s3://${S3_BUCKET}/raw/"
```

Verify the upload:

```bash
aws s3 ls "s3://${S3_BUCKET}/raw/" --recursive --human-readable --summarize
```

## 5. Provision AWS Networking with Terraform

The project requires a non-default VPC. The `terraform/` folder should create the VPC, public/private subnets, route tables, internet gateway, security groups, and supporting infrastructure.

```bash
cd terraform
terraform init
terraform fmt
terraform validate
```

Preview the infrastructure plan:

```bash
terraform plan \
  -var="netid=${NETID}" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"
```

Apply the infrastructure:

```bash
terraform apply \
  -var="netid=${NETID}" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"
```

Save Terraform outputs for later steps:

```bash
terraform output
terraform output -json > ../terraform-outputs.json
cd ..
```

Recommended evidence for the report:

- VPC ID and CIDR block.
- Public and private subnet IDs.
- Route table configuration.
- Internet Gateway configuration.
- Security group inbound/outbound rules.
- Screenshot of the created VPC resources.

## 6. Run PySpark Preprocessing on AWS EMR

The `spark/` folder contains the preprocessing pipeline. The pipeline should read raw data from S3, clean and normalize records, create train/validation/test splits, compute EDA summaries, and write processed JSONL files back to S3.

### 6.1 Upload Spark code to S3

```bash
aws s3 sync spark "s3://${S3_BUCKET}/code/spark/"
```

### 6.2 Create an EMR cluster

Use a small temporary cluster for preprocessing. Replace subnet and security group values with the outputs from Terraform.

```bash
export EMR_RELEASE="emr-6.15.0"
export EMR_CLUSTER_NAME="${NETID}-${PROJECT_NAME}-emr"
export EMR_LOG_URI="s3://${S3_BUCKET}/logs/emr/"
export EC2_SUBNET_ID="$(jq -r '.public_subnet_id.value // .public_subnet_ids.value[0]' terraform-outputs.json)"
```

Create the cluster:

```bash
aws emr create-cluster \
  --name "${EMR_CLUSTER_NAME}" \
  --release-label "${EMR_RELEASE}" \
  --applications Name=Spark \
  --region "${AWS_REGION}" \
  --log-uri "${EMR_LOG_URI}" \
  --use-default-roles \
  --ec2-attributes KeyName="${KEY_NAME}",SubnetId="${EC2_SUBNET_ID}" \
  --instance-type m5.xlarge \
  --instance-count 3 \
  --auto-termination-policy IdleTimeout=1800
```

Store the cluster ID returned by the command:

```bash
export EMR_CLUSTER_ID="j-XXXXXXXXXXXXX"
```

### 6.3 Submit the Spark preprocessing job

If your Spark script has a different name, replace `preprocess.py` with the script in the `spark/` folder.

```bash
aws emr add-steps \
  --cluster-id "${EMR_CLUSTER_ID}" \
  --steps Type=Spark,Name="${NETID}-spark-preprocess",ActionOnFailure=TERMINATE_CLUSTER,Args=[--deploy-mode,cluster,s3://${S3_BUCKET}/code/spark/preprocess.py,--input,s3://${S3_BUCKET}/raw/,--output,s3://${S3_BUCKET}/processed/]
```

Monitor the cluster:

```bash
aws emr describe-cluster --cluster-id "${EMR_CLUSTER_ID}" \
  --query 'Cluster.Status' \
  --output json
```

Verify processed outputs:

```bash
aws s3 ls "s3://${S3_BUCKET}/processed/" --recursive --human-readable --summarize
```

Expected processed outputs:

```text
s3://${S3_BUCKET}/processed/train.jsonl
s3://${S3_BUCKET}/processed/validation.jsonl
s3://${S3_BUCKET}/processed/test.jsonl
s3://${S3_BUCKET}/processed/eda/
```

After preprocessing is complete, terminate the EMR cluster if it has not auto-terminated:

```bash
aws emr terminate-clusters --cluster-ids "${EMR_CLUSTER_ID}"
```

Recommended evidence for the report:

- EMR cluster configuration screenshot.
- EMR terminated-state screenshot.
- S3 screenshot showing processed output files.
- At least three EDA figures, such as token length distribution, class/label balance, and sample count per split.

## 7. Fine-Tune TinyLlama with QLoRA/PEFT

The fine-tuning scripts are in `finetuning/`.

```bash
cd finetuning
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install torch transformers datasets accelerate peft trl bitsandbytes sentencepiece protobuf huggingface_hub pandas numpy matplotlib scikit-learn evaluate tensorboard
```

Log in to Hugging Face if needed:

```bash
huggingface-cli login
```

Download the processed splits from S3:

```bash
mkdir -p "${LOCAL_DATA_DIR}" "${LOCAL_OUTPUT_DIR}"
aws s3 cp "s3://${S3_BUCKET}/processed/train.jsonl" "${LOCAL_DATA_DIR}/train.jsonl"
aws s3 cp "s3://${S3_BUCKET}/processed/validation.jsonl" "${LOCAL_DATA_DIR}/validation.jsonl"
aws s3 cp "s3://${S3_BUCKET}/processed/test.jsonl" "${LOCAL_DATA_DIR}/test.jsonl"
```

Verify the files:

```bash
ls -lh "${LOCAL_DATA_DIR}"
head -n 2 "${LOCAL_DATA_DIR}/train.jsonl"
```

### 7.1 Run a 50K-sample test fine-tuning job

```bash
python finetune_tinyllama_qlora_50K.py \
  --base_model "${BASE_MODEL}" \
  --train_file "${LOCAL_DATA_DIR}/train.jsonl" \
  --validation_file "${LOCAL_DATA_DIR}/validation.jsonl" \
  --output_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora-50k" \
  --max_samples 50000 \
  --num_train_epochs 1 \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 2e-4 \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --max_seq_length 2048
```

If the script does not accept command-line arguments, edit the configuration variables at the top of `finetune_tinyllama_qlora_50K.py`, then run:

```bash
python finetune_tinyllama_qlora_50K.py
```

### 7.2 Run the full fine-tuning job

```bash
python finetune_tinyllama_qlora.py \
  --base_model "${BASE_MODEL}" \
  --train_file "${LOCAL_DATA_DIR}/train.jsonl" \
  --validation_file "${LOCAL_DATA_DIR}/validation.jsonl" \
  --output_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  --num_train_epochs 3 \
  --per_device_train_batch_size 2 \
  --gradient_accumulation_steps 8 \
  --learning_rate 2e-4 \
  --lora_r 16 \
  --lora_alpha 32 \
  --lora_dropout 0.05 \
  --max_seq_length 2048
```

Upload the final model artifacts to S3:

```bash
aws s3 sync "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  "s3://${S3_BUCKET}/models/tinyllama-cyber-soc-qlora/"
```

Recommended hyperparameters to report:

| Hyperparameter | Value |
|---|---:|
| Base model | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` |
| Fine-tuning method | QLoRA / PEFT |
| Quantization | 4-bit |
| Epochs | 3 |
| Learning rate | `2e-4` |
| Per-device batch size | 2 |
| Gradient accumulation | 8 |
| LoRA rank | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| Max sequence length | 2048 |

## 8. Test the Base Model vs. Fine-Tuned Model

Run prompt-based testing:

```bash
python test_model.py \
  --base_model "${BASE_MODEL}" \
  --adapter_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  --test_file "${LOCAL_DATA_DIR}/test.jsonl" \
  --num_examples 10
```

If the script uses hard-coded paths, update `test_model.py`, then run:

```bash
python test_model.py
```

Include at least two comparisons in the report:

| Prompt | Base Model Response | Fine-Tuned Model Response |
|---|---|---|
| A workstation executed encoded PowerShell and contacted an unknown IP. What should the SOC analyst do first? | Add output here. | Add output here. |
| Multiple failed logins occurred from several foreign IP addresses. How should this be triaged? | Add output here. | Add output here. |

## 9. Export the Fine-Tuned Model to GGUF

Run the GGUF export script:

```bash
python GGUF_Script.py \
  --base_model "${BASE_MODEL}" \
  --adapter_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  --merged_output_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-merged" \
  --gguf_output "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc.Q4_K_M.gguf" \
  --quantization "Q4_K_M"
```

If the script does not accept command-line arguments, update the paths in `GGUF_Script.py`, then run:

```bash
python GGUF_Script.py
```

Verify the GGUF file:

```bash
ls -lh "${LOCAL_OUTPUT_DIR}"/*.gguf
```

Upload the GGUF model to S3:

```bash
aws s3 cp "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc.Q4_K_M.gguf" \
  "s3://${S3_BUCKET}/models/gguf/tinyllama-cyber-soc.Q4_K_M.gguf"
```

Return to the repository root:

```bash
cd ..
```

## 10. Deploy the Model on EC2 with Ollama

Launch an EC2 instance in the project VPC. Recommended deployment setup:

- AMI: Ubuntu 22.04 LTS
- Instance type: `g4dn.xlarge` for GPU-backed testing, or a CPU instance for small quantized GGUF testing
- Storage: at least 60 GB EBS
- Security group inbound rules:
  - TCP 22 from your IP only
  - TCP 3000 from your IP only for OpenWebUI
  - TCP 11434 should remain local/VPC-only unless explicitly required

SSH into the EC2 instance:

```bash
ssh -i /path/to/${KEY_NAME}.pem ubuntu@<EC2_PUBLIC_IP>
```

Install system packages:

```bash
sudo apt-get update
sudo apt-get install -y curl git unzip python3-pip docker.io awscli
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu
```

Install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

Download the GGUF model from S3:

```bash
export NETID="q1abc"
export PROJECT_NAME="cyber-soc-chatbot"
export S3_BUCKET="${NETID}-${PROJECT_NAME}"

mkdir -p ~/models/cyber-soc
aws s3 cp "s3://${S3_BUCKET}/models/gguf/tinyllama-cyber-soc.Q4_K_M.gguf" \
  ~/models/cyber-soc/tinyllama-cyber-soc.Q4_K_M.gguf
```

Create the Ollama `Modelfile`:

```bash
cat > ~/models/cyber-soc/Modelfile <<'MODELFILE'
FROM ./tinyllama-cyber-soc.Q4_K_M.gguf

SYSTEM "You are a cybersecurity SOC assistant. Provide concise, accurate alert triage guidance. Identify likely threats, recommend investigation steps, and avoid inventing evidence."

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_ctx 2048
MODELFILE
```

Create the Ollama model:

```bash
cd ~/models/cyber-soc
ollama create cyber-soc-chatbot -f Modelfile
ollama list
```

Run the model interactively:

```bash
ollama run cyber-soc-chatbot
```

Test the Ollama API with `curl`:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "cyber-soc-chatbot",
  "prompt": "A workstation executed encoded PowerShell and contacted an unknown external IP. What should a SOC analyst do first?",
  "stream": false
}'
```

Recommended evidence for the report:

- Terminal screenshot showing Ollama serving `cyber-soc-chatbot`.
- Screenshot of the `curl` command and model response.

## 11. Run OpenWebUI

Start OpenWebUI with Docker:

```bash
docker run -d \
  --name open-webui \
  --restart always \
  --network host \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:main
```

Check the container:

```bash
docker ps
```

Open the web interface:

```text
http://<EC2_PUBLIC_IP>:8080
```

If using port mapping instead of host networking, run:

```bash
docker run -d \
  --name open-webui \
  --restart always \
  -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:main
```

Then open:

```text
http://<EC2_PUBLIC_IP>:3000
```

Recommended evidence for the report:

- Browser screenshot showing OpenWebUI running.
- Screenshot showing the selected model name `cyber-soc-chatbot`.
- Screenshot of a sample SOC conversation.

## 12. Security Group Reference

| Port | Purpose | Recommended Source |
|---:|---|---|
| 22 | SSH administration | Your IP only |
| 3000 or 8080 | OpenWebUI browser access | Your IP only |
| 11434 | Ollama API | Localhost or VPC-only |
| 80 / 443 | Optional reverse proxy | Public only if TLS and reverse proxy are configured |

Do not expose Ollama directly to the public internet unless a secure proxy and authentication layer are configured.

## 13. Cost Summary

Update this table with actual values from AWS Billing or Cost Explorer before final submission.

| Service | Purpose | Estimated Usage | Estimated Cost |
|---|---|---:|---:|
| S3 | Raw dataset, processed dataset, model artifacts, logs | Dataset + checkpoints for project duration | `$1–$5` |
| EMR | Spark preprocessing cluster | One short preprocessing run, terminated afterward | `$2–$10` |
| EC2 | Model deployment/testing instance | Temporary Ollama/OpenWebUI serving | `$3–$20` |
| EBS | EC2 storage volume for model files | 60 GB temporary volume | `$1–$5` |
| Data transfer | S3/EC2 artifact movement | Same-region transfer where possible | `$0–$2` |
| Total | Approximate project spend | Depends on runtime and teardown timing | `$7–$42` |

Cost controls:

- Terminate the EMR cluster after preprocessing.
- Stop or terminate EC2 when not testing.
- Delete unused checkpoints and old intermediate files.
- Delete unattached EBS volumes.
- Keep S3, EMR, and EC2 in the same AWS region.

## 14. Final Submission Checklist

Before submitting, confirm that the repository and report include:

- [ ] System architecture diagram with VPC, subnets, security groups, EMR, EC2, Ollama, and OpenWebUI.
- [ ] VPC/networking explanation and Terraform files or annotated console screenshots.
- [ ] Model and dataset selection details, including license, sample count, split strategy, and leakage prevention.
- [ ] PySpark preprocessing code in `spark/`.
- [ ] EMR configuration screenshot.
- [ ] EMR terminated-state screenshot.
- [ ] S3 screenshot showing processed output files.
- [ ] At least three EDA figures.
- [ ] Fine-tuning code in `finetuning/`.
- [ ] Hyperparameter table.
- [ ] At least two base-vs-fine-tuned prompt comparisons.
- [ ] GGUF export evidence.
- [ ] Exact Ollama deployment commands in both this README and the report.
- [ ] Terminal screenshot showing Ollama serving the fine-tuned model.
- [ ] Screenshot of `curl` response from the model API.
- [ ] OpenWebUI browser screenshot with the model name visible.
- [ ] Sample conversation screenshot.
- [ ] Cost summary table.

## 15. Teardown Commands

Run these commands after grading or when resources are no longer needed.

Terminate EMR if still running:

```bash
aws emr list-clusters --active
aws emr terminate-clusters --cluster-ids "${EMR_CLUSTER_ID}"
```

Stop or terminate EC2 instances from the AWS console or CLI:

```bash
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=${NETID}-${PROJECT_NAME}*" \
  --query 'Reservations[].Instances[].{InstanceId:InstanceId,State:State.Name,Name:Tags[?Key==`Name`]|[0].Value}' \
  --output table
```

Destroy Terraform-managed infrastructure:

```bash
cd terraform
terraform destroy \
  -var="netid=${NETID}" \
  -var="aws_region=${AWS_REGION}" \
  -var="project_name=${PROJECT_NAME}"
cd ..
```

Optional S3 cleanup after confirming nothing else is needed:

```bash
aws s3 rm "s3://${S3_BUCKET}" --recursive
aws s3 rb "s3://${S3_BUCKET}"
```

## 16. Troubleshooting

### Terraform variables are missing

List variables expected by the Terraform files:

```bash
grep -R "variable " terraform
```

Then pass the required values with `-var` or a `.tfvars` file.

### EMR step fails immediately

Check the step logs:

```bash
aws emr list-steps --cluster-id "${EMR_CLUSTER_ID}"
aws emr describe-step --cluster-id "${EMR_CLUSTER_ID}" --step-id <STEP_ID>
```

Common issues:

- Incorrect S3 path for the Spark script.
- Missing IAM permissions for S3 read/write.
- Dataset schema does not match the preprocessing script.

### CUDA out of memory during fine-tuning

Reduce memory use:

```bash
--per_device_train_batch_size 1
--gradient_accumulation_steps 16
--max_seq_length 1024
--lora_r 8
```

Also confirm 4-bit quantization is enabled in the training script.

### OpenWebUI cannot connect to Ollama

Check Ollama locally:

```bash
curl http://localhost:11434/api/tags
```

Restart OpenWebUI:

```bash
docker restart open-webui
```

Check container logs:

```bash
docker logs --tail 100 open-webui
```

## License and Attribution

Document the licenses for the selected base model and dataset in the final report. Also include links to the model and dataset sources used for training.
