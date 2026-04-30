import unsloth
from unsloth import FastLanguageModel

import torch
from datasets import load_dataset
from trl import SFTTrainer, SFTConfig


MODEL_NAME = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
MAX_SEQ_LENGTH = 1024
OUTPUT_DIR = "outputs/cyber-soc-tinyllama-lora"

TRAIN_FILE = "/content/train_10k.jsonl"
VAL_FILE = "/content/validation_1k.jsonl"


def main():
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA GPU is not available. Enable T4 GPU in Colab runtime settings.")

    print("Using GPU:", torch.cuda.get_device_name(0))

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=MODEL_NAME,
        max_seq_length=MAX_SEQ_LENGTH,
        dtype=None,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset = load_dataset(
        "json",
        data_files={
            "train": TRAIN_FILE,
            "validation": VAL_FILE,
        },
    )

    def formatting_func(batch):
        texts = []
        for i in range(len(batch["instruction"])):
            text = (
                "### Instruction:\n"
                + batch["instruction"][i]
                + "\n\n### Cybersecurity Event:\n"
                + batch["input"][i]
                + "\n\n### Response:\n"
                + batch["output"][i]
            )
            texts.append(text)
        return texts

    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=8,
        warmup_steps=20,
        num_train_epochs=1,
        learning_rate=2e-4,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=100,
        save_steps=250,
        save_total_limit=2,
        optim="adamw_8bit",
        weight_decay=0.01,
        lr_scheduler_type="linear",
        seed=42,
        report_to="none",
        max_length=MAX_SEQ_LENGTH,
        packing=False,
        padding_free=False,
    )

    trainer = SFTTrainer(
        model=model,
        processing_class=tokenizer,
        train_dataset=dataset["train"],
        eval_dataset=dataset["validation"],
        tokenizer=tokenizer,
        formatting_func=formatting_func,
        args=training_args,
    )

    trainer.train()

    model.save_pretrained("models/cyber-soc-tinyllama-lora")
    tokenizer.save_pretrained("models/cyber-soc-tinyllama-lora")

    print("Fine-tuning complete.")
    print("Saved adapter to models/cyber-soc-tinyllama-lora")


if __name__ == "__main__":
    main()