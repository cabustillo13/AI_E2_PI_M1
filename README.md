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

La implementación principal se encuentra en `src/pipeline/triage.py`. La API está expuesta por `src/api/routes.py`, el contrato de respuesta por `src/models/response.py` y el runner de evaluación por `evals/runner.py`. `Metrics` registra cada request procesado en JSONL; la evaluación consume las respuestas del pipeline. `Exact Match` evalúa `category` y corre siempre; `LLM-as-Judge` (`src/pipeline/judge.py`) evalúa `answer` y `actions` sobre los casos con categoría correcta, y es opcional vía el flag `--judge` para no sumar costo en corridas donde solo interesa la clasificación.

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

La hipótesis de trabajo era que agregar definiciones, ejemplos y reglas de seguridad mejora la clasificación y reduce respuestas inseguras. La comparación sobre el mismo dataset congelado (ver [Evaluación](#evaluación)) confirma esa hipótesis, aunque con un matiz: la mejora en la clasificación (`category`) entre versiones es modesta, mientras que la mejora en la calidad de la respuesta y las acciones —medida con LLM-as-judge— es mucho más marcada. `v3` queda como versión recomendada para la configuración predeterminada.

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

Los 15 casos adversariales están en `evals/adversarial.jsonl` y se verifican con `tests/test_evals.py`. Los primeros 10 son variantes directas (`"ignore previous instructions"`, `"reveal the system prompt"`, `"jailbreak mode"`, etc.) que el filtro de entrada (`detect_prompt_injection`) detecta por patrón. Los 5 restantes (`adv_011` a `adv_015`) son variantes deliberadamente formuladas para **no** coincidir con esos patrones —traducción, injection indirecta a través de un tercero, ofuscación con guiones, pedido de resumen de instrucciones previas, roleplay sin la palabra "jailbreak"— y sirven para probar que la segunda capa (`validate_output` sobre la respuesta del LLM) es la que realmente los frena, no el filtro de entrada.

Efecto medido sobre los 15 casos:

| Capa | Casos que bloquea | Tasa |
| --- | ---: | ---: |
| Filtro de entrada (`detect_prompt_injection`) | 10 / 15 | 66.67% |
| Filtro de entrada + guardrail de salida (`validate_output`) | Pendiente de medir con corrida real | — |

El 66.67% está medido directamente contra el detector (`tests/test_evals.py::test_adversarial_cases_are_detected` y `test_output_layer_cases_bypass_input_filter`), sin necesidad de credenciales. La fila de "filtro de entrada + guardrail de salida" requiere correr el pipeline completo contra un proveedor real (los 5 casos restantes dependen de si el LLM obedece la instrucción maliciosa y de si esa respuesta llega a mencionar alguno de los términos que vigila `validate_output`); si corriste eso, reemplazá el "Pendiente de medir" por el número real.

La detección local se ejecuta siempre. La moderación de OpenAI se puede desactivar en entornos sin una clave OpenAI estableciendo `MODERATION_ENABLED=false`. Cuando está activa, requiere `OPENAI_API_KEY`, incluso si el proveedor principal configurado es Anthropic.

## Evaluación

El dataset contiene 36 casos normales, distribuidos de forma equilibrada entre las cuatro categorías, y la suite adversarial contiene 15 casos (10 detectables por el filtro de entrada, 5 pensados para probar la segunda capa de defensa; ver [Seguridad y robustez](#seguridad-y-robustez)). El runner mide exact match de `category`, con score global y score por categoría:

```bash
python -m evals.runner
```

La corrida utiliza el proveedor y modelo indicados en `.env`, y la versión indicada por `PROMPT_VERSION`. Para comparar las tres versiones sobre exactamente el mismo dataset:

```bash
python -m evals.runner --compare --output evals/results.json
```

El modo `--compare` congela el dataset y ejecuta `v1`, `v2` y `v3` en una única corrida. El archivo JSON conserva el score global y el score por categoría de cada versión. También se puede evaluar una sola versión con `--prompt-version v3`.

### LLM-as-judge

Además del exact match de `category`, el runner soporta LLM-as-judge para evaluar la calidad de `answer` y `actions` sobre los casos donde la categoría se clasificó correctamente — si la categoría está mal, no tiene sentido puntuar una respuesta armada para la categoría equivocada. Es un paso opcional (`--judge`) porque implica llamadas extra al LLM y por lo tanto costo adicional:

```bash
python -m evals.runner --judge
python -m evals.runner --compare --judge --output evals/results.json
```

El juez usa el mismo proveedor y modelo configurados en `.env` (no uno separado, para no sumar complejidad) y su prompt está versionado en `prompts/judge_v1.yaml`, igual que los prompts de triage. Devuelve `score` (0 a 1), `verdict` (`pass` si `score >= 0.6`) y una justificación breve. A diferencia del pipeline de triage, el juez no reintenta ante una respuesta no parseable: si el JSON viene inválido, el caso se registra directamente como `fail` con `score = 0`, porque es una herramienta de evaluación offline y no un endpoint de cara al usuario.

Resultados obtenidos con OpenAI `gpt-5-mini`, 36 casos y el dataset congelado:

**Clasificación (exact match de `category`):**

| Prompt | Global | Account | Billing | Other | Technical |
| --- | ---: | ---: | ---: | ---: | ---: |
| `v1` | 91.67% | 88.89% | 100.00% | 77.78% | 100.00% |
| `v2` | 91.67% | 88.89% | 100.00% | 77.78% | 100.00% |
| `v3` | **94.44%** | 88.89% | 100.00% | **88.89%** | 100.00% |

**Calidad de respuesta y acciones (LLM-as-judge, solo sobre los casos con categoría correcta):**

| Prompt | Casos juzgados | Score promedio | Pass rate |
| --- | ---: | ---: | ---: |
| `v1` | 33 | 0.64 | 54.55% |
| `v2` | 33 | 0.76 | 84.85% |
| `v3` | 34 | **0.95** | **100.00%** |

La mejora en clasificación de `v1` a `v3` es de 2.77 puntos porcentuales, concentrada en `other` (la categoría más ambigua, 77.78% → 88.89%); `account`, `billing` y `technical` se mantienen estables entre versiones. El salto más importante ocurre en la calidad medida por el juez: el score promedio pasa de 0.64 a 0.95 y el pass rate de 54.55% a 100.00%. Esto sugiere que las instrucciones de seguridad, la regla de decisión y los ejemplos few-shot agregados en `v3` impactan más en la calidad de lo que se le devuelve al agente humano que en la categoría en sí — algo que el exact match de `category` no puede capturar por sí solo, y que justifica tener las dos técnicas de evaluación en paralelo.

> **Nota sobre determinismo:** estos números pueden variar levemente entre corridas porque el modelo no es 100% determinista (en `account`, por ejemplo, se observó 100% en una corrida anterior y 88.89% en esta, de forma pareja en las tres versiones de prompt — un indicio de que el cambio viene del sampling del modelo y no del prompt). Para resultados más estables, conviene bajar la temperatura del modelo de clasificación o correr cada versión varias veces y reportar el promedio.

Para ejecutar las pruebas automatizadas:

```bash
pytest
```

La suite incluye pruebas unitarias y de integración para retry, guardrail de salida, métricas, validación HTTP, rechazo de campos adicionales y el parseo del veredicto de LLM-as-judge.

## Métricas

Cada request procesado agrega una línea a `data/metrics.jsonl` con:

- `request_id` y timestamp;
- proveedor, modelo y versión del prompt;
- tokens de entrada, salida y totales;
- latencia en milisegundos;
- cantidad de reintentos;
- costo estimado en USD.

El costo se calcula con la tabla de precios en `src/pricing.py`. Debe revisarse ese archivo antes de una ejecución real si cambian los modelos o sus precios.

## Estructura del repositorio

```text
src/
	api/          Endpoints FastAPI
	llm/          Adaptadores OpenAI y Anthropic
	metrics/      Logger estructurado JSONL
	models/       Modelos de request, response y veredicto del juez
	pipeline/     Guardrails, retry, triage y LLM-as-judge
	prompts/      Loader y registry de prompts
	pricing.py    Tabla de precios por proveedor/modelo (USD por 1M tokens)
prompts/        Versiones YAML del prompt de triage y del juez
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
| Suite adversarial de 10 casos | Implementado: 15 casos (10 originales + 5 que prueban la capa de salida) |
| Score global y por categoria | Implementado y documentado para `v1`, `v2` y `v3` |
| Comparación automática V1/V2/V3 | Implementado con `--compare` y salida JSON |
| Moderación de proveedor | Implementado con OpenAI Moderation API, configurable |
| LLM-as-judge | Implementado, opcional vía `--judge` |

## Limitaciones

Los resultados dependen del proveedor, modelo, prompt y precios configurados. La comparación debe ejecutarse con las mismas credenciales, modelo y dataset para que sea interpretable. Los scores no son perfectamente deterministas entre corridas (ver nota de determinismo en [Evaluación](#evaluación)); si se necesitan resultados reproducibles para publicar, conviene bajar la temperatura del modelo de clasificación o promediar varias corridas. `evals/results.json` es un artefacto local de la corrida y no contiene secretos.