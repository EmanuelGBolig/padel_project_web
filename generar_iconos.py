"""Genera los iconos de la PWA conservando el diseño original.

El problema que resuelve: el icono venía con las esquinas redondeadas "pintadas"
y transparentes por fuera. iOS NO soporta transparencia en el apple-touch-icon:
rellena de blanco lo transparente y recién después aplica su propia máscara
redondeada, así que en la pantalla de inicio quedaba un halo blanco alrededor
del verde.

La solución NO es cambiar el dibujo: es entregarlo **cuadrado, opaco y a
sangre**. Las esquinas se rellenan con el mismo verde del icono, y el redondeo
lo hace el sistema operativo.

Uso:  python generar_iconos.py
"""
import os

from PIL import Image

ORIGEN = 'docs/reporte/iconos/original/favicon.png'   # el original, en alta
DESTINO = 'theme/static/img'
VERDE = (20, 177, 124)     # el verde del icono original


def base_cuadrada(lado):
    """Devuelve el icono original como un cuadrado opaco de `lado` px.

    Recorta la pastilla verde, la lleva a un cuadrado y rellena las esquinas
    redondeadas con el mismo verde. El dibujo no se toca: sólo deja de haber
    transparencia.
    """
    im = Image.open(ORIGEN).convert('RGBA')

    # Recortar al contenido (saca el margen transparente que traía el archivo).
    caja = im.getbbox()
    if caja:
        im = im.crop(caja)

    # Llevarlo a cuadrado sin deformar: se completa con el verde.
    n = max(im.size)
    cuadrado = Image.new('RGBA', (n, n), VERDE + (255,))
    cuadrado.alpha_composite(im, ((n - im.width) // 2, (n - im.height) // 2))

    # Fondo opaco: las esquinas redondeadas del dibujo quedan del mismo verde,
    # así que la pastilla pasa a ocupar todo el cuadro y no se ve ningún borde.
    fondo = Image.new('RGB', (n, n), VERDE)
    fondo.paste(cuadrado.convert('RGB'), (0, 0), cuadrado)

    return fondo.resize((lado, lado), Image.LANCZOS)


def con_zona_segura(lado, escala=0.78):
    """Versión 'maskable' para Android: el dibujo va en el centro.

    Android recorta el icono con formas distintas según el launcher (círculo,
    squircle, gota). Lo que quede fuera de ese círculo central se pierde, así que
    el dibujo se achica y el resto es verde liso.
    """
    base = base_cuadrada(lado)
    chico = base.resize((round(lado * escala),) * 2, Image.LANCZOS)
    salida = Image.new('RGB', (lado, lado), VERDE)
    salida.paste(chico, ((lado - chico.width) // 2, (lado - chico.height) // 2))
    return salida


def main():
    # apple-touch-icon: 180x180, cuadrado y opaco. iOS lo redondea solo.
    base_cuadrada(180).save(os.path.join(DESTINO, 'apple-touch-icon.png'))
    base_cuadrada(192).save(os.path.join(DESTINO, 'favicon_192.png'))
    base_cuadrada(512).save(os.path.join(DESTINO, 'pwa-512.png'))
    con_zona_segura(512).save(os.path.join(DESTINO, 'pwa-512-maskable.png'))
    base_cuadrada(64).save(os.path.join(DESTINO, 'favicon.png'))

    # El .ico se arma pegando cada tamaño sobre un fondo opaco: si se deja que
    # PIL genere las variantes solo, mete alfa en algunas y quedan esquinas
    # transparentes justo en el tamaño que elige el navegador.
    capas = []
    for lado in (16, 32, 48, 64):
        fondo = Image.new('RGB', (lado, lado), VERDE)
        fondo.paste(base_cuadrada(lado), (0, 0))
        capas.append(fondo)
    capas[-1].save(os.path.join(DESTINO, 'favicon.ico'), format='ICO',
                   sizes=[(c.width, c.height) for c in capas],
                   append_images=capas[:-1])

    print('Iconos generados (diseño original, cuadrado y opaco):')
    for f in ('apple-touch-icon.png', 'favicon_192.png', 'pwa-512.png',
              'pwa-512-maskable.png', 'favicon.png', 'favicon.ico'):
        ruta = os.path.join(DESTINO, f)
        print(f'  {f:<26} {os.path.getsize(ruta) // 1024} KB')


if __name__ == '__main__':
    main()
