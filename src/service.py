import yaml
from pathlib import Path
from src.models import TicketRequest, TicketResponse, JudgeResponse
from src.llm_client import LLMProvider
from src.metrics import log_metric


def load_prompt(version: str) -> str:
    """Carga el system prompt desde un archivo YAML."""
    prompt_path = Path("prompts") / f"{version}.yaml"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["system"]


def process_ticket(request: TicketRequest, provider: LLMProvider) -> TicketResponse:
    # 1. GUARDRAIL: Moderación de entrada
    if provider.check_moderation(request.ticket):
        return TicketResponse(
            category="other",
            confidence="high",
            answer="La consulta contiene material bloqueado por políticas de seguridad.",
            actions=["Revisar términos de servicio"]
        )

    # 2. CONTEXT ENGINEERING: Cargar el prompt ganador de las evals
    system_prompt = load_prompt("triage_v3")

    # 3. GENERACIÓN: Llamada principal con salida estructurada
    response_data, metrics = provider.generate_structured(
        system_prompt=system_prompt,
        user_message=request.ticket,
        response_model=TicketResponse
    )
    
    ticket_response = TicketResponse(**response_data)

    # 4. EXTRA CREDIT (LLM-as-Judge): Segunda instancia si la confianza es baja
    if ticket_response.confidence == "low":
        judge_prompt = load_prompt("judge_v1")
        judge_context = f"Ticket original: {request.ticket}\nClasificación dudosa: {ticket_response.model_dump_json()}"
        
        # Usamos un modelo más inteligente/grande para juzgar (ej. gpt-4o en lugar de mini)
        judge_data, judge_metrics = provider.generate_structured(
            system_prompt=judge_prompt,
            user_message=judge_context,
            response_model=JudgeResponse,
            model="gpt-4o" if provider.provider_name == "openai" else "claude-3-5-sonnet-20240620"
        )
        
        # Aplicamos la corrección
        ticket_response.category = judge_data.get("corrected_category", ticket_response.category)
        
        # Sumamos las métricas de la segunda llamada
        metrics["cost_usd"] += judge_metrics["cost_usd"]
        metrics["input_tokens"] += judge_metrics["input_tokens"]
        metrics["output_tokens"] += judge_metrics["output_tokens"]
        metrics["judge_invoked"] = True

    # 5. OBSERVABILIDAD: Registrar métricas
    log_metric(request.ticket, ticket_response.category, metrics)

    return ticket_response