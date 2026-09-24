#!/usr/bin/env python3
"""Benchmark de tokenización y latencia entre modelos de Claude (Anthropic).

Lee preguntas clínicas de un JSONL, envía la MISMA entrada a varios modelos
y mide por cada petición:

  - input_tokens  : tokens de entrada (valor exacto que devuelve la API)
  - output_tokens : tokens de salida (valor exacto; INCLUYE el razonamiento
                    cuando el modo thinking está activado)
  - thinking_tokens : tokens de razonamiento (exacto: output_tokens_details.
                    thinking_tokens que devuelve la API)
  - text_tokens : tokens de texto visible (exacto: output_tokens - thinking)
  - time_s        : tiempo de respuesta medido con time.perf_counter()

Las peticiones se lanzan en paralelo con un semáforo de concurrencia.

Uso:
    .venv/bin/python benchmark_claude.py \
        --models claude-opus-5-5,claude-opus-5 \
        --max-questions 100 --concurrency 8
"""

import argparse
import asyncio
import csv
import json
import os
import statistics
import sys
import time

from dotenv import load_dotenv
from anthropic import AsyncAnthropic

DEFAULT_MODELS = ["claude-opus-5-5", "claude-opus-5"]

SYSTEM_PROMPT = (
    "Eres un asistente clínico experto. "
    "Responde a la pregunta del usuario de forma directa, clara y concisa. "
    "Responde en español."
)


def load_questions(path: str, max_questions: int):
    questions = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            q = obj.get("pregunta")
            if q:
                questions.append({
                    "id": len(questions) + 1,
                    "pregunta": q,
                    "orig_id": obj.get("orig_id", ""),
                    "variante": obj.get("variante", ""),
                })
            if len(questions) >= max_questions:
                break
    return questions


async def run_one(client, sem, model, q, thinking, effort, max_tokens):
    async with sem:
        start = time.perf_counter()
        try:
            kwargs = dict(
                model=model,
                max_tokens=max_tokens,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": q["pregunta"]}],
            )
            if thinking:
                kwargs["thinking"] = {"type": "adaptive", "display": "summarized"}
                kwargs["output_config"] = {"effort": effort}
            else:
                kwargs["thinking"] = {"type": "disabled"}
                kwargs["temperature"] = 0.0

            resp = await client.messages.create(**kwargs)
            elapsed = time.perf_counter() - start

            thinking_text = ""
            text_out = ""
            for block in resp.content:
                btype = getattr(block, "type", None)
                if btype == "thinking":
                    thinking_text += getattr(block, "thinking", "") or ""
                elif btype == "text":
                    text_out += getattr(block, "text", "") or ""

            u = resp.usage
            output_tokens = u.output_tokens
            # Tokens de razonamiento exactos que reporta la API.
            details = getattr(u, "output_tokens_details", None)
            thinking_tokens = (getattr(details, "thinking_tokens", 0) if details else 0) or 0
            text_tokens = max(0, output_tokens - thinking_tokens)

            return {
                "id": q["id"],
                "orig_id": q.get("orig_id", ""),
                "variante": q.get("variante", ""),
                "pregunta": q["pregunta"],
                "model": model,
                "status": "ok",
                "input_tokens": u.input_tokens,
                "cache_creation_input_tokens": getattr(
                    u, "cache_creation_input_tokens", 0
                )
                or 0,
                "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0)
                or 0,
                "output_tokens": output_tokens,
                "thinking_tokens": thinking_tokens,
                "text_tokens": text_tokens,
                "thinking_chars": len(thinking_text),
                "text_chars": len(text_out),
                "time_s": round(elapsed, 4),
                "stop_reason": resp.stop_reason or "",
                "error": "",
            }
        except Exception as e:  # noqa: BLE001
            elapsed = time.perf_counter() - start
            return {
                "id": q["id"],
                "orig_id": q.get("orig_id", ""),
                "variante": q.get("variante", ""),
                "pregunta": q["pregunta"],
                "model": model,
                "status": "error",
                "input_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
                "output_tokens": 0,
                "thinking_tokens": 0,
                "text_tokens": 0,
                "thinking_chars": 0,
                "text_chars": 0,
                "time_s": round(elapsed, 4),
                "stop_reason": "",
                "error": f"{type(e).__name__}: {e}",
            }


def summarize(rows):
    by_model = {}
    for r in rows:
        by_model.setdefault(r["model"], []).append(r)

    summary = []
    for model, items in by_model.items():
        ok = [r for r in items if r["status"] == "ok"]
        err = [r for r in items if r["status"] != "ok"]
        if ok:
            summary.append(
                {
                    "model": model,
                    "n_total": len(items),
                    "n_ok": len(ok),
                    "n_error": len(err),
                    "input_tokens_mean": round(statistics.mean(r["input_tokens"] for r in ok), 2),
                    "input_tokens_median": statistics.median(r["input_tokens"] for r in ok),
                    "output_tokens_mean": round(statistics.mean(r["output_tokens"] for r in ok), 2),
                    "output_tokens_median": statistics.median(r["output_tokens"] for r in ok),
                    "thinking_tokens_mean": round(statistics.mean(r["thinking_tokens"] for r in ok), 2),
                    "thinking_tokens_median": statistics.median(r["thinking_tokens"] for r in ok),
                    "text_tokens_mean": round(statistics.mean(r["text_tokens"] for r in ok), 2),
                    "time_s_mean": round(statistics.mean(r["time_s"] for r in ok), 3),
                    "time_s_median": round(statistics.median(r["time_s"] for r in ok), 3),
                    "time_s_max": round(max(r["time_s"] for r in ok), 3),
                    "total_output_tokens": sum(r["output_tokens"] for r in ok),
                }
            )
        else:
            summary.append(
                {
                    "model": model,
                    "n_total": len(items),
                    "n_ok": 0,
                    "n_error": len(err),
                    "input_tokens_mean": None,
                    "input_tokens_median": None,
                    "output_tokens_mean": None,
                    "output_tokens_median": None,
                    "thinking_tokens_mean": None,
                    "thinking_tokens_median": None,
                    "text_tokens_mean": None,
                    "time_s_mean": None,
                    "time_s_median": None,
                    "time_s_max": None,
                    "total_output_tokens": 0,
                }
            )
    return summary


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(DEFAULT_MODELS))
    ap.add_argument("--input", default="data_shard01.jsonl")
    ap.add_argument("--max-questions", type=int, default=100)
    ap.add_argument("--concurrency", type=int, default=8)
    ap.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument(
        "--effort",
        default="high",
        choices=["low", "medium", "high", "xhigh", "max"],
    )
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--out", default="resultados_tokenizacion.csv")
    ap.add_argument("--summary-out", default="resumen_tokenizacion.csv")
    args = ap.parse_args()

    load_dotenv()
    api_key = os.getenv("ANTROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("No se encontró ANTHROPIC_API_KEY en el .env", file=sys.stderr)
        sys.exit(1)

    models = [m.strip() for m in args.models.split(",") if m.strip()]

    questions = load_questions(args.input, args.max_questions)
    print(f"Preguntas cargadas: {len(questions)}")
    print(f"Modelos: {models}")
    print(
        f"Thinking: {args.thinking}"
        + (f" (effort={args.effort})" if args.thinking else "")
        + f" | max_tokens={args.max_tokens} | concurrencia={args.concurrency}"
    )

    client = AsyncAnthropic(api_key=api_key, max_retries=5)
    sem = asyncio.Semaphore(args.concurrency)

    total_start = time.perf_counter()
    tasks = [
        run_one(
            client, sem, model, q,
            args.thinking, args.effort, args.max_tokens,
        )
        for model in models
        for q in questions
    ]
    rows = await asyncio.gather(*tasks)
    total_elapsed = time.perf_counter() - total_start

    # Guardar CSV por petición
    fieldnames = [
        "id", "orig_id", "variante", "pregunta", "model", "status",
        "input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens",
        "output_tokens", "thinking_tokens", "text_tokens",
        "thinking_chars", "text_chars", "time_s", "stop_reason", "error",
    ]
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    # Resumen por modelo
    summary = summarize(rows)
    sfieldnames = list(summary[0].keys()) if summary else []
    with open(args.summary_out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=sfieldnames)
        w.writeheader()
        w.writerows(summary)

    # Imprimir resumen
    print("\n" + "=" * 100)
    print(f"TOTAL peticiones: {len(rows)} | Tiempo total del run: {total_elapsed:.2f}s")
    print("=" * 100)
    header = (
        f"{'modelo':<18} {'n_ok':>5} {'in_med':>8} {'out_med':>8} "
        f"{'think_med':>10} {'vis_med':>8} {'t_med(s)':>9} {'t_max(s)':>9} "
        f"{'out_total':>10}"
    )
    print(header)
    print("-" * 100)
    for s in summary:
        def f(v, nd=1):
            return " " * (nd + 4) if v is None else f"{v:>{nd + 4}.1f}"

        print(
            f"{s['model']:<18} {s['n_ok']:>5} "
            f"{f(s['input_tokens_mean'], 1)} "
            f"{f(s['output_tokens_mean'], 1)} "
            f"{f(s['thinking_tokens_mean'], 3)} "
            f"{f(s['text_tokens_mean'], 1)} "
            f"{f(s['time_s_mean'], 2)} "
            f"{f(s['time_s_max'], 2)} "
            f"{s['total_output_tokens']:>10}"
        )
    print("-" * 100)
    print("in_med   = media de input_tokens (exacto)")
    print("out_med  = media de output_tokens (exacto, INCLUYE razonamiento)")
    print("think_med= media de thinking_tokens (exacto, razonamiento)")
    print("vis_med  = media de text_tokens (out - thinking, exacto)")
    print("t_med/t_max = tiempo de respuesta por petición (segundos)")
    print(f"\nCSV por petición: {args.out}")
    print(f"CSV resumen:      {args.summary_out}")


if __name__ == "__main__":
    asyncio.run(main())
