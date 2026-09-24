#!/usr/bin/env python3
"""Calcula el coste de cada modelo en las 3 pruebas del benchmark.

Precios (por millón de tokens):
  - claude-opus-5   : $5  input / $25 output
  - claude-opus-5-5 : $4  input / $20 output
El coste usa output_tokens (que ya incluye razonamiento), como factura Anthropic.
"""

import csv
from collections import defaultdict

PRICES = {
    "claude-opus-5": {"in": 5.0, "out": 25.0},
    "claude-opus-5-5": {"in": 4.0, "out": 20.0},
}

TESTS = [
    ("Haiku (n=175)", "resultados_tokenizacion.csv"),
    ("Regex (n=175)", "resultados_tokenizacion_regex.csv"),
    ("Regex +100 (n=275)", "resultados_tokenizacion_regex_extendido.csv"),
]

MODELS = ["claude-opus-5-5", "claude-opus-5"]


def totals_for(csv_path):
    t = {m: {"in": 0, "out": 0, "n": 0} for m in MODELS}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status") != "ok":
                continue
            m = r["model"]
            t[m]["in"] += int(r["input_tokens"])
            t[m]["out"] += int(r["output_tokens"])
            t[m]["n"] += 1
    return t


def cost(m, t):
    p = PRICES[m]
    return t[m]["in"] / 1e6 * p["in"] + t[m]["out"] / 1e6 * p["out"]


def main():
    agg = {m: {"in": 0, "out": 0, "n": 0, "cost": 0.0} for m in MODELS}

    print(f"{'Prueba':<20} {'Modelo':<18} {'in_tok':>10} {'out_tok':>10} {'coste $':>9}")
    print("-" * 70)
    for name, path in TESTS:
        t = totals_for(path)
        for m in MODELS:
            c = cost(m, t)
            agg[m]["in"] += t[m]["in"]
            agg[m]["out"] += t[m]["out"]
            agg[m]["n"] += t[m]["n"]
            agg[m]["cost"] += c
            print(f"{name:<20} {m:<18} {t[m]['in']:>10,} {t[m]['out']:>10,} {c:>9.3f}")
        print("-" * 70)

    print("\nTOTAL 3 pruebas")
    for m in MODELS:
        a = agg[m]
        print(
            f"  {m:<18} in={a['in']:,}  out={a['out']:,}  "
            f"peticiones={a['n']:,}  coste_total=${a['cost']:.3f}"
        )
    print("\nMEDIA por prueba (total / 3)")
    for m in MODELS:
        print(f"  {m:<18} ${agg[m]['cost'] / len(TESTS):.3f}")
    print("\nMEDIA por petición")
    for m in MODELS:
        print(f"  {m:<18} ${agg[m]['cost'] / agg[m]['n']:.6f}")

    # Comparativa
    c55 = agg[MODELS[0]]["cost"]
    c5 = agg[MODELS[1]]["cost"]
    print(f"\nDiferencia: Opus 5 vs Opus 5.5 = ${c5 - c55:+.3f} en total "
          f"({(c5 / c55 - 1) * 100:+.1f}%)")


if __name__ == "__main__":
    main()
