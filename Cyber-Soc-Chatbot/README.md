# Fine-Tuning Pipeline — TinyLlama QLoRA and GGUF Export

This folder contains the fine-tuning and model-conversion scripts for the **Cyber-SOC Chatbot** project. The goal is to fine-tune a lightweight open-source LLM using QLoRA/PEFT, evaluate the tuned model against the base model, and export the final model to GGUF so it can be served with Ollama and connected to OpenWebUI.

## Folder Contents

| File | Purpose |
|---|---|
| `finetune_tinyllama_qlora.py` | Full QLoRA fine-tuning script for TinyLlama on the preprocessed cybersecurity/SOC dataset. |
| `finetune_tinyllama_qlora_50K.py` | Smaller 50K-sample fine-tuning run for faster experimentation and debugging. |
| `GGUF_Script.py` | Exports or converts the fine-tuned model/adapters into GGUF format for Ollama deployment. |
| `test_model.py` | Runs prompt-based testing against the base and/or fine-tuned model. |

## Project Context

This fine-tuning stage is part of the end-to-end cloud chatbot pipeline:

1. Dataset is uploaded to Amazon S3.
2. Data is cleaned and split using PySpark on AWS EMR.
3. TinyLlama is fine-tuned using QLoRA/PEFT.
4. The fine-tuned model is exported to GGUF.
5. The GGUF model is served on EC2 using Ollama.
6. OpenWebUI provides the browser-based chatbot interface.

## Prerequisites

### Accounts and Services

- AWS account access for S3, EMR, and EC2.
- Hugging Face account and token if the selected base model or dataset requires authentication.
- Optional: Google Colab with GPU runtime for fine-tuning.

### Local or Cloud Machine

Recommended training environment:

- Python 3.10+
- NVIDIA GPU with approximately 16 GB VRAM, such as Google Colab T4 or AWS `g4dn.xlarge`
- CUDA-compatible PyTorch installation
- At least 40 GB free disk space for model checkpoints and GGUF export

Recommended deployment environment:

- AWS EC2 GPU or CPU instance, depending on GGUF quantization level
- Ubuntu 22.04 LTS or similar Linux AMI
- Ollama
- Docker, if using OpenWebUI

## Required AWS Naming Convention

All AWS resources should be prefixed with your Queen's NetID.

Example:

```bash
export NETID="q1abc"
export AWS_REGION="us-east-1"
export S3_BUCKET="${NETID}-cyber-soc-chatbot"
```

Use your actual NetID before running any AWS commands.

## Expected Input Data

The fine-tuning scripts expect preprocessed JSONL files produced by the EMR/Spark preprocessing stage.

Recommended S3 structure:

```text
s3://${S3_BUCKET}/processed/train.jsonl
s3://${S3_BUCKET}/processed/validation.jsonl
s3://${S3_BUCKET}/processed/test.jsonl
```

Recommended JSONL format:

```json
{"instruction":"Analyze the following SOC alert.","input":"Suspicious PowerShell execution from endpoint host-22.","output":"This may indicate malicious script execution. Review parent process, command-line arguments, user context, and network indicators."}
```

If your scripts use `prompt` and `response` instead of `instruction`, `input`, and `output`, keep the schema consistent across train, validation, and test files.

## Environment Setup

Create and activate a Python virtual environment:

```bash
cd finetuning
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

Install required packages:

```bash
pip install torch transformers datasets accelerate peft trl bitsandbytes sentencepiece protobuf huggingface_hub
```

Optional packages for logging and evaluation:

```bash
pip install pandas numpy matplotlib scikit-learn evaluate tensorboard
```

Log in to Hugging Face if needed:

```bash
huggingface-cli login
```

Configure AWS CLI:

```bash
aws configure
aws sts get-caller-identity
```

## Download Preprocessed Dataset from S3

Set project variables:

```bash
export NETID="q1abc"
export AWS_REGION="us-east-1"
export S3_BUCKET="${NETID}-cyber-soc-chatbot"
export LOCAL_DATA_DIR="./data"
export LOCAL_OUTPUT_DIR="./outputs"

mkdir -p "${LOCAL_DATA_DIR}" "${LOCAL_OUTPUT_DIR}"
```

Download the processed splits:

```bash
aws s3 cp "s3://${S3_BUCKET}/processed/train.jsonl" "${LOCAL_DATA_DIR}/train.jsonl"
aws s3 cp "s3://${S3_BUCKET}/processed/validation.jsonl" "${LOCAL_DATA_DIR}/validation.jsonl"
aws s3 cp "s3://${S3_BUCKET}/processed/test.jsonl" "${LOCAL_DATA_DIR}/test.jsonl"
```

Verify files exist:

```bash
ls -lh "${LOCAL_DATA_DIR}"
head -n 2 "${LOCAL_DATA_DIR}/train.jsonl"
```

## Base Model

Default base model:

```bash
export BASE_MODEL="TinyLlama/TinyLlama-1.1B-Chat-v1.0"
```

TinyLlama is suitable for this project because it is small enough for low-cost experimentation while still supporting instruction-style fine-tuning.

## Run a Fast 50K-Sample Fine-Tuning Experiment

Use the 50K script first to confirm that the dataset, tokenizer, GPU, and output paths work correctly.

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

If the script does not accept command-line arguments, edit the configuration block at the top of `finetune_tinyllama_qlora_50K.py` with the same values above, then run:

```bash
python finetune_tinyllama_qlora_50K.py
```

## Run the Full Fine-Tuning Job

After the 50K run completes successfully, run the full fine-tuning script:

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

If the script uses hard-coded settings, update the script configuration and run:

```bash
python finetune_tinyllama_qlora.py
```

## Recommended Hyperparameters to Report

| Hyperparameter | Recommended Value | Notes |
|---|---:|---|
| Base model | `TinyLlama/TinyLlama-1.1B-Chat-v1.0` | Small open-source chat model. |
| Fine-tuning method | QLoRA / PEFT | Updates adapter weights instead of full model weights. |
| Quantization | 4-bit | Reduces VRAM usage. |
| Epochs | `1` for test run, `3` for full run | Adjust based on validation loss. |
| Learning rate | `2e-4` | Common LoRA starting point. |
| Batch size | `2` | Increase only if GPU memory allows. |
| Gradient accumulation | `8` | Effective batch size = batch size × accumulation. |
| LoRA rank `r` | `16` | Adapter capacity. |
| LoRA alpha | `32` | LoRA scaling factor. |
| LoRA dropout | `0.05` | Helps reduce overfitting. |
| Max sequence length | `2048` | Adjust based on dataset token lengths. |

## Expected Training Outputs

After training, the output directory should contain files similar to:

```text
outputs/tinyllama-cyber-soc-qlora/
├── adapter_config.json
├── adapter_model.safetensors
├── tokenizer.json
├── tokenizer_config.json
├── special_tokens_map.json
├── training_args.bin
└── checkpoint-*/
```

Upload training artifacts to S3:

```bash
aws s3 sync "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  "s3://${S3_BUCKET}/models/tinyllama-cyber-soc-qlora"
```

## Test the Fine-Tuned Model

Run model testing on cybersecurity/SOC prompts:

```bash
python test_model.py \
  --base_model "${BASE_MODEL}" \
  --adapter_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  --test_file "${LOCAL_DATA_DIR}/test.jsonl" \
  --num_examples 10
```

If command-line arguments are not supported, edit `test_model.py` with the same paths and run:

```bash
python test_model.py
```

Recommended report evidence:

| Prompt | Base Model Response | Fine-Tuned Model Response |
|---|---|---|
| Investigate a suspicious PowerShell command from a workstation. | Add base response here. | Add fine-tuned response here. |
| Classify a failed-login spike from multiple IP addresses. | Add base response here. | Add fine-tuned response here. |

## Export to GGUF

Run the GGUF export/conversion script:

```bash
python GGUF_Script.py \
  --base_model "${BASE_MODEL}" \
  --adapter_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-qlora" \
  --merged_output_dir "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc-merged" \
  --gguf_output "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc.Q4_K_M.gguf" \
  --quantization "Q4_K_M"
```

If the script does not accept command-line arguments, update the paths in `GGUF_Script.py` and run:

```bash
python GGUF_Script.py
```

Verify the GGUF file:

```bash
ls -lh "${LOCAL_OUTPUT_DIR}"/*.gguf
```

Upload GGUF to S3:

```bash
aws s3 cp "${LOCAL_OUTPUT_DIR}/tinyllama-cyber-soc.Q4_K_M.gguf" \
  "s3://${S3_BUCKET}/models/gguf/tinyllama-cyber-soc.Q4_K_M.gguf"
```

## Serve the GGUF Model with Ollama on EC2

Install Ollama:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama --version
```

Download the GGUF model from S3:

```bash
mkdir -p ~/models/cyber-soc
aws s3 cp "s3://${S3_BUCKET}/models/gguf/tinyllama-cyber-soc.Q4_K_M.gguf" \
  ~/models/cyber-soc/tinyllama-cyber-soc.Q4_K_M.gguf
```

Create an Ollama `Modelfile`:

```bash
cat > ~/models/cyber-soc/Modelfile <<'MODELFILE'
FROM ./tinyllama-cyber-soc.Q4_K_M.gguf

SYSTEM "You are a cybersecurity SOC assistant. Provide concise, accurate triage guidance, identify likely threats, and recommend investigation steps. Do not invent evidence."

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_ctx 2048
MODELFILE
```

Create and run the model:

```bash
cd ~/models/cyber-soc
ollama create cyber-soc-chatbot -f Modelfile
ollama list
ollama run cyber-soc-chatbot
```

Test the Ollama API:

```bash
curl http://localhost:11434/api/generate -d '{
  "model": "cyber-soc-chatbot",
  "prompt": "A workstation executed encoded PowerShell and contacted an unknown external IP. What should a SOC analyst do first?",
  "stream": false
}'
```

## Run OpenWebUI

Install and start OpenWebUI with Docker:

```bash
docker run -d \
  --name open-webui \
  --restart always \
  -p 3000:8080 \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:main
```

On Linux EC2, if `host.docker.internal` does not resolve, use:

```bash
docker run -d \
  --name open-webui \
  --restart always \
  --network host \
  -e OLLAMA_BASE_URL=http://127.0.0.1:11434 \
  -v open-webui:/app/backend/data \
  ghcr.io/open-webui/open-webui:main
```

Open the interface in a browser:

```text
http://<EC2_PUBLIC_IP>:3000
```

Select the model named:

```text
cyber-soc-chatbot
```

## Security Group Ports for Deployment

| Port | Purpose | Source Recommendation |
|---:|---|---|
| `22` | SSH | Your IP only. |
| `11434` | Ollama API | Keep private unless required. Prefer localhost or VPC-only access. |
| `3000` | OpenWebUI | Your IP only for grading/demo access. |
| `80` / `443` | Optional web access | Use only if reverse proxy and TLS are configured. |

## Reproducibility Checklist

Before submitting, confirm that this folder supports the following:

- [ ] `finetune_tinyllama_qlora_50K.py` runs successfully on a small sample.
- [ ] `finetune_tinyllama_qlora.py` runs the final training job.
- [ ] `test_model.py` produces at least two base-vs-fine-tuned comparisons.
- [ ] Training hyperparameters are recorded in the report.
- [ ] Final adapter/model artifacts are uploaded to S3.
- [ ] `GGUF_Script.py` creates a `.gguf` file.
- [ ] Ollama can load and run the model as `cyber-soc-chatbot`.
- [ ] A `curl` request returns a response from the model API.
- [ ] OpenWebUI displays the fine-tuned model name.
- [ ] Screenshots are captured for the report.

## Approximate Cost Summary

| Service | Purpose | Approximate Cost Control |
|---|---|---|
| S3 | Store raw data, processed data, checkpoints, and GGUF model | Delete unused checkpoints and old intermediate files. |
| EMR | Spark preprocessing | Terminate cluster immediately after preprocessing. |
| EC2 `g4dn.xlarge` | Training or deployment testing | Stop or terminate when not actively testing. |
| EBS | EC2 model/checkpoint storage | Delete unattached volumes after teardown. |
| Data transfer | Moving model/data artifacts | Keep artifacts in the same AWS region where possible. |
| Google Colab | Optional fine-tuning environment | Free tier may be sufficient for small QLoRA runs. |

## Troubleshooting

### CUDA out of memory

Reduce one or more of the following:

```bash
--per_device_train_batch_size 1
--max_seq_length 1024
--lora_r 8
```

Also confirm 4-bit quantization is enabled in the training script.

### Dataset schema error

Print one row from the JSONL file:

```bash
head -n 1 ./data/train.jsonl
```

Confirm the script expects the same column names used in the JSONL file.

### Ollama cannot find GGUF model

Confirm the GGUF path in `Modelfile` is relative to the directory where `ollama create` is executed:

```bash
cd ~/models/cyber-soc
ls -lh
ollama create cyber-soc-chatbot -f Modelfile
```

### OpenWebUI cannot connect to Ollama

Check that Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

Then restart OpenWebUI:

```bash
docker restart open-webui
```

## Submission Notes

Include the following evidence in the final report:

1. Fine-tuning setup: model, hardware, QLoRA/PEFT method, and hyperparameters.
2. Training output or loss curve.
3. At least two prompt comparisons between the base and fine-tuned model.
4. Terminal screenshot showing Ollama serving `cyber-soc-chatbot`.
5. Screenshot of the `curl` response from the Ollama API.
6. Browser screenshot of OpenWebUI showing the fine-tuned model name.
7. Sample conversation screenshot from OpenWebUI.
