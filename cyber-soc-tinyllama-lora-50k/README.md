# cyber-soc-tinyllama-QLoRA-50k

Fine-tuned TinyLlama QLoRA adapter for the **Cyber-SOC Chatbot** project.

This folder contains the trained PEFT/QLoRA adapter artifacts and tokenizer files produced by the fine-tuning pipeline. The adapter is intended to be loaded on top of the TinyLlama base model for cybersecurity/SOC-style assistant behavior.

---

## Folder contents

| File | Purpose |
|---|---|
| `adapter_config.json` | PEFT/QLoRA adapter configuration, including base model reference and QLoRA settings. |
| `adapter_model.safetensors` | Fine-tuned QLoRA adapter weights. |
| `tokenizer.json` | Fast tokenizer configuration. |
| `tokenizer.model` | SentencePiece tokenizer model used by TinyLlama-compatible checkpoints. |
| `tokenizer_config.json` | Tokenizer metadata and runtime configuration. |
| `special_tokens_map.json` | Mapping for BOS, EOS, unknown, padding, and other special tokens. |
| `chat_template.jinja` | Chat formatting template used to serialize messages into model prompts. |
| `README.md` | Documentation for using this adapter folder. |

---

## Model summary

| Field | Value |
|---|---|
| Adapter name | `cyber-soc-tinyllama-QLoRA-50k` |
| Base model family | TinyLlama |
| Fine-tuning method | QLoRA / PEFT |
| Training sample size | 50k records |
| Target domain | Cybersecurity SOC assistant |
| Weight format | `safetensors` |
| Expected use | Load adapter with the TinyLlama base model for inference or export/merge into a deployable model |

---

## Prerequisites

Use Python 3.10 or newer.

Install the required packages:

```bash
pip install --upgrade pip
pip install torch transformers peft accelerate safetensors sentencepiece
```

For GPU inference, install a CUDA-compatible PyTorch build from the official PyTorch instructions for your environment.

---

## Quick verification

From the parent directory that contains `cyber-soc-tinyllama-QLoRA-50k/`, run:

```bash
ls -lh cyber-soc-tinyllama-QLoRA-50k
```

Expected core files:

```text
adapter_config.json
adapter_model.safetensors
chat_template.jinja
special_tokens_map.json
tokenizer.json
tokenizer.model
tokenizer_config.json
```

---

## Load the adapter with Transformers + PEFT

Create a file named `test_adapter.py` outside this folder:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ADAPTER_DIR = "./cyber-soc-tinyllama-QLoRA-50k"

tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR, trust_remote_code=True)

base_model_name = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

base_model = AutoModelForCausalLM.from_pretrained(
    base_model_name,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    trust_remote_code=True,
)

model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
model.eval()

messages = [
    {
        "role": "system",
        "content": "You are a cybersecurity SOC assistant. Provide concise, practical guidance."
    },
    {
        "role": "user",
        "content": "A workstation generated multiple failed login events followed by a successful login from a new country. What should the analyst check first?"
    }
]

prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=256,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
        repetition_penalty=1.1,
    )

response = tokenizer.decode(outputs[0], skip_special_tokens=True)
print(response)
```

Run it:

```bash
python test_adapter.py
```

---

## Merge the QLoRA adapter into the base model

Use this when you want a standalone merged Hugging Face model directory.

Create `merge_adapter.py`:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel

ADAPTER_DIR = "./cyber-soc-tinyllama-QLoRA-50k"
OUTPUT_DIR = "./cyber-soc-tinyllama-QLoRA-50k-merged"
BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"

tokenizer = AutoTokenizer.from_pretrained(ADAPTER_DIR, trust_remote_code=True)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    trust_remote_code=True,
)

model = PeftModel.from_pretrained(base_model, ADAPTER_DIR)
merged_model = model.merge_and_unload()

merged_model.save_pretrained(OUTPUT_DIR, safe_serialization=True)
tokenizer.save_pretrained(OUTPUT_DIR)

print(f"Merged model saved to: {OUTPUT_DIR}")
```

Run:

```bash
python merge_adapter.py
```

---

## Test the merged model

Create `test_merged_model.py`:

```python
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_DIR = "./cyber-soc-tinyllama-QLoRA-50k-merged"

tokenizer = AutoTokenizer.from_pretrained(MODEL_DIR, trust_remote_code=True)

model = AutoModelForCausalLM.from_pretrained(
    MODEL_DIR,
    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    device_map="auto",
    trust_remote_code=True,
)

messages = [
    {
        "role": "system",
        "content": "You are a cybersecurity SOC assistant."
    },
    {
        "role": "user",
        "content": "Explain how to triage a phishing alert in a SOC queue."
    }
]

prompt = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

with torch.no_grad():
    outputs = model.generate(
        **inputs,
        max_new_tokens=300,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
    )

print(tokenizer.decode(outputs[0], skip_special_tokens=True))
```

Run:

```bash
python test_merged_model.py
```

---

## Optional: Export to GGUF for Ollama

Ollama normally runs GGUF models. To deploy this fine-tuned model with Ollama, first merge the QLoRA adapter into the base model, then convert the merged model to GGUF using `llama.cpp`.

Install `llama.cpp`:

```bash
git clone https://github.com/ggerganov/llama.cpp.git
cd llama.cpp
pip install -r requirements.txt
```

Convert the merged Hugging Face model to GGUF:

```bash
python convert_hf_to_gguf.py ../cyber-soc-tinyllama-QLoRA-50k-merged \
  --outfile ../cyber-soc-tinyllama-QLoRA-50k.gguf \
  --outtype f16
```

Optional quantization:

```bash
cmake -B build
cmake --build build --config Release

./build/bin/llama-quantize \
  ../cyber-soc-tinyllama-QLoRA-50k.gguf \
  ../cyber-soc-tinyllama-QLoRA-50k-q4_k_m.gguf \
  Q4_K_M
```

---

## Optional: Run with Ollama

Create a `Modelfile` next to the GGUF file:

```text
FROM ./cyber-soc-tinyllama-QLoRA-50k-q4_k_m.gguf

TEMPLATE """{{ if .System }}<|system|>
{{ .System }}</s>
{{ end }}<|user|>
{{ .Prompt }}</s>
<|assistant|>
"""

PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER num_ctx 4096

SYSTEM """You are a cybersecurity SOC assistant. Provide concise, safe, practical incident triage guidance."""
```

Create the Ollama model:

```bash
ollama create cyber-soc-tinyllama-QLoRA-50k -f Modelfile
```

Run it interactively:

```bash
ollama run cyber-soc-tinyllama-QLoRA-50k
```

Test through the local API:

```bash
curl http://localhost:11434/api/generate \
  -d '{
    "model": "cyber-soc-tinyllama-QLoRA-50k",
    "prompt": "A user clicked a suspicious link and entered credentials. What should the SOC analyst do first?",
    "stream": false
  }'
```

---

## Suggested evaluation prompts

Use these prompts to compare the base model and fine-tuned adapter.

### Prompt 1: Phishing triage

```text
A user reports a suspicious email with an attachment. The sender domain is one character different from a vendor domain. What should a SOC analyst do?
```

### Prompt 2: Brute-force detection

```text
Multiple failed SSH logins from one IP are followed by a successful login to a Linux server. What are the first triage steps?
```

### Prompt 3: Malware alert

```text
An endpoint alert shows PowerShell spawning from Microsoft Word. What should the analyst investigate?
```

### Prompt 4: Data exfiltration

```text
A workstation uploaded 3 GB of data to an unknown cloud storage domain after midnight. What evidence should be collected?
```

---

## Recommended inference settings

| Parameter | Recommended value |
|---|---:|
| `temperature` | `0.1` to `0.3` |
| `top_p` | `0.8` to `0.95` |
| `max_new_tokens` | `256` to `512` |
| `repetition_penalty` | `1.05` to `1.15` |
| `num_ctx` | `2048` to `4096` |

For SOC triage, lower temperature is recommended because answers should be stable, procedural, and evidence-focused.

---

## Deployment notes

This folder stores the adapter, not necessarily a full standalone model. For deployment, use one of these options:

1. **PEFT runtime loading**  
   Load TinyLlama from Hugging Face, then attach this QLoRA adapter using `PeftModel.from_pretrained`.

2. **Merged Hugging Face model**  
   Merge the adapter into the base model with `merge_and_unload()` and serve the merged directory.

3. **Ollama GGUF model**  
   Merge the adapter, convert to GGUF, optionally quantize, then create an Ollama model with a `Modelfile`.

For the course deployment path, the recommended approach is:

```text
QLoRA adapter -> merged Hugging Face model -> GGUF -> Ollama -> OpenWebUI
```

---

## Known limitations

- The adapter must be used with a compatible TinyLlama base model.
- The model is intended for cybersecurity guidance and SOC triage assistance, not autonomous incident response.
- Outputs should be reviewed by a human analyst before operational use.
- The model may hallucinate commands, indicators, or remediation steps; verify all actions against logs, policies, and approved playbooks.
- Do not use the model to generate harmful exploit instructions or unauthorized attack guidance.

---

## Reproducibility checklist

Before submitting or deploying, verify that:

- [ ] `adapter_model.safetensors` is present.
- [ ] `adapter_config.json` points to the correct base model.
- [ ] Tokenizer files are included.
- [ ] A local PEFT loading test succeeds.
- [ ] At least two qualitative evaluation prompts have been tested.
- [ ] If using Ollama, the model has been converted to GGUF.
- [ ] The deployed model name is visible in terminal/API screenshots.
- [ ] A sample API response or browser chat screenshot has been captured.

---

## Example project commands

From the repository root:

```bash
# Verify adapter files
ls -lh cyber-soc-tinyllama-QLoRA-50k

# Install dependencies
pip install torch transformers peft accelerate safetensors sentencepiece

# Test adapter inference
python test_adapter.py

# Merge adapter into the base model
python merge_adapter.py

# Test merged model
python test_merged_model.py
```

---

## Citation / attribution notes

When documenting this model in the final report, include:

- Base model name and source
- Base model license
- Dataset name and license
- Fine-tuning method: QLoRA / PEFT
- Hardware used for fine-tuning
- Hyperparameters used during training
- At least two base-model vs fine-tuned-model response comparisons
