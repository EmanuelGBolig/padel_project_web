"""Arma el informe para clientes incrustando las capturas como WebP.

El HTML fuente vive en docs/reporte/plantilla.html con marcas {{img:nombre}}.
Este script las reemplaza por data URIs para que el archivo sea uno solo y se
pueda mandar por WhatsApp o abrir sin internet.
"""
import io
import os
import re
import base64

from PIL import Image

RAIZ = r'C:\Users\egome\Documents\ClaudeCode\padel_project_web'
IMG = os.path.join(RAIZ, 'docs', 'reporte', 'img')
PLANTILLA = os.path.join(RAIZ, 'docs', 'reporte', 'plantilla.html')
SALIDA = os.path.join(RAIZ, 'docs', 'reporte', 'reporte-clientes.html')

# Ancho al que se reescala cada captura. Las de celular no necesitan más de
# 460px para verse nítidas en pantalla; el PDF y las anchas van más grandes.
ANCHOS = {
    'h2-programacion-pdf': 900,
    'h1-programacion': 460,
    '08-llave-desktop': 1100,
    '07-home-desktop': 1100,
    'i1-invitacion': 620,
    'f1b-cta-arriba': 560,
}
ANCHO_POR_DEFECTO = 460


def a_data_uri(nombre):
    ruta = os.path.join(IMG, f'{nombre}.png')
    im = Image.open(ruta)
    if im.mode in ('RGBA', 'LA', 'P'):
        # `.convert('RGB')` a secas compone lo transparente sobre NEGRO: una
        # captura con alfa terminaba con marco negro. Se compone sobre blanco.
        im = im.convert('RGBA')
        fondo = Image.new('RGB', im.size, (255, 255, 255))
        fondo.paste(im, (0, 0), im)
        im = fondo
    else:
        im = im.convert('RGB')
    ancho = ANCHOS.get(nombre, ANCHO_POR_DEFECTO)
    if im.width > ancho:
        alto = round(im.height * ancho / im.width)
        im = im.resize((ancho, alto), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format='WEBP', quality=82, method=6)
    b64 = base64.b64encode(buf.getvalue()).decode()
    print(f'  {nombre:<26} {im.width}x{im.height}  {len(buf.getvalue())//1024:>4} KB')
    return f'data:image/webp;base64,{b64}'


def main():
    html = open(PLANTILLA, encoding='utf-8').read()
    usadas = re.findall(r'\{\{img:([\w.-]+)\}\}', html)
    print(f'{len(set(usadas))} imágenes:')
    for nombre in dict.fromkeys(usadas):
        html = html.replace('{{img:' + nombre + '}}', a_data_uri(nombre))
    open(SALIDA, 'w', encoding='utf-8').write(html)
    print(f'\n{SALIDA}\n{os.path.getsize(SALIDA)//1024} KB')


if __name__ == '__main__':
    main()
