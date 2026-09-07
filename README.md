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
| `MODERATION_ENABLED` | `true` | Activa moderación de entrada y salida con OpenAI |
| `MODERATION_MODEL` | `omni-moderation-latest` | Modelo de moderación de OpenAI |
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

La hipótesis de trabajo era que agregar definiciones, ejemplos y reglas de seguridad mejora la clasificación y reduce respuestas inseguras. La comparación sobre el mismo dataset congelado confirma una mejora progresiva de la clasificación: `v1` obtiene 91.67%, `v2` 94.44% y `v3` 97.22%. Por lo tanto, `v3` queda como versión recomendada para la configuración predeterminada.

## Seguridad y robustez

Actualmente se implementan estas capas:

- detección de patrones conocidos de prompt injection, jailbreak y exfiltración;
- moderación de entrada con OpenAI Moderation API cuando `MODERATION_ENABLED=true`;
- límite de longitud de entrada;
- instrucción en `v3` para tratar el ticket como dato no confiable;
- parseo JSON y validación estricta con Pydantic;
- bloqueo de respuestas que intenten revelar API keys, system prompts o developer messages;
- moderación de la respuesta y de las acciones sugeridas con OpenAI Moderation API;
- reintentos configurables ante respuestas inválidas.

Los 10 casos adversariales están en `evals/adversarial.jsonl` y se verifican con `evals/test_triage.py`.

La detección local se ejecuta siempre. La moderación de OpenAI se puede desactivar en entornos sin una clave OpenAI estableciendo `MODERATION_ENABLED=false`. Cuando está activa, requiere `OPENAI_API_KEY`, incluso si el proveedor principal configurado es Anthropic.

## Evaluación

El dataset contiene 36 casos normales, distribuidos de forma equilibrada entre las cuatro categorías, y la suite adversarial contiene 10 casos. El runner mide exact match de `category`, con score global y score por categoría:

```bash
python -m evals.runner
```

La corrida utiliza el proveedor y modelo indicados en `.env`, y la versión indicada por `PROMPT_VERSION`. Para comparar las tres versiones sobre exactamente el mismo dataset:

```bash
python -m evals.runner --compare --output evals/results.json
```

El modo `--compare` congela el dataset y ejecuta `v1`, `v2` y `v3` en una única corrida. El archivo JSON conserva el score global y el score por categoría de cada versión. También se puede evaluar una sola versión con `--prompt-version v3`.

Resultados obtenidos con OpenAI `gpt-5-mini`, 36 casos y el dataset congelado:

| Prompt | Global | Account | Billing | Other | Technical |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v1` | 91.67% | 100.00% | 100.00% | 66.67% | 100.00% |
| `v2` | 94.44% | 100.00% | 100.00% | 77.78% | 100.00% |
| `v3` | **97.22%** | 100.00% | 100.00% | **88.89%** | 100.00% |

La mejora absoluta de `v1` a `v3` es de 5.55 puntos porcentuales. El avance se concentra en `other`, la categoría más ambigua: sube de 66.67% a 88.89%. Las categorías `account`, `billing` y `technical` mantienen 100.00% en las tres versiones. Estos resultados justifican el uso de definiciones, reglas de decisión y ejemplos few-shot incorporados en `v3`.

Para ejecutar las pruebas automatizadas:

```bash
pytest
```

La suite incluye pruebas unitarias y de integración para retry, guardrail de salida, métricas, validación HTTP y rechazo de campos adicionales.

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
evals/          Dataset, casos adversariales y runner
tests/          Tests unitarios, de integración y de evaluación
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
| Dataset etiquetado de al menos 30 casos | Implementado: 36 casos normales, 9 por categoría |
| Suite adversarial de 10 casos | Implementado |
| Score global y por categoria | Implementado y documentado para `v1`, `v2` y `v3` |
| Comparación automática V1/V2/V3 | Implementado con `--compare` y salida JSON |
| Moderación de proveedor | Implementado con OpenAI Moderation API, configurable |
| LLM-as-judge | Opcional y pendiente |

## Próximos pasos para la entrega final

1. Implementar LLM-as-judge para evaluar `answer` y `actions` en los casos clasificados correctamente, manteniendo exact match para `category`.

## Limitaciones

Los resultados dependen del proveedor, modelo, prompt y precios configurados. La comparación debe ejecutarse con las mismas credenciales, modelo y dataset para que sea interpretable. `evals/results.json` es un artefacto local de la corrida y no contiene secretos.