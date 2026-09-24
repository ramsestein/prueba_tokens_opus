#!/usr/bin/env python3
"""Genera 5 variaciones de cada pregunta clínica usando SOLO transformaciones
con expresiones regulares (sin LLM).

Lee data_original.jsonl (las 35 preguntas originales) y escribe data_regex.jsonl
con un registro por variante: {"orig_id", "variante", "pregunta"}.

Las variantes conservan el significado clínico (números, fechas, fármacos y
términos médicos no se tocan) y solo varían la redacción mediante prefijos y
sustituciones de sinónimos aplicadas con re.sub.
"""

import json
import re

INPUT = "data_original.jsonl"
OUTPUT = "data_regex.jsonl"

# Reglas de sinónimos: (patrón regex con \b, reemplazo). Se aplican con re.IGNORECASE.
RULES = [
    (r"\bcu[áa]ntos\b", "qué número de"),
    (r"\bcu[áa]ntas\b", "qué número de"),
    (r"\bhay\b", "existen"),
    (r"\btenemos\b", "hay"),
    (r"\bpctes\b", "pacientes"),
    (r"\bregistradas\b", "documentadas"),
]


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


def core(q):
    """Quita ¿, ? finales y deja la primera letra en minúscula."""
    c = q.strip()
    c = re.sub(r"^¿", "", c)
    c = re.sub(r"\?+\s*$", "", c)
    c = c.strip()
    if c:
        c = c[0].lower() + c[1:]
    return c


def apply_rules(text, rule_idxs):
    out = text
    for i in rule_idxs:
        pat, rep = RULES[i]
        out = re.sub(pat, rep, out, flags=re.IGNORECASE)
    return out


def variants(q):
    c = core(q)
    return [
        f"¿Me puedes decir {c}?",                     # solo prefijo, sin cambios
        f"Dime {apply_rules(c, [4])}",                # pctes -> pacientes
        f"Necesito saber {apply_rules(c, [2, 3])}",   # hay -> existen, tenemos -> hay
        f"Quiero saber {apply_rules(c, [5])}",        # registradas -> documentadas
        f"¿Sabrías decirme {apply_rules(c, [0, 1])}?",  # cuántos/cuántas -> qué número de
    ]


def main():
    qs = load_questions(INPUT)
    total = 0
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for q in qs:
            for v_idx, v in enumerate(variants(q["pregunta"]), 1):
                f.write(
                    json.dumps(
                        {"orig_id": q["id"], "variante": v_idx, "pregunta": v},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                total += 1
    print(f"Preguntas originales: {len(qs)} | variantes por pregunta: 5")
    print(f"Variantes regex escritas: {total} -> {OUTPUT}")


if __name__ == "__main__":
    main()
