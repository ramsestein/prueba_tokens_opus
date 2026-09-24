#!/usr/bin/env python3
"""Extiende data_regex.jsonl con 100 variantes regex más.

Fuentes de las 20 preguntas originales nuevas (10 + 10):
  - 10 frases de un benchmark clínico español (text-to-SQL).
  - 10 frases generadas directamente.

Cada una se expande a 5 variantes con las mismas reglas regex de
generar_variaciones_regex.py. Resultado: 175 + 100 = 275 preguntas.
"""

import json

from generar_variaciones_regex import variants

BENCH_PATH = "/home/ramses/Proyectos/benchmark-text-to-sql/dataset/questions/data_shard01.jsonl"

# Índices (1-based) del benchmark español a incluir.
BENCH_INDICES = [1, 5, 7, 9, 10, 11, 13, 15, 19, 27]

# 10 preguntas clínicas generadas directamente (mismo estilo text-to-SQL).
MIS_PREGUNTAS = [
    "cuantos pacientes distintos tenemos con un diagnóstico de diabetes registrado?",
    "¿cuántas visitas a urgencias hubo en el último trimestre de 2024?",
    "dame el número de ingresos hospitalarios por mes durante 2025",
    "¿cuántas pruebas de laboratorio de hemoglobina se han pedido en el último año?",
    "cuantos pacientes tienen alergias medicamentosas registradas?",
    "¿cuál es el número de intervenciones quirúrgicas por servicio desde enero de 2025?",
    "dime cuántas hospitalizaciones a domicilio con perfusiones de dosis alta hay activas",
    "¿cuántos episodios tienen al menos una prescripción de anticoagulantes?",
    "cuantas vacunas de la gripe se han administrado en la campaña 2024-2025?",
    "¿qué número de pacientes tienen una tensión arterial sistólica mayor de 140 en sus últimas constantes?",
]


def load_bench_picks():
    qs = []
    with open(BENCH_PATH, encoding="utf-8") as f:
        lines = [json.loads(l) for l in f if l.strip()]
    for idx in BENCH_INDICES:
        qs.append(lines[idx - 1].get("pregunta"))
    return qs


def main():
    new_originals = load_bench_picks() + MIS_PREGUNTAS
    print(f"Nuevas preguntas originales: {len(new_originals)} "
          f"({len(BENCH_INDICES)} benchmark + {len(MIS_PREGUNTAS)} propias)")

    with open("data_regex.jsonl", encoding="utf-8") as fin, \
         open("data_regex_extendido.jsonl", "w", encoding="utf-8") as fout:
        # Copiar las 175 existentes.
        base = 0
        for line in fin:
            fout.write(line)
            base += 1

        # Añadir las nuevas (orig_id 36 en adelante).
        added = 0
        for i, q in enumerate(new_originals, start=36):
            for v_idx, v in enumerate(variants(q), 1):
                fout.write(
                    json.dumps(
                        {"orig_id": i, "variante": v_idx, "pregunta": v},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                added += 1

    print(f"Base: {base} | añadidas: {added} | total: {base + added}")
    print("Escrito: data_regex_extendido.jsonl")


if __name__ == "__main__":
    main()
