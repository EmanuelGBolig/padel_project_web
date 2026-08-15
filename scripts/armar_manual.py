"""Arma el manual de usuario incrustando las capturas como WebP.

El HTML fuente vive en docs/manual/plantilla.html con marcas
{{img:jugador/j01-home}} (ruta relativa a docs/manual/img, sin extensión).
Este script las reemplaza por data URIs para que el manual sea UN archivo que
se puede mandar por WhatsApp o abrir sin internet.

Uso:  python scripts/armar_manual.py
"""
import base64
import io
import os
import re

from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(RAIZ, 'docs', 'manual', 'img')
PLANTILLA = os.path.join(RAIZ, 'docs', 'manual', 'plantilla.html')
SALIDA = os.path.join(RAIZ, 'docs', 'manual', 'manual-usuario.html')

# Ancho al que se reescala cada captura según su origen.
ANCHO_MOVIL = 440       # capturas de jugador (390 css px @2x)
ANCHO_ESCRITORIO = 1080  # capturas de organizador/admin (1280 css px @1.5x)

# Una captura de página completa puede medir 8000px de alto (listados largos).
# En el manual eso es una tira inmanejable: se recorta el pie y se indica con
# un degradé. Las pantallas donde el final importa van en SIN_RECORTE.
MAX_ALTO_RELATIVO = {'movil': 3.4, 'escritorio': 2.2}
SIN_RECORTE = {
    'jugador/j06-ficha',          # la ficha entera es el recorrido del jugador
    'jugador/j14-torneo-en-juego',
    'organizador/o05-gestion-en-juego',
}


def a_data_uri(nombre):
    ruta = os.path.join(IMG, *nombre.split('/')) + '.png'
    im = Image.open(ruta)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        fondo = Image.new('RGB', im.size, (255, 255, 255))
        fondo.paste(im, (0, 0), im)
        im = fondo
    else:
        im = im.convert('RGB')

    tipo = 'movil' if nombre.startswith('jugador/') else 'escritorio'
    ancho = ANCHO_MOVIL if tipo == 'movil' else ANCHO_ESCRITORIO

    recortada = False
    if nombre not in SIN_RECORTE:
        max_alto = int(im.width * MAX_ALTO_RELATIVO[tipo])
        if im.height > max_alto:
            im = im.crop((0, 0, im.width, max_alto))
            recortada = True

    if im.width > ancho:
        im = im.resize((ancho, round(im.height * ancho / im.width)), Image.LANCZOS)

    buf = io.BytesIO()
    im.save(buf, format='WEBP', quality=82, method=6)
    b64 = base64.b64encode(buf.getvalue()).decode()
    print(f'  {nombre:<34} {im.width}x{im.height}{" (recortada)" if recortada else "":<12} {len(buf.getvalue())//1024:>4} KB')
    return f'data:image/webp;base64,{b64}'


def main():
    html = open(PLANTILLA, encoding='utf-8').read()
    usadas = re.findall(r'\{\{img:([\w/.-]+)\}\}', html)
    print(f'{len(dict.fromkeys(usadas))} imágenes:')
    for nombre in dict.fromkeys(usadas):
        html = html.replace('{{img:' + nombre + '}}', a_data_uri(nombre))
    sobrantes = re.findall(r'\{\{img:[\w/.-]+\}\}', html)
    assert not sobrantes, f'marcas sin resolver: {sobrantes}'
    open(SALIDA, 'w', encoding='utf-8').write(html)
    print(f'\n{SALIDA}\n{os.path.getsize(SALIDA)//1024} KB')


if __name__ == '__main__':
    main()
