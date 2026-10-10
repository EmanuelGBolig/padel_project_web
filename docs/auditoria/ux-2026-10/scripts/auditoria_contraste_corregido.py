# -*- coding: utf-8 -*-
"""Reemplazo de auditoria_modo_claro.py: contraste WCAG real, en los DOS temas.

Corre audit_contraste.py para `corporate` y `business` y despues imprime el
resumen agrupado por causa (combinacion color/fondo), que es lo accionable:
no interesa cuantos nodos fallan sino cuantas REGLAS distintas los producen.

Por que el original no veia nada (0 de 27 pantallas):

  a) Usaba una RESTA de luminancias gamma con umbral 45/255. Eso no es
     contraste: dos grises medios separados 45 puntos dan un ratio de 1.76:1
     y pasan el filtro. El texto secundario de la app vive justo ahi.
  b) Ignoraba el ALPHA del color del texto. `text-base-content/50` es un color
     con alpha 0.5; el script leia su luminancia a alpha 1. El pie de pagina
     entero (34 pantallas) pasaba el filtro midiendo 3.18:1 real.
  c) No componia los fondos semitransparentes (`bg-base-200/50`) sobre su
     ancestro.
  d) Solo miraba el tema claro, a 1280px (escritorio), cuando la app se usa
     desde el celular.

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python auditoria_contraste_corregido.py
"""
import os
import subprocess
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable


def main():
    for tema in ('corporate', 'business'):
        salida = os.path.join(AQUI, f'contraste_{tema}.json')
        subprocess.check_call([PY, os.path.join(AQUI, 'audit_contraste.py'), tema, salida])
    subprocess.check_call(
        [PY, os.path.join(AQUI, 'reporte_contraste.py'),
         os.path.join(AQUI, 'contraste_corporate.json'),
         os.path.join(AQUI, 'contraste_business.json')])


if __name__ == '__main__':
    main()
