# TicketFlow: triage inteligente de tickets

TicketFlow es el proyecto integrador del módulo 1 de AI Engineering 2.0 para Nubbix, un SaaS de gestión para pymes de LATAM. El servicio recibe una consulta de soporte en texto libre y devuelve una respuesta estructurada, clasificada y validada para asistir al equipo de soporte de nivel 1.

## Objetivo

El servicio automatiza el primer triage de tickets en cuatro categorías:

- `billing`: facturación, cobros, pagos, planes, suscripciones o reembolsos.
- `technical`: errores, caídas, integraciones, rendimiento o funcionalidades que no funcionan.
- `account`: acceso, login, contraseña, perfil, permisos o configuración de cuenta.
- `other`: consultas que no encajan claramente en las categorías anteriores.

El proyecto busca cumplir los objetivos de las cinco clases del módulo:

1. Integrar dos proveedores LLM configurables y registrar costo, latencia y tokens.
2. Aplicar context engineering mediante prompts versionados fuera del código.
3. Validar una salida estructurada con Pydantic y reintentar respuestas no parseables.
4. Detectar prompt injection y proteger la entrada y la salida.
5. Evaluar la calidad con un dataset etiquetado y métricas globales y por categoría.

## Arquitectura

```text
									  TICKETFLOW
										  │
							┌─────────────┼──────────────┐
							│             │              │
							▼             ▼              ▼
						  FastAPI       Guardrails      Metrics
							│             │              │
							└───────┬─────┘              ▼
								   ▼             data/metrics.jsonl
							 Context Engineering
								   │
							  V1 / V2 / V3
								   │
								   ▼
							┌───────────────┐
							│  LLM Provider │
							├───────────────┤
							│    OpenAI     │
							│   Anthropic   │
							└───────┬───────┘
								   ▼
							 Structured Output
								   │
							   Pydantic
								   │
								 Retry
								   │
								   ▼
							    EVALUATION
								   │
						   ┌─────────┴────────┐
						   ▼                  ▼
					    Exact Match       LLM-as-Judge
```

La implementación principal se encuentra en `src/pipeline/triage.py`. La API está expuesta por `src/api/routes.py`, el contrato de respuesta por `src/models/response.py` y el runner de evaluación por `evals/runner.py`. `Metrics` registra cada request procesado en JSONL; la evaluación consume las respuestas del pipeline. `Exact Match` está implementado y `LLM-as-Judge` queda como evaluación opcional pendiente.

## Requisitos

- Python 3.10 o superior.
- Una API key de OpenAI o Anthropic, según el proveedor elegido.

## Instalación

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Completar en `.env` solamente la clave del proveedor elegido. Las claves no deben subirse al repositorio.

## Configuración

Las variables soportadas son:

| Variable | Valor predeterminado | Descripción |
| --- | --- | --- |
| `OPENAI_API_KEY` | vacío | API key para OpenAI |
| `ANTHROPIC_API_KEY` | vacío | API key para Anthropic |
| `LLM_PROVIDER` | `openai` | Proveedor: `openai` o `anthropic` |
| `LLM_MODEL` | `gpt-5-mini` | Modelo utilizado por el proveedor |
| `PROMPT_VERSION` | `v3` | Prompt congelado: `v1`, `v2` o `v3` |
| `MAX_RETRIES` | `2` | Reintentos ante JSON o salida inválida |
| `MAX_INPUT_CHARS` | `4000` | Longitud máxima de la consulta |
| `METRICS_PATH` | `data/metrics.jsonl` | Archivo de métricas estructuradas |
| `PROMPTS_PATH` | `prompts` | Directorio de prompts YAML |

## Uso de la API

Iniciar el servidor desde la raíz del proyecto:

```bash
uvicorn src.main:app --reload
```

La API queda disponible en `http://127.0.0.1:8000`.

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Respuesta:

```json
{"status":"ok"}
```

Triage:

```bash
curl -X POST http://127.0.0.1:8000/triage \
	-H "Content-Type: application/json" \
	-d '{"query":"Me cobraron dos veces este mes"}'
```

Contrato de respuesta:

```json
{
	"answer": "I can help review the duplicate charge.",
	"confidence": 0.95,
	"category": "billing",
	"actions": ["Review the two charges"]
}
```

Pydantic rechaza campos adicionales, categorías fuera del conjunto permitido, `confidence` fuera del rango `0..1`, respuestas vacías y listas de acciones vacías. Una consulta bloqueada por un guardrail devuelve HTTP 400.

## Context engineering

Los prompts viven en `prompts/` y se seleccionan mediante `PROMPT_VERSION`; no están hardcodeados en la lógica de negocio.

- `v1`: zero-shot, con el contrato de salida.
- `v2`: definiciones de categorías y ejemplos few-shot.
- `v3`: definiciones, regla de decisión, instrucciones de seguridad, contrato estricto y ejemplos few-shot.

La hipótesis de trabajo es que agregar definiciones, ejemplos y reglas de seguridad mejora la clasificación y reduce respuestas inseguras. Esta hipótesis debe validarse con el dataset congelado, no mediante la inspección de unos pocos tickets.

## Seguridad y robustez

Actualmente se implementan estas capas locales:

- detección de patrones conocidos de prompt injection, jailbreak y exfiltración;
- límite de longitud de entrada;
- instrucción en `v3` para tratar el ticket como dato no confiable;
- parseo JSON y validación estricta con Pydantic;
- bloqueo de respuestas que intenten revelar API keys, system prompts o developer messages;
- reintentos configurables ante respuestas inválidas.

Los 10 casos adversariales están en `evals/adversarial.jsonl` y se verifican con `evals/test_triage.py`.

> La Moderation API de OpenAI todavía no está integrada. El guardrail actual es local y está basado en reglas; incorporar moderación del proveedor es una mejora pendiente para cubrir completamente la alternativa propuesta en la consigna.

## Evaluación

El dataset actual contiene 12 casos normales, distribuidos entre las cuatro categorías, y la suite adversarial contiene 10 casos. El runner mide exact match de `category`, con score global y score por categoría:

```bash
python -m evals.runner
```

La corrida utiliza el proveedor, modelo y versión indicados en `.env`. Por lo tanto, para comparar `v1`, `v2` y `v3` hay que ejecutar el runner con cada `PROMPT_VERSION` y conservar los resultados de forma separada. El runner actual no genera todavía una tabla comparativa automática ni evalúa la calidad de `answer` con LLM-as-judge.

Para ejecutar las pruebas automatizadas:

```bash
pytest
```

## Métricas

Cada request procesado agrega una línea a `data/metrics.jsonl` con:

- `request_id` y timestamp;
- proveedor, modelo y versión del prompt;
- tokens de entrada, salida y totales;
- latencia en milisegundos;
- cantidad de reintentos;
- costo estimado en USD.

El costo se calcula con la tabla de precios definida en `src/pipeline/triage.py`. Debe revisarse antes de una ejecución real si cambian los modelos o sus precios.

## Estructura del repositorio

```text
src/
	api/          Endpoints FastAPI
	llm/          Adaptadores OpenAI y Anthropic
	metrics/      Logger estructurado JSONL
	models/       Modelos de request y response
	pipeline/     Guardrails, retry y triage
	prompts/      Loader y registry de prompts
prompts/        Versiones YAML del prompt
evals/          Dataset, casos adversariales, runner y tests
tests/          Tests unitarios
	data/           Salida local de métricas
```

## Estado frente a la consigna

| Requisito | Estado actual |
| --- | --- |
| API HTTP funcional | Implementado con FastAPI (`/health` y `/triage`) |
| Dos proveedores configurables | Implementado: OpenAI y Anthropic |
| Salida JSON validada | Implementado con Pydantic |
| Retry ante respuesta inválida | Implementado y configurable |
| Prompts versionados fuera del código | Implementado: `v1`, `v2`, `v3` |
| Tokens, latencia y costo por request | Implementado en JSONL |
| Dataset etiquetado de al menos 30 casos | Pendiente: actualmente hay 12 casos normales |
| Suite adversarial de 10 casos | Implementado |
| Score global y por categoria | Implementado para una version por corrida |
| Comparación automática V1/V2/V3 | Pendiente |
| Moderación de proveedor | Pendiente; hoy hay reglas locales |
| LLM-as-judge | Opcional y pendiente |

## Próximos pasos para la entrega final

1. Ampliar el dataset normal a 30 casos como mínimo, idealmente con casos ambiguos y una distribución equilibrada.
2. Automatizar la comparación de `v1`, `v2` y `v3` en una única corrida reproducible.
3. Publicar en este README la tabla de accuracy global y por categoría obtenida con el dataset congelado.
4. Agregar la Moderation API como segunda capa cuando el proveedor sea compatible, manteniendo el guardrail local.
5. Evaluar `answer` con LLM-as-judge solamente como métricas complementarias o extra credit.

## Limitaciones

Los resultados dependen del proveedor, modelo, prompt y precios configurados. El dataset actual es inicial y no alcanza todavía el mínimo de 30 casos normales solicitado por la consigna. Por ese motivo, este README documenta el estado verificable del repositorio y no presenta resultados de evaluación que aún no hayan sido medidos.