# TicketFlow: triage inteligente de tickets

TicketFlow es el proyecto integrador del modulo 1 de AI Engineering 2.0 para Nubbix, un SaaS de gestion para pymes de LATAM. El servicio recibe una consulta de soporte en texto libre y devuelve una respuesta estructurada, clasificada y validada para asistir al equipo de soporte de nivel 1.

## Objetivo

El servicio automatiza el primer triage de tickets en cuatro categorias:

- `billing`: facturacion, cobros, pagos, planes, suscripciones o reembolsos.
- `technical`: errores, caidas, integraciones, rendimiento o funcionalidades que no funcionan.
- `account`: acceso, login, contrasena, perfil, permisos o configuracion de cuenta.
- `other`: consultas que no encajan claramente en las categorias anteriores.

El proyecto busca cumplir los objetivos de las cinco clases del modulo:

1. Integrar dos proveedores LLM configurables y registrar costo, latencia y tokens.
2. Aplicar context engineering mediante prompts versionados fuera del codigo.
3. Validar una salida estructurada con Pydantic y reintentar respuestas no parseables.
4. Detectar prompt injection y proteger la entrada y la salida.
5. Evaluar la calidad con un dataset etiquetado y metricas globales y por categoria.

## Arquitectura

```text
FastAPI
	-> validacion de request
	-> guardrail de entrada (longitud + prompt injection)
	-> registro de prompts YAML
	-> proveedor LLM (OpenAI o Anthropic)
	-> parseo JSON + validacion Pydantic
	-> retry ante respuesta invalida
	-> guardrail de salida
	-> metricas JSONL
```

La implementacion principal se encuentra en `src/pipeline/triage.py`. La API esta expuesta por `src/api/routes.py` y el contrato de respuesta por `src/models/response.py`.

## Requisitos

- Python 3.10 o superior.
- Una API key de OpenAI o Anthropic, según el proveedor elegido.

## Instalacion

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

Completar en `.env` solamente la clave del proveedor elegido. Las claves no deben commitearse.

## Configuracion

Las variables soportadas son:

| Variable | Default | Descripcion |
| --- | --- | --- |
| `OPENAI_API_KEY` | vacio | API key para OpenAI |
| `ANTHROPIC_API_KEY` | vacio | API key para Anthropic |
| `LLM_PROVIDER` | `openai` | Proveedor: `openai` o `anthropic` |
| `LLM_MODEL` | `gpt-5-mini` | Modelo utilizado por el proveedor |
| `PROMPT_VERSION` | `v3` | Prompt congelado: `v1`, `v2` o `v3` |
| `MAX_RETRIES` | `2` | Reintentos ante JSON o salida inválida |
| `MAX_INPUT_CHARS` | `4000` | Longitud máxima de la consulta |
| `METRICS_PATH` | `data/metrics.jsonl` | Archivo de mátricas estructuradas |
| `PROMPTS_PATH` | `prompts` | Directorio de prompts YAML |

## Uso de la API

Iniciar el servidor desde la raiz del proyecto:

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

Pydantic rechaza campos adicionales, categorias fuera del conjunto permitido, `confidence` fuera del rango `0..1`, respuestas vacias y listas de acciones vacias. Una consulta bloqueada por un guardrail devuelve HTTP 400.

## Context engineering

Los prompts viven en `prompts/` y se seleccionan mediante `PROMPT_VERSION`; no estan hardcodeados en la lógica de negocio.

- `v1`: zero-shot, con el contrato de salida.
- `v2`: definiciones de categorías y ejemplos few-shot.
- `v3`: definiciones, regla de decisión, instrucciones de seguridad, contrato estricto y ejemplos few-shot.

La hipotesis de trabajo es que agregar definiciones, ejemplos y reglas de seguridad mejora la clasificacion y reduce respuestas inseguras. Esta hipotesis debe validarse con el dataset congelado, no mediante la inspeccion de unos pocos tickets.

## Seguridad y robustez

Actualmente se implementan estas capas locales:

- deteccion de patrones conocidos de prompt injection, jailbreak y exfiltracion;
- limite de longitud de entrada;
- instruccion en `v3` para tratar el ticket como dato no confiable;
- parseo JSON y validacion estricta con Pydantic;
- bloqueo de respuestas que intenten revelar API keys, system prompts o developer messages;
- reintentos configurables ante respuestas invalidas.

Los 10 casos adversariales estan en `evals/adversarial.jsonl` y se verifican con `evals/test_triage.py`.

> La Moderation API de OpenAI todavia no esta integrada. El guardrail actual es local y basado en reglas; incorporar moderacion de proveedor es una mejora pendiente para cubrir completamente la alternativa propuesta en la consigna.

## Evaluacion

El dataset actual contiene 12 casos normales, distribuidos entre las cuatro categorias, y la suite adversarial contiene 10 casos. El runner mide exact match de `category`, con score global y score por categoria:

```bash
python -m evals.runner
```

La corrida utiliza el proveedor, modelo y version indicados en `.env`. Por lo tanto, para comparar `v1`, `v2` y `v3` hay que ejecutar el runner con cada `PROMPT_VERSION` y conservar los resultados de forma separada. El runner actual no genera todavia una tabla comparativa automatica ni evalua la calidad de `answer` con LLM-as-judge.

Para ejecutar las pruebas automatizadas:

```bash
pytest
```

## Metricas

Cada request procesado agrega una linea a `data/metrics.jsonl` con:

- `request_id` y timestamp;
- proveedor, modelo y version del prompt;
- tokens de entrada, salida y totales;
- latencia en milisegundos;
- cantidad de reintentos;
- costo estimado en USD.

El costo se calcula con la tabla de precios definida en `src/pipeline/triage.py`. Debe revisarse antes de una ejecucion real si cambian los modelos o sus precios.

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
data/           Salida local de metricas
```

## Estado frente a la consigna

| Requisito | Estado actual |
| --- | --- |
| API HTTP funcional | Implementado con FastAPI (`/health` y `/triage`) |
| Dos proveedores configurables | Implementado: OpenAI y Anthropic |
| Salida JSON validada | Implementado con Pydantic |
| Retry ante respuesta invalida | Implementado y configurable |
| Prompts versionados fuera del codigo | Implementado: `v1`, `v2`, `v3` |
| Tokens, latencia y costo por request | Implementado en JSONL |
| Dataset etiquetado de al menos 30 casos | Pendiente: actualmente hay 12 casos normales |
| Suite adversarial de 10 casos | Implementado |
| Score global y por categoria | Implementado para una version por corrida |
| Comparacion automatica V1/V2/V3 | Pendiente |
| Moderacion de proveedor | Pendiente; hoy hay reglas locales |
| LLM-as-judge | Opcional y pendiente |

## Proximos pasos para la entrega final

1. Ampliar el dataset normal a 30 casos como minimo, idealmente con casos ambiguos y una distribucion equilibrada.
2. Automatizar la comparacion de `v1`, `v2` y `v3` en una unica corrida reproducible.
3. Publicar en este README la tabla de accuracy global y por categoria obtenida con el dataset congelado.
4. Agregar la Moderation API como segunda capa cuando el proveedor sea compatible, manteniendo el guardrail local.
5. Evaluar `answer` con LLM-as-judge solamente como metricas complementarias o extra credit.

## Limitaciones

Los resultados dependen del proveedor, modelo, prompt y precios configurados. El dataset actual es inicial y no alcanza todavia el minimo de 30 casos normales solicitado por la consigna. Por ese motivo, este README documenta el estado verificable del repositorio y no presenta resultados de evaluacion que aun no hayan sido medidos.