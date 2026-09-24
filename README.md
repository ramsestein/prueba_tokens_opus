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
├── data.jsonl               # 175 preguntas (35 × 5 variaciones)
├── benchmark_claude.py               # lanza el benchmark en paralelo
├── generar_variaciones.py            # genera 5 reformulaciones por pregunta
├── analisis_significancia.py         # test pareado de significancia
├── resultados_tokenizacion.csv  # 350 filas (175 preguntas)
└── resumen_tokenizacion.csv     # agregado por modelo (ampliado)
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

### 1. Benchmark (35 preguntas originales)

```bash
.venv/bin/python benchmark_claude.py
```

Salidas: `resultados_tokenizacion.csv` y `resumen_tokenizacion.csv`.

### 2. Generar variaciones y benchmark ampliado (175 preguntas)

```bash
.venv/bin/python generar_variaciones.py
.venv/bin/python benchmark_claude.py \
    --input data.jsonl \
    --max-questions 1000 \
    --out resultados_tokenizacion.csv \
    --summary-out resumen_tokenizacion_ampliado.csv
```

### 3. Análisis de significancia

```bash
.venv/bin/python analisis_significancia.py --csv resultados_tokenizacion_ampliado.csv
```

## Opciones del benchmark

| Flag | Por defecto | Descripción |
|---|---|---|
| `--models` | `claude-opus-5-5,claude-opus-5` | Modelos a comparar (separados por coma) |
| `--input` | `data_shard01.jsonl` | JSONL de entrada (campo `pregunta`) |
| `--max-questions` | `100` | Máximo de preguntas a procesar |
| `--concurrency` | `8` | Peticiones concurrentes |
| `--thinking` / `--no-thinking` | activado | Modo razonamiento |
| `--effort` | `high` | `low`, `medium`, `high`, `xhigh`, `max` |
| `--max-tokens` | `8192` | Límite de tokens de salida |
| `--out` | `resultados_tokenizacion.csv` | CSV por petición |
| `--summary-out` | `resumen_tokenizacion.csv` | CSV de resumen |

## Notas técnicas

- Los modelos nuevos (Opus 5.x) usan la API de *adaptive thinking*:
  `thinking={"type": "adaptive"}` + `output_config={"effort": ...}`.
  El formato clásico `thinking={"type": "enabled", "budget_tokens": N}` **no** es compatible con ellos.
- El mínimo de `budget_tokens` para el formato "enabled" clásico es **1024**.
- `temperature` no está disponible en esta versión de la API.
- El `input_tokens` difiere en 2 tokens constantes entre modelos (tokenizadores distintos) con la misma entrada.

## Resultados (175 preguntas, 350 peticiones, 0 errores)

| Modelo | in (media) | out (media) | thinking (media) | text (media) | tiempo (media) | out total |
|---|---|---|---|---|---|---|
| `claude-opus-5-5` | 88.8 | 638.6 | 153.3 | 485.2 | 7.12 s | 111 750 |
| `claude-opus-5` | 86.8 | 635.5 | 175.6 | 459.9 | 10.06 s | 111 211 |

### Significancia (test pareado, n=175)

| Métrica | Dif. media (5.5 − 5) | Wilcoxon p | Cohen's d | Veredicto |
|---|---|---|---|---|
| `output_tokens` | +3.1 | 0.61 | +0.02 | No significativo |
| `thinking_tokens` | −22.3 | 1.0e−6 | −0.19 | Significativo |
| `text_tokens` | +25.4 | 0.0025 | +0.17 | Significativo |
| `time_s` | −2.9 s | 8.2e−28 | −1.02 | Significativo |

## Conclusión

- **En coste de salida (`output_tokens`): no hay diferencia estadísticamente significativa** entre Opus 5.5 y Opus 5 (≈ +3 tokens, IC 95% cruza el cero).
- Opus 5.5 razona menos (thinking −22) pero escribe más (text +25); ambos efectos se compensan en el total.
- La única diferencia operativa clara es la **velocidad**: Opus 5.5 es ~30% más rápido.
- Ojo: con solo 35 preguntas la diferencia de salida parecía significativa (+64 tokens, p≈0.005); al ampliar a 175 muestras desapareció. Era ruido muestral.
