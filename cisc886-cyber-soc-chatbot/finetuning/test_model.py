import torch
from unsloth import FastLanguageModel


BASE_MODEL = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
ADAPTER_PATH = "outputs/cyber-soc-tinyllama-lora/models/cyber-soc-tinyllama-lora"
MAX_SEQ_LENGTH = 2048


TEST_PROMPTS = [
    """Analyze the following cybersecurity event and provide a SOC triage assessment.

Severity: 8
Action: deny
Lifecycle stage: credential_access
Matched rules: repeated_failed_login
Message: Multiple failed login attempts from a single source to an admin account.""",
    """Analyze the following cybersecurity event and provide a SOC triage assessment.

Severity: 9
Action: allowed
Lifecycle stage: lateral_movement
Matched rules: suspicious_remote_execution
Message: Remote process execution observed between internal hosts."""
]


def generate(model, tokenizer, prompt):
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    outputs = model.generate(
        **inputs,
        max_new_tokens=250,
        temperature=0.2,
        top_p=0.9,
        do_sample=True,
    )
    return tokenizer.decode(outputs[0], skip_special_tokens=True)


def main():
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=ADAPTER_PATH,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    FastLanguageModel.for_inference(model)

    for i, prompt in enumerate(TEST_PROMPTS, start=1):
        formatted = (
            "### Instruction:\n"
            f"{prompt}\n\n"
            "### Response:\n"
        )
        print("=" * 80)
        print(f"Prompt {i}")
        print("=" * 80)
        print(generate(model, tokenizer, formatted))


if __name__ == "__main__":
    main()