# PIM1: Triage Inteligente de Tickets (Nubbix SaaS)

Proyecto integrador del Módulo 1. Este servicio automatiza el primer nivel de soporte de Nubbix: recibe consultas en texto libre, las clasifica, y devuelve un JSON estructurado listo para ser consumido por un sistema automatizado.

## Estructura del Proyecto

El proyecto está diseñado de forma minimalista para enfocar la complejidad en los prompts y las evaluaciones, no en la arquitectura:

*   `/prompts/`: Archivos YAML con las distintas versiones de tus system prompts.
*   `/evals/`: Tu laboratorio. Contiene el dataset de prueba (`dataset.jsonl`) y el script para evaluar tus prompts (`runner.py`).
*   `/src/`: El código de producción.
    *   `models.py`: Contratos de datos (Pydantic).
    *   `llm_client.py`: Conexión con OpenAI/Anthropic forzando salidas JSON.
    *   `service.py`: La lógica de negocio (Guardrails -> LLM -> Juez de Fallback).
    *   `metrics.py`: Sistema de registro de logs (costo, latencia, tokens).
    *   `main.py`: Endpoint de FastAPI.

## Setup Inicial

1. Clona el repositorio.
2. Crea un entorno virtual y actívalo:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Windows: venv\Scripts\activate
   ```

3. Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

4. Copia el archivo de variables de entorno y agrega tu API Key:
    ```bash
    cp .env.example .env
    ```

## Fase 1: Ingeniería de Contexto y Evals

Antes de levantar la API, necesitas un prompt que funcione.
No adivines la calidad de tu prompt: **mídela**.

1. Abre `evals/dataset.jsonl` y asegúrate de tener al menos 30 casos representativos.
2. Crea versiones de tu prompt en la carpeta `prompts/` (ej. `triage_v1.yaml`, `triage_v2.yaml`).
3. Corre la suite de evaluaciones:

```bash
python evals/runner.py
```

4. Analiza los resultados. El prompt ganador es el que configurarás en `src/service.py`.

## El Servicio API

Una vez que tengas un prompt ganador y tu dataset listo, levanta el servicio para producción:

```bash
python src/main.py
```

### Probar el endpoint

Envía un POST a `http://localhost:8000/api/triage`:

```bash
curl -X POST "http://localhost:8000/api/triage" \
     -H "Content-Type: application/json" \
     -d '{"ticket": "Hola, me cobraron dos veces la suscripción de este mes, necesito un reintegro."}'
```

**Respuesta esperada:**

```json
{
  "category": "billing",
  "confidence": "high",
  "answer": "Lamentamos el inconveniente con tu cobro. Hemos escalado tu caso al equipo de facturación para procesar el reintegro a la brevedad.",
  "actions": ["Verificar pagos duplicados en Stripe", "Emitir nota de crédito"]
}
```
