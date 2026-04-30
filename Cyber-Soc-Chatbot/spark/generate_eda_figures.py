import os
import glob
import pandas as pd
import matplotlib.pyplot as plt


EDA_DIR = "eda_downloads"
FIG_DIR = "figures"
os.makedirs(FIG_DIR, exist_ok=True)


def read_csv_folder(folder_path):
    files = glob.glob(os.path.join(folder_path, "part-*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV part files found in {folder_path}")
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)


# 1. Label distribution before balancing
before = read_csv_folder(os.path.join(EDA_DIR, "label_distribution_before"))
plt.figure(figsize=(8, 5))
plt.bar(before["label_binary"], before["count"])
plt.title("Label Distribution Before Balancing")
plt.xlabel("Label")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "label_distribution_before.png"), dpi=200)
plt.close()

# 2. Label distribution after balancing
after = read_csv_folder(os.path.join(EDA_DIR, "label_distribution_after"))
plt.figure(figsize=(8, 5))
plt.bar(after["label_binary"], after["count"])
plt.title("Label Distribution After Balancing")
plt.xlabel("Label")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "label_distribution_after.png"), dpi=200)
plt.close()

# 3. Message length distribution
lengths = read_csv_folder(os.path.join(EDA_DIR, "message_lengths_sample"))
plt.figure(figsize=(8, 5))
plt.hist(lengths["message_length_chars"], bins=50)
plt.title("Sanitized Message Length Distribution")
plt.xlabel("Message length in characters")
plt.ylabel("Frequency")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "message_length_distribution.png"), dpi=200)
plt.close()

# 4. Split counts
split_counts = read_csv_folder(os.path.join(EDA_DIR, "split_counts"))
pivot = split_counts.pivot(index="split", columns="label_binary", values="count").fillna(0)
pivot.plot(kind="bar", figsize=(8, 5))
plt.title("Train/Validation/Test Split Counts")
plt.xlabel("Split")
plt.ylabel("Count")
plt.tight_layout()
plt.savefig(os.path.join(FIG_DIR, "split_counts.png"), dpi=200)
plt.close()

print("EDA figures saved to figures/")