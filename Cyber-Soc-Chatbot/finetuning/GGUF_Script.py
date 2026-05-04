import unsloth
from unsloth import FastLanguageModel
from pathlib import Path

ADAPTER_DIR = Path("/mnt/c/Users/digilians01/Desktop/Cloud_Project/Cyber-SOC-Chatbot/cyber-soc-tinyllama-lora-50k")

GGUF_DIR = Path("/mnt/c/Users/digilians01/Desktop/Cloud_Project/Cyber-SOC-Chatbot/cisc886-cyber-soc-chatbot/models/cyber-soc-tinyllama-gguf-50k")

MAX_SEQ_LENGTH = 1024

if not ADAPTER_DIR.exists():
    raise FileNotFoundError(f"Adapter folder not found: {ADAPTER_DIR}")

print("Loading adapter from:", ADAPTER_DIR)

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name=str(ADAPTER_DIR),
    max_seq_length=MAX_SEQ_LENGTH,
    dtype=None,
    load_in_4bit=True,
)

GGUF_DIR.mkdir(parents=True, exist_ok=True)

print("Exporting GGUF to:", GGUF_DIR)

model.save_pretrained_gguf(
    str(GGUF_DIR),
    tokenizer,
    quantization_method="q4_k_m",
)

print("GGUF export complete.")
print("Saved to:", GGUF_DIR)