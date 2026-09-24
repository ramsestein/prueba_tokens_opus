#!/usr/bin/env python3
"""Test de significancia estadística (pareado) entre dos modelos.

Usa los datos de resultados_tokenizacion.csv. Cada pregunta (id) fue enviada a
ambos modelos, por lo que las muestras están emparejadas: se analizan las
diferencias por pregunta con test de t pareado y Wilcoxon signed-rank.
"""

import argparse
import csv
from collections import defaultdict

import numpy as np
from scipy import stats

CSV_DEFAULT = "resultados_tokenizacion.csv"
MODEL_A = "claude-opus-5-5"
MODEL_B = "claude-opus-5"

METRICAS = ["output_tokens", "thinking_tokens", "text_tokens", "input_tokens", "time_s"]


def load_paired(csv_path):
    by_id = defaultdict(dict)
    with open(csv_path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            by_id[int(r["id"])][r["model"]] = r
    return by_id


def analizar_metrica(a, b, nombre):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    d = a - b  # diferencia A - B

    n = len(d)
    mean_d = float(np.mean(d))
    med_d = float(np.median(d))
    std_d = float(np.std(d, ddof=1)) if n > 1 else 0.0

    # Normalidad de las diferencias
    sh_w, sh_p = stats.shapiro(d) if n >= 3 else (np.nan, np.nan)

    # Test de t pareado
    t_stat, t_p = stats.ttest_rel(a, b)

    # Wilcoxon signed-rank (robusto a no-normalidad)
    try:
        w_stat, w_p = stats.wilcoxon(a, b)
    except ValueError:
        w_stat, w_p = np.nan, np.nan

    # Tamaño del efecto: Cohen's d pareado
    cohen_d = mean_d / std_d if std_d > 0 else 0.0

    # IC 95% de la diferencia media (t pareado)
    if n > 1:
        se = std_d / np.sqrt(n)
        t_crit = stats.t.ppf(0.975, n - 1)
        ci_lo = mean_d - t_crit * se
        ci_hi = mean_d + t_crit * se
    else:
        ci_lo = ci_hi = np.nan

    return {
        "metrica": nombre,
        "n": n,
        "media_A": float(np.mean(a)),
        "media_B": float(np.mean(b)),
        "media_diff": mean_d,
        "mediana_diff": med_d,
        "std_diff": std_d,
        "shapiro_p": sh_p,
        "t_stat": float(t_stat),
        "t_p": float(t_p),
        "wilcoxon_stat": float(w_stat) if not np.isnan(w_stat) else np.nan,
        "wilcoxon_p": float(w_p) if not np.isnan(w_p) else np.nan,
        "cohen_d": cohen_d,
        "ci95_lo": ci_lo,
        "ci95_hi": ci_hi,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=CSV_DEFAULT)
    args = ap.parse_args()

    by_id = load_paired(args.csv)
    ids = sorted(by_id.keys())

    print(f"CSV: {args.csv}")
    print(f"Modelo A: {MODEL_A}")
    print(f"Modelo B: {MODEL_B}")
    print(f"Preguntas emparejadas: {len(ids)}")

    resultados = []
    for m in METRICAS:
        a = [by_id[i][MODEL_A][m] for i in ids]
        b = [by_id[i][MODEL_B][m] for i in ids]
        resultados.append(analizar_metrica(a, b, m))

    print("\n" + "=" * 110)
    for r in resultados:
        print(f"\n--- {r['metrica']} (n={r['n']}) ---")
        print(f"  media {MODEL_A} = {r['media_A']:.2f} | media {MODEL_B} = {r['media_B']:.2f}")
        print(
            f"  diferencia media (A-B) = {r['media_diff']:+.2f}  "
            f"[IC95%: {r['ci95_lo']:+.2f}, {r['ci95_hi']:+.2f}]"
        )
        print(f"  mediana de las diferencias = {r['mediana_diff']:+.2f}")
        print(f"  Shapiro-Wilk (normalidad dif): p={r['shapiro_p']:.4f}")
        print(
            f"  t pareado: t={r['t_stat']:.3f}, p={r['t_p']:.4g}  "
            f"({'SIGNIFICATIVO' if r['t_p'] < 0.05 else 'no significativo'})"
        )
        print(
            f"  Wilcoxon: W={r['wilcoxon_stat']:.1f}, p={r['wilcoxon_p']:.4g}  "
            f"({'SIGNIFICATIVO' if r['wilcoxon_p'] < 0.05 else 'no significativo'})"
        )
        print(f"  Cohen's d (pareado) = {r['cohen_d']:+.3f}")

    # Resumen compacto
    print("\n" + "=" * 110)
    print(f"{'metrica':<16} {'dif_media':>11} {'t_p':>9} {'wilcox_p':>9} {'cohen_d':>9}  veredicto")
    print("-" * 110)
    for r in resultados:
        sig = "SÍ*" if r["wilcoxon_p"] < 0.05 else "no"
        print(
            f"{r['metrica']:<16} {r['media_diff']:>+10.2f} "
            f"{r['t_p']:>9.2e} {r['wilcoxon_p']:>9.2e} {r['cohen_d']:>+9.3f}  {sig}"
        )
    print("-" * 110)
    print("* significativo a p < 0.05 (dos colas). Diferencias positivas = A > B.")

    # Análisis agrupado por pregunta original (promedio de sus variantes)
    has_orig = all(
        (by_id[i][MODEL_A].get("orig_id") not in (None, "")) for i in ids
    )
    if has_orig:
        orig_ids = sorted({by_id[i][MODEL_A]["orig_id"] for i in ids})
        a_agg, b_agg = [], []
        for oid in orig_ids:
            vals_a = [
                float(by_id[i][MODEL_A]["output_tokens"])
                for i in ids
                if by_id[i][MODEL_A].get("orig_id") == oid
            ]
            vals_b = [
                float(by_id[i][MODEL_B]["output_tokens"])
                for i in ids
                if by_id[i][MODEL_B].get("orig_id") == oid
            ]
            a_agg.append(float(np.mean(vals_a)))
            b_agg.append(float(np.mean(vals_b)))
        r_agg = analizar_metrica(a_agg, b_agg, "output_tokens (prom. por pregunta)")
        print("\n" + "=" * 110)
        print(f"AGRUPADO por pregunta original (n={len(orig_ids)}): output_tokens")
        print(f"  media {MODEL_A} = {r_agg['media_A']:.2f} | media {MODEL_B} = {r_agg['media_B']:.2f}")
        print(
            f"  diferencia media (A-B) = {r_agg['media_diff']:+.2f}  "
            f"[IC95%: {r_agg['ci95_lo']:+.2f}, {r_agg['ci95_hi']:+.2f}]"
        )
        print(
            f"  Wilcoxon p = {r_agg['wilcoxon_p']:.4g} | t p = {r_agg['t_p']:.4g} "
            f"| Cohen's d = {r_agg['cohen_d']:+.3f}"
        )


if __name__ == "__main__":
    main()
