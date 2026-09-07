import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.config import get_settings
from src.pipeline.triage import TriagePipeline


def load_jsonl(path: str) -> list[dict]:
    with open(
        path,
        encoding="utf-8",
    ) as file:
        return [
            json.loads(line)
            for line in file
            if line.strip()
        ]


def evaluate(
    pipeline: TriagePipeline,
    dataset: list[dict],
    prompt_version: str,
) -> dict:
    pipeline.settings.prompt_version = prompt_version
    results = []

    for case in dataset:

        try:
            response = pipeline.run(
                case["query"]
            )

            predicted = response.category.value

            correct = (
                predicted
                == case["expected_category"]
            )

            results.append(
                (
                    case,
                    predicted,
                    correct,
                )
            )

        except Exception as exc:

            results.append(
                (
                    case,
                    f"ERROR: {exc}",
                    False,
                )
            )

    total = len(results)

    accuracy = (
        sum(
            correct
            for _, _, correct in results
        )
        / total
        if total
        else 0
    )

    by_category = defaultdict(list)

    for case, _, correct in results:
        by_category[
            case["expected_category"]
        ].append(correct)

    return {
        "prompt_version": prompt_version,
        "cases": total,
        "overall_accuracy": accuracy,
        "by_category": {
            category: sum(values) / len(values)
            for category, values in sorted(
                by_category.items()
            )
        },
    }


def print_report(
    summaries: list[dict],
    provider: str,
    model: str,
) -> None:
    print("\nTicketFlow Evaluation")
    print("=====================")
    print(f"Provider: {provider}")
    print(f"Model: {model}")

    for summary in summaries:
        print(f"\nPrompt: {summary['prompt_version']}")
        print(f"Cases: {summary['cases']}")
        print(
            "Overall accuracy: "
            f"{summary['overall_accuracy']:.2%}"
        )
        print("By category:")

        for category, score in summary["by_category"].items():
            print(f"{category:10} {score:.2%}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run TicketFlow prompt evaluations."
    )
    parser.add_argument(
        "--prompt-version",
        help="Evaluate one prompt version.",
    )
    parser.add_argument(
        "--compare",
        action="store_true",
        help="Evaluate v1, v2 and v3 using the same dataset.",
    )
    parser.add_argument(
        "--output",
        help="Write the evaluation summaries to a JSON file.",
    )
    args = parser.parse_args()

    if args.compare and args.prompt_version:
        parser.error(
            "--compare and --prompt-version cannot be combined"
        )

    settings = get_settings()
    dataset = load_jsonl("evals/dataset.jsonl")
    pipeline = TriagePipeline()

    versions = (
        ["v1", "v2", "v3"]
        if args.compare
        else [args.prompt_version or settings.prompt_version]
    )
    summaries = [
        evaluate(pipeline, dataset, version)
        for version in versions
    ]

    print_report(
        summaries,
        settings.llm_provider,
        settings.llm_model,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(summaries, indent=2),
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()