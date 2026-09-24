# Benchmark de tokenización entre modelos de Claude

Experimento para comparar, con **la misma entrada**, cuántos tokens de entrada y salida consumen dos modelos de Claude, cuántos de esos tokens son de razonamiento y cuánto tardan en responder. Todo en paralelo y con medición de tiempo por petición.

## Qué mide

Por cada pregunta clínica se registra:

| Campo | Origen | Tipo |
|---|---|---|
| `input_tokens` | `usage.input_tokens` | exacto |
| `output_tokens` | `usage.output_tokens` (incluye razonamiento) | exacto |
| `thinking_tokens` | `usage.output_tokens_details.thinking_tokens` | exacto |
| `text_tokens` | `output_tokens - thinking_tokens` | derivado |
| `time_s` | `time.perf_counter()` alrededor de la llamada | medido |
| `cache_*_input_tokens` | `usage.*` | exacto |

> Nota: `output_tokens` ya **incluye** el razonamiento. La separación reasoning/texto se obtiene del campo exacto `output_tokens_details.thinking_tokens`.

## Modelos comparados

- `claude-opus-5-5`
- `claude-opus-5`

(`claude-opus-5-1` no existe en la cuenta; el único "5.1" disponible es `claude-fable-5-1`, de otra familia).

## Estructura del proyecto

```
prueba_claude/
├── data/
│   ├── data_original.jsonl           # 35 preguntas clínicas originales
│   ├── data.jsonl                    # 175 variantes generadas con Haiku (LLM)
│   ├── data_regex.jsonl              # 175 variantes generadas con regex
│   └── data_regex_extendido.jsonl    # 275 (las 175 + 100 más: benchmark ES + propias)
├── results/
│   ├── resultados_tokenizacion.csv                  # 350 filas (Haiku)
│   ├── resultados_tokenizacion_regex.csv            # 350 filas (regex)
│   ├── resultados_tokenizacion_regex_extendido.csv  # 550 filas (regex +100)
│   └── resumen_tokenizacion*.csv                    # agregados por modelo
├── scripts/
│   ├── benchmark_claude.py            # lanza el benchmark en paralelo
│   ├── generar_variaciones.py         # variaciones con Haiku (LLM)
│   ├── generar_variaciones_regex.py   # variaciones con regex
│   ├── extender_regex.py              # añade 100 variantes regex más
│   ├── analisis_significancia.py      # test pareado de significancia
│   └── calcular_coste.py              # coste en $ por modelo
├── requirements.txt
├── .gitignore
└── README.md
```

## Requisitos

- Python 3.12+
- Clave de Anthropic en `.env` como `ANTROPIC_API_KEY`

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install anthropic python-dotenv scipy
```

`scipy` solo es necesario para el análisis de significancia.

## Uso

Los scripts están en `scripts/` y los datos en `data/`. Ejecuta desde la raíz del proyecto.

### 1. Generar variaciones (dos métodos)

```bash
# Con Haiku (LLM): 35 -> 175
python scripts/generar_variaciones.py --input data/data_original.jsonl --out data/data.jsonl

# Con regex (sin LLM): 35 -> 175
python scripts/generar_variaciones_regex.py

# Ampliar el dataset regex con 100 variantes más (benchmark español + propias)
python scripts/extender_regex.py
```

### 2. Lanzar el benchmark

```bash
python scripts/benchmark_claude.py \
    --input data/data_regex_extendido.jsonl \
    --max-questions 1000 \
    --out results/resultados_tokenizacion_regex_extendido.csv \
    --summary-out results/resumen_tokenizacion_regex_extendido.csv
```

### 3. Análisis de significancia

```bash
python scripts/analisis_significancia.py --csv results/resultados_tokenizacion_regex_extendido.csv
```

### 4. Coste en dólares

```bash
python scripts/calcular_coste.py
```

## Opciones del benchmark

| Flag | Por defecto | Descripción |
|---|---|---|
| `--models` | `claude-opus-5-5,claude-opus-5` | Modelos a comparar (separados por coma) |
| `--input` | — | JSONL de entrada (campo `pregunta`); pasa ruta explícita |
| `--max-questions` | `100` | Máximo de preguntas a procesar |
| `--concurrency` | `8` | Peticiones concurrentes |
| `--thinking` / `--no-thinking` | activado | Modo razonamiento |
| `--effort` | `high` | `low`, `medium`, `high`, `xhigh`, `max` |
| `--max-tokens` | `8192` | Límite de tokens de salida |
| `--out` | — | CSV por petición |
| `--summary-out` | — | CSV de resumen |

> Algunos defaults de rutas de los scripts apuntan al layout antiguo; pásalas siempre explícitas.

## Notas técnicas

- Los modelos nuevos (Opus 5.x) usan la API de *adaptive thinking*:
  `thinking={"type": "adaptive"}` + `output_config={"effort": ...}`.
  El formato clásico `thinking={"type": "enabled", "budget_tokens": N}` **no** es compatible con ellos.
- El mínimo de `budget_tokens` para el formato "enabled" clásico es **1024**.
- `temperature` no está disponible en esta versión de la API.
- El `input_tokens` difiere en 2 tokens constantes entre modelos (tokenizadores distintos) con la misma entrada.

## Resultados

Se compararon dos métodos de variación y un dataset ampliado:

| Prueba | n (preguntas) | Variantes | Peticiones |
|---|---|---|---|
| 1. Haiku | 175 | generadas con LLM | 350 |
| 2. Regex | 175 | generadas con regex | 350 |
| 3. Regex +100 | 275 | regex + benchmark ES + propias | 550 |

### Diferencia en `output_tokens` (5.5 − 5) por prueba

| Prueba | n | Dif. media | Wilcoxon p | Cohen's d | ¿Significativo? |
|---|---|---|---|---|---|
| Haiku | 175 | +3.1 | 0.61 | +0.02 | No |
| Regex | 175 | +24.4 | 0.073 | +0.14 | No (cerca) |
| Regex +100 | 275 | +10.9 | 0.18 | +0.05 | No |

En las tres pruebas **no hay diferencia estadísticamente significativa en tokens
de salida totales**. Lo que sí se mantiene significativo en todas: Opus 5.5 razona
menos (`thinking_tokens`) y escribe más (`text_tokens`), efectos que se compensan,
y es ~30% más rápido.

### Medias de la prueba final (n=275)

| Modelo | in (media) | out (media) | thinking (media) | text (media) | tiempo (media) |
|---|---|---|---|---|---|
| `claude-opus-5-5` | 88.9 | 718.8 | 163.9 | 554.8 | 7.8 s |
| `claude-opus-5` | 86.9 | 707.8 | 174.1 | 533.8 | 11.1 s |

### Coste (precios: Opus 5 = $5/M in, $25/M out; Opus 5.5 = $4/M in, $20/M out)

| Prueba | Opus 5.5 | Opus 5 |
|---|---|---|
| Haiku | $2.30 | $2.86 |
| Regex | $2.52 | $3.04 |
| Regex +100 | $4.05 | $4.99 |
| **Total 3 pruebas** | **$8.87** | **$10.88** |
| Media por petición | $0.0142 | $0.0174 |

## Conclusión

- **En tokens de salida totales (`output_tokens`): Opus 5.5 y Opus 5 son equivalentes** (sin diferencia significativa en ninguna de las 3 pruebas).
- **En coste: Opus 5 es ~23% más caro** ($10.88 vs $8.87 en total). Aunque Opus 5.5 genera un poco más de tokens, es un 20% más barato por token y sale ganando.
- **En velocidad: Opus 5.5 es ~30% más rápido** (−3.3 s de media).
- El método de generación de variaciones (LLM vs regex) cambia los números (+3 vs +24 vs +11 tokens), pero no la conclusión: la diferencia real de salida es pequeña frente a su variabilidad.
