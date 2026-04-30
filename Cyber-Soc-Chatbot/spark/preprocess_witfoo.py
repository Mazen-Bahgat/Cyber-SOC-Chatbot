import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col,
    lit,
    when,
    concat_ws,
    length,
    rand,
    lower,
    regexp_replace,
    coalesce,
    array,
    monotonically_increasing_id
)


def add_missing_columns(df, required_columns):
    """
    Ensures the script does not fail if the dataset schema differs slightly.
    Missing columns are added as string column 'unknown'.
    """
    for c in required_columns:
        if c not in df.columns:
            df = df.withColumn(c, lit("unknown"))
    return df


def main(args):
    spark = (
        SparkSession.builder
        .appName("cisc886-witfoo-instruction-preprocessing")
        .config("spark.sql.shuffle.partitions", "200")
        .getOrCreate()
    )

    raw_path = args.input
    output_path = args.output
    eda_path = args.eda
    target_per_class = args.target_per_class

    print(f"Reading raw dataset from: {raw_path}")
    df = (
    spark.read
    .option("pathGlobFilter", "*.parquet")
    .option("recursiveFileLookup", "true")
    .parquet(raw_path)
    )

    print("Available columns:")
    print(df.columns)

    required_columns = [
        "timestamp",
        "message_type",
        "vendor_name",
        "product_name",
        "src_ip",
        "dst_ip",
        "src_port",
        "dst_port",
        "action",
        "severity",
        "message_sanitized",
        "label_binary",
        "label_confidence",
        "suspicion_score",
        "lifecycle_stage",
        "matched_rules"
    ]

    df = add_missing_columns(df, required_columns)

    # Normalize labels
    df = df.withColumn("label_binary", lower(col("label_binary").cast("string")))

    # Keep only useful labeled records
    df = df.filter(col("label_binary").isin("benign", "suspicious", "malicious"))
    df = df.filter(col("message_sanitized").isNotNull())
    df = df.filter(length(col("message_sanitized").cast("string")) >= 20)

    # Clean text fields
    df = df.withColumn(
        "message_sanitized",
        regexp_replace(col("message_sanitized").cast("string"), r"\s+", " ")
    )

    # EDA: label distribution before balancing
    (
        df.groupBy("label_binary")
        .count()
        .orderBy("label_binary")
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{eda_path}/label_distribution_before")
    )

    # EDA: message length statistics source
    length_df = df.withColumn("message_length_chars", length(col("message_sanitized")))
    (
        length_df.select("label_binary", "message_length_chars")
        .sample(False, 0.01, seed=42)
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{eda_path}/message_lengths_sample")
    )

    # Balance classes.
    # Use row limits instead of full 114M fine-tuning to keep training practical.
    benign = (
        df.filter(col("label_binary") == "benign")
        .orderBy(rand(seed=42))
        .limit(target_per_class)
    )

    suspicious = (
        df.filter(col("label_binary") == "suspicious")
        .orderBy(rand(seed=43))
        .limit(target_per_class)
    )

    malicious = (
        df.filter(col("label_binary") == "malicious")
        .orderBy(rand(seed=44))
        .limit(target_per_class)
    )

    balanced = benign.unionByName(suspicious).unionByName(malicious)

    # EDA: label distribution after balancing
    (
        balanced.groupBy("label_binary")
        .count()
        .orderBy("label_binary")
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{eda_path}/label_distribution_after")
    )

    # Build input string
    balanced = balanced.withColumn(
        "input",
        concat_ws(
            "\n",
            concat_ws("", lit("Timestamp: "), col("timestamp").cast("string")),
            concat_ws("", lit("Message type: "), col("message_type").cast("string")),
            concat_ws("", lit("Vendor: "), col("vendor_name").cast("string")),
            concat_ws("", lit("Product: "), col("product_name").cast("string")),
            concat_ws("", lit("Severity: "), col("severity").cast("string")),
            concat_ws("", lit("Action: "), col("action").cast("string")),
            concat_ws("", lit("Source IP: "), col("src_ip").cast("string")),
            concat_ws("", lit("Source port: "), col("src_port").cast("string")),
            concat_ws("", lit("Destination IP: "), col("dst_ip").cast("string")),
            concat_ws("", lit("Destination port: "), col("dst_port").cast("string")),
            concat_ws("", lit("Label confidence: "), col("label_confidence").cast("string")),
            concat_ws("", lit("Suspicion score: "), col("suspicion_score").cast("string")),
            concat_ws("", lit("Lifecycle stage: "), col("lifecycle_stage").cast("string")),
            concat_ws("", lit("Matched rules: "), col("matched_rules").cast("string")),
            concat_ws("", lit("Message: "), col("message_sanitized").cast("string"))
        )
    )

    balanced = balanced.withColumn(
        "instruction",
        lit("Analyze the following cybersecurity event and provide a SOC triage assessment.")
    )

    benign_output = (
        "Classification: benign\n"
        "Risk level: low\n"
        "Explanation: The event does not show strong indicators of compromise based on the available fields. "
        "No high-risk lifecycle stage or confirmed malicious behavior is evident from this record alone.\n"
        "Recommended action: No immediate escalation is required. Continue monitoring for repeated or correlated activity."
    )

    suspicious_output = (
        "Classification: suspicious\n"
        "Risk level: medium\n"
        "Explanation: The event contains indicators that require analyst review, such as suspicious behavior, elevated severity, "
        "matched detection logic, or possible attack lifecycle context.\n"
        "Recommended action: Correlate this event with authentication, endpoint, and network activity. Escalate if related events, "
        "privileged accounts, or repeated attempts are observed."
    )

    malicious_output = (
        "Classification: malicious\n"
        "Risk level: high\n"
        "Explanation: The event is associated with high-confidence malicious behavior or attack activity. The available fields suggest "
        "potential compromise, exploitation, lateral movement, or other incident-level behavior.\n"
        "Recommended action: Escalate to incident response, review affected hosts and accounts, block related indicators, and preserve evidence."
    )

    final_df = balanced.withColumn(
        "output",
        when(col("label_binary") == "benign", lit(benign_output))
        .when(col("label_binary") == "suspicious", lit(suspicious_output))
        .otherwise(lit(malicious_output))
    )

    final_df = final_df.select(
        "instruction",
        "input",
        "output",
        "label_binary"
    )

    # Deterministic split
    final_df = final_df.withColumn("split_rand", rand(seed=123))

    train = final_df.filter(col("split_rand") < 0.90).drop("split_rand")
    validation = final_df.filter(
        (col("split_rand") >= 0.90) & (col("split_rand") < 0.95)
    ).drop("split_rand")
    test = final_df.filter(col("split_rand") >= 0.95).drop("split_rand")

    # Write JSONL-style JSON output directories
    (
        train.select("instruction", "input", "output")
        .coalesce(args.train_partitions)
        .write.mode("overwrite")
        .json(f"{output_path}/train")
    )

    (
        validation.select("instruction", "input", "output")
        .coalesce(args.eval_partitions)
        .write.mode("overwrite")
        .json(f"{output_path}/validation")
    )

    (
        test.select("instruction", "input", "output")
        .coalesce(args.eval_partitions)
        .write.mode("overwrite")
        .json(f"{output_path}/test")
    )

    # Split counts for report
    train_counts = train.groupBy("label_binary").count().withColumn("split", lit("train"))
    val_counts = validation.groupBy("label_binary").count().withColumn("split", lit("validation"))
    test_counts = test.groupBy("label_binary").count().withColumn("split", lit("test"))

    (
        train_counts.unionByName(val_counts).unionByName(test_counts)
        .select("split", "label_binary", "count")
        .orderBy("split", "label_binary")
        .write.mode("overwrite")
        .option("header", True)
        .csv(f"{eda_path}/split_counts")
    )

    # Save a few samples for the report
    (
        final_df.select("instruction", "input", "output", "label_binary")
        .limit(20)
        .coalesce(1)
        .write.mode("overwrite")
        .json(f"{eda_path}/sample_instruction_examples")
    )

    print("Preprocessing complete.")
    spark.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--input", required=True, help="S3 input path to raw Parquet dataset")
    parser.add_argument("--output", required=True, help="S3 output path for instruction JSON")
    parser.add_argument("--eda", required=True, help="S3 output path for EDA files")
    parser.add_argument("--target-per-class", type=int, default=50000)
    parser.add_argument("--train-partitions", type=int, default=8)
    parser.add_argument("--eval-partitions", type=int, default=2)

    args = parser.parse_args()
    main(args)