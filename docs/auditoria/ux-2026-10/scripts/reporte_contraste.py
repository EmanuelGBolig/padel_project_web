# -*- coding: utf-8 -*-
"""Agrupa los fallos de contraste por CAUSA (color de texto + fondo), no por nodo."""
import io
import json
import sys
from collections import Counter, defaultdict

sys.stdout.reconfigure(encoding='utf-8')

for ruta in sys.argv[1:]:
    d = json.load(io.open(ruta, encoding='utf-8'))
    pags = d['paginas']
    tot = sum(p['totalVisible'] for p in pags.values())
    mal = sum(p['bajo45'] for p in pags.values())
    mal3 = sum(p['bajo3'] for p in pags.values())
    print('=' * 100)
    print(f"TEMA {d['tema']}  |  {len(pags)} pantallas  |  {tot} nodos de texto visibles")
    print(f"  por debajo del umbral WCAG AA: {mal} ({100*mal//max(1,tot)}%)")
    print(f"  por debajo de 3:1 (ilegible incluso como texto grande): {mal3} ({100*mal3//max(1,tot)}%)")

    grupos = Counter()
    pagsde = defaultdict(set)
    ej = {}
    for n, p in pags.items():
        for m in p['malos']:
            if m['oculto']:
                continue
            k = (m['color'], m['fondo'], m['ratio'])
            grupos[k] += 1
            pagsde[k].add(n)
            ej.setdefault(k, [])
            if len(ej[k]) < 3:
                ej[k].append(f'"{m["txt"][:30]}" <{m["tag"]}> {m["cls"][:40]}')
    print(f'\n  {len(grupos)} combinaciones color/fondo distintas que fallan:')
    print(f'  {"n":>4} {"ratio":>6} {"pant":>5}  texto -> fondo')
    for k, v in grupos.most_common(28):
        print(f'  {v:>4} {k[2]:>6} {len(pagsde[k]):>5}  {k[0][:40]:<40} -> {k[1]}')
        for e in ej[k][:2]:
            print(f'                        {e}')

    # bordes de inputs
    bo = [b for p in pags.values() for b in p['bordes']]
    sinb = [b for b in bo if b.get('sinBorde')]
    conb = [b for b in bo if b.get('ratio') is not None]
    flojos = [b for b in conb if b['ratio'] < 3]
    print(f'\n  CONTROLES: {len(bo)} inputs/selects/textarea medidos')
    print(f'    sin borde dibujado: {len(sinb)}')
    print(f'    con borde por debajo de 3:1 contra el fondo (WCAG 1.4.11): {len(flojos)}')
    rs = Counter(round(b['ratio'], 2) for b in conb)
    print('    ratios de borde:', dict(sorted(rs.items())))
    print()
