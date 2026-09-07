import json
from collections import defaultdict

from ticketflow.config import get_settings
from ticketflow.pipeline.triage import TriagePipeline


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


def main() -> None:
    settings = get_settings()

    dataset = load_jsonl(
        "evals/dataset.jsonl"
    )

    pipeline = TriagePipeline()

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

        print(
            f"{case['id']}: "
            f"{results[-1][1]}"
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

    print("\nTicketFlow Evaluation")
    print("=====================")

    print(
        f"Provider: "
        f"{settings.llm_provider}"
    )

    print(
        f"Model: "
        f"{settings.llm_model}"
    )

    print(
        f"Prompt: "
        f"{settings.prompt_version}"
    )

    print(
        f"Cases: {total}"
    )

    print(
        f"Overall accuracy: "
        f"{accuracy:.2%}"
    )

    print("\nBy category:")

    for category in sorted(by_category):

        values = by_category[category]

        score = (
            sum(values)
            / len(values)
        )

        print(
            f"{category:10} "
            f"{score:.2%}"
        )


if __name__ == "__main__":
    main()