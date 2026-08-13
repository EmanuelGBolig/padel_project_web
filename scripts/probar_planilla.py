"""Genera el PDF de la planilla igual que lo hace el navegador y lo revisa."""
import os
import sys

import fitz
from playwright.sync_api import sync_playwright

TORNEO = int(sys.argv[1]) if len(sys.argv) > 1 else 3
BASE = 'http://localhost:8010'
SALIDA = r'C:\Users\egome\AppData\Local\Temp\claude\C--Users-egome-Documents-ClaudeCode\3845ff33-9c25-48c6-9dd4-1adc33178a09\scratchpad'

with sync_playwright() as p:
    nav = p.chromium.launch()
    pag = nav.new_page()
    pag.goto(f'{BASE}/torneos/{TORNEO}/programacion/', wait_until='networkidle')
    pdf = os.path.join(SALIDA, 'planilla_nueva.pdf')
    pag.pdf(path=pdf, format='A4', print_background=True)
    nav.close()

d = fitz.open(pdf)
print(f'paginas: {d.page_count}')
for i in range(d.page_count):
    d[i].get_pixmap(dpi=100).save(os.path.join(SALIDA, f'nueva_pag{i+1}.png'))
print('--- texto pagina 1 ---')
print(d[0].get_text()[:1200])
