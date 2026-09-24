#!/usr/bin/env python3
"""Genera 5 variaciones (reformulaciones) de cada pregunta clínica.

Lee data_shard01.jsonl y, para cada pregunta, pide a un modelo de Claude 5
reformulaciones que preserven el significado clínico (mismos números, fechas,
fármacos, términos médicos y filtros). Escribe data_ampliado.jsonl con un
registro por variante: {"orig_id", "variante", "pregunta"}.
"""

import argparse
import asyncio
import json
import os
import re
import sys

from dotenv import load_dotenv
from anthropic import AsyncAnthropic

GEN_MODEL = "claude-haiku-4-5-20251001"
N_VARIANTS = 5

PROMPT = (
    "Reformula la siguiente pregunta clínica en {n} versiones distintas, en español.\n"
    "Requisitos:\n"
    "- Preserva EXACTAMENTE el significado clínico y la intención de la pregunta.\n"
    "- Conserva sin cambios: números, fechas, nombres propios, fármacos, unidades "
    "y cualquier valor o filtro (p. ej. 'desde el 6 de agosto de 2024', 'vancomicina', 'UCI').\n"
    "- Varía la redacción, el orden y los sinónimos, de forma natural, como lo harían "
    "distintos usuarios de un hospital.\n"
    "- Devuelve EXCLUSIVAMENTE un array JSON con {n} strings, sin markdown, sin "
    "explicaciones ni comentarios.\n\n"
    "Pregunta: {pregunta}"
)


def load_questions(path):
    qs = []
    with open(path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            p = obj.get("pregunta")
            if p:
                qs.append({"id": i, "pregunta": p})
    return qs


def extract_array(text):
    if not text:
        return None
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        arr = json.loads(text)
        if isinstance(arr, list):
            return [str(x) for x in arr]
    except Exception:
        pass
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            if isinstance(arr, list):
                return [str(x) for x in arr]
        except Exception:
            pass
    return None


def fallback_variants(q, n):
    p = q["pregunta"]
    return [
        p,
        f"¿Me puedes decir {p}?",
        f"Dime, {p}",
        f"Necesito saber {p}",
        f"¿Sabrías decirme {p}?",
    ][:n]


async def generate(client, sem, q, n, model):
    async with sem:
        try:
            resp = await client.messages.create(
                model=model,
                max_tokens=1200,
                messages=[
                    {"role": "user", "content": PROMPT.format(n=n, pregunta=q["pregunta"])}
                ],
            )
            text = resp.content[0].text if resp.content else ""
            variants = extract_array(text)
            if not variants:
                raise ValueError("no se pudo parsear el array JSON")
            variants = variants[:n]
            while len(variants) < n:
                variants.append(variants[-1])
            return q["id"], variants
        except Exception as e:  # noqa: BLE001
            print(f"  fallo en pregunta {q['id']} ({type(e).__name__}): {e}", file=sys.stderr)
            return q["id"], fallback_variants(q, n)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="data_shard01.jsonl")
    ap.add_argument("--out", default="data_ampliado.jsonl")
    ap.add_argument("--variants", type=int, default=N_VARIANTS)
    ap.add_argument("--model", default=GEN_MODEL)
    ap.add_argument("--concurrency", type=int, default=8)
    args = ap.parse_args()

    load_dotenv()
    api_key = os.getenv("ANTROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("No se encontró ANTHROPIC_API_KEY en el .env", file=sys.stderr)
        sys.exit(1)

    qs = load_questions(args.input)
    print(f"Preguntas originales: {len(qs)} | variantes por pregunta: {args.variants}")
    print(f"Modelo generador: {args.model}")

    client = AsyncAnthropic(api_key=api_key, max_retries=5)
    sem = asyncio.Semaphore(args.concurrency)
    results = dict(await asyncio.gather(*[generate(client, sem, q, args.variants, args.model) for q in qs]))

    total = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for q in qs:
            variants = results[q["id"]]
            for v_idx, v in enumerate(variants, 1):
                f.write(
                    json.dumps(
                        {"orig_id": q["id"], "variante": v_idx, "pregunta": v},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                total += 1

    print(f"Variantes generadas y escritas: {total} -> {args.out}")


if __name__ == "__main__":
    asyncio.run(main())
