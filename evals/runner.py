import json
import yaml
from pathlib import Path
from pydantic import BaseModel, Field


# Importamos directamente desde nuestra nueva estructura aplanada
from src.llm_client import LLMProvider
from src.models import TicketResponse


# --- Modelo exclusivo para el LLM-as-Judge de Evals ---
class EvalJudgeScore(BaseModel):
    score: int = Field(..., ge=1, le=5, description="Puntuación del 1 al 5 de la respuesta generada.")
    reasoning: str = Field(..., description="Breve justificación de la nota.")


def load_prompt(version: str) -> str:
    with open(f"prompts/{version}.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["system_prompt"]


def evaluate_quality_with_judge(provider: LLMProvider, query: str, answer: str, actions: list) -> int:
    """Usa un LLM para puntuar la calidad humana de la respuesta generada (LLM-as-Judge)."""
    judge_prompt = """Eres un auditor de calidad. Evalúa del 1 al 5 qué tan útil y profesional es la respuesta y las acciones sugeridas para el siguiente ticket de soporte. Solo da el puntaje y una breve razón."""
    user_msg = f"TICKET: {query}\nRESPUESTA DEL BOT: {answer}\nACCIONES SUGERIDAS: {actions}"
    
    try:
        data, _ = provider.generate_structured(judge_prompt, user_msg, EvalJudgeScore)
        return data["score"]
    except Exception:
        return 0


def main():
    print("Iniciando suite de Evals (TicketFlow)...")
    
    provider = LLMProvider(provider_name="openai") # Por defecto usará OpenAI (o el que hayas configurado)
    
    # Cargar dataset
    with open("evals/dataset.jsonl", "r", encoding="utf-8") as f:
        dataset = [json.loads(line) for line in f if line.strip()]
    
    prompts_to_test = ["triage_v1", "triage_v2", "triage_v3"]
    final_report = []

    for version in prompts_to_test:
        print(f"\n--- Evaluando {version} ---")
        try:
            system_prompt = load_prompt(version)
        except FileNotFoundError:
            print(f"Archivo prompts/{version}.yaml no encontrado. Saltando...")
            continue

        correct_categories = 0
        quality_scores = []
        
        for case in dataset:
            query = case["query"]
            expected_category = case["expected_category"]
            
            try:
                # 1. Generar respuesta con el prompt actual
                response_data, _ = provider.generate_structured(system_prompt, query, TicketResponse)
                predicted_category = response_data["category"]
                
                # 2. Métrica 1: Exact Match (Categoría)
                is_correct = (predicted_category == expected_category)
                if is_correct:
                    correct_categories += 1
                    
                    # 3. Métrica 2: LLM-as-Judge (Solo si acertó la categoría)
                    score = evaluate_quality_with_judge(
                        provider, query, response_data["answer"], response_data["actions"]
                    )
                    if score > 0:
                        quality_scores.append(score)
                        
            except Exception as e:
                print(f"Error procesando caso '{query[:20]}...': {e}")
        
        # Calcular métricas finales de la versión
        total_cases = len(dataset)
        accuracy = (correct_categories / total_cases) * 100 if total_cases else 0
        avg_quality = (sum(quality_scores) / len(quality_scores)) if quality_scores else 0
        
        print(f"Exact Match (Categoría): {accuracy:.1f}% ({correct_categories}/{total_cases})")
        print(f"Score Promedio Calidad (Judge): {avg_quality:.1f}/5.0")
        
        final_report.append({
            "prompt_version": version,
            "cases_tested": total_cases,
            "accuracy_percentage": round(accuracy, 2),
            "avg_quality_score": round(avg_quality, 2)
        })

    # Guardar resultados para que el alumno analice
    Path("evals/results.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print("\nResultados guardados en evals/results.json")


if __name__ == "__main__":
    main()