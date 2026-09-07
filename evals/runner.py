import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.config import get_settings
from src.pipeline.judge import judge_response
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
    judge: bool = False,
    judge_prompt_version: str = "v1",
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

            # El juez solo evalúa la calidad de answer/actions cuando la
            # categoría (exact match) ya salió bien; si la clasificación
            # falló, no tiene sentido puntuar una respuesta armada para
            # la categoría equivocada.
            quality = None
            if judge and correct:
                quality = judge_response(
                    pipeline.provider,
                    pipeline.prompts,
                    judge_prompt_version,
                    case["query"],
                    predicted,
                    response.answer,
                    response.actions,
                )

            results.append(
                (
                    case,
                    predicted,
                    correct,
                    quality,
                )
            )

        except Exception as exc:

            results.append(
                (
                    case,
                    f"ERROR: {exc}",
                    False,
                    None,
                )
            )

    total = len(results)

    accuracy = (
        sum(
            correct
            for _, _, correct, _ in results
        )
        / total
        if total
        else 0
    )

    by_category = defaultdict(list)

    for case, _, correct, _ in results:
        by_category[
            case["expected_category"]
        ].append(correct)

    summary = {
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

    if judge:
        quality_scores = [
            quality.score
            for _, _, _, quality in results
            if quality is not None
        ]

        summary["quality_judged_cases"] = len(quality_scores)
        summary["avg_quality_score"] = (
            sum(quality_scores) / len(quality_scores)
            if quality_scores
            else None
        )
        summary["quality_pass_rate"] = (
            sum(
                1
                for _, _, _, quality in results
                if quality is not None and quality.verdict == "pass"
            )
            / len(quality_scores)
            if quality_scores
            else None
        )

    return summary


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

        if "avg_quality_score" in summary:
            avg_quality = summary["avg_quality_score"]
            pass_rate = summary["quality_pass_rate"]

            print(
                "LLM-as-judge "
                f"(sobre {summary['quality_judged_cases']} casos "
                "con categoría correcta):"
            )

            if avg_quality is None:
                print("  Sin casos correctos para juzgar.")
            else:
                print(f"  Score promedio: {avg_quality:.2f}")
                print(f"  Pass rate: {pass_rate:.2%}")


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
    parser.add_argument(
        "--judge",
        action="store_true",
        help=(
            "Run LLM-as-judge over answer/actions for cases where "
            "the category was classified correctly. Uses extra "
            "LLM calls, so it is off by default."
        ),
    )
    parser.add_argument(
        "--judge-prompt-version",
        default="v1",
        help="Prompt version used for the judge (default: v1).",
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
        evaluate(
            pipeline,
            dataset,
            version,
            judge=args.judge,
            judge_prompt_version=args.judge_prompt_version,
        )
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