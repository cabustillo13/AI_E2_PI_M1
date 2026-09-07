# Precios en USD por 1M de tokens (input, output).
# Fuente: pricing pages de OpenAI y Anthropic. Revisar antes de cada
# corrida real si cambian los modelos o sus precios.
PRICING: dict[str, dict[str, tuple[float, float]]] = {
    "openai": {
        "gpt-5-mini": (0.25, 2.00),
    },
    "anthropic": {
        "claude-3-5-haiku-latest": (0.80, 4.00),
    },
}