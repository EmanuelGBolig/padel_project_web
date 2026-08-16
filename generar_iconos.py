"""Genera los iconos de la PWA conservando el diseño original.

El problema que resuelve: el icono venía con las esquinas redondeadas "pintadas"
y transparentes por fuera. iOS NO soporta transparencia en el apple-touch-icon:
rellena de blanco lo transparente y recién después aplica su propia máscara
redondeada, así que en la pantalla de inicio quedaba un halo blanco alrededor
del verde.

La solución depende de DÓNDE se muestra el icono:

- Donde el sistema aplica su propia máscara (apple-touch-icon de iOS, maskable
  de Android) se entrega **cuadrado, opaco y a sangre**: el redondeo lo hace él.
- Donde el icono se muestra tal cual (la pestaña del navegador, el manifest) va
  **con las esquinas redondeadas de la marca** y transparencia afuera, que es
  como se ve el logo.

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


def con_esquinas_redondeadas(lado):
    """El icono con sus esquinas redondeadas de siempre y transparencia afuera.

    Es la forma de la marca tal cual: en vez de dibujar un rectangulo redondeado
    a ojo, se conserva el canal alfa del archivo original.

    Va SOLO donde la transparencia se respeta: la pestana del navegador y el
    icono del manifest. En el `apple-touch-icon` NO, porque iOS rellena de
    blanco lo transparente antes de aplicar su propia mascara y vuelve el halo.
    """
    im = Image.open(ORIGEN).convert('RGBA')

    caja = im.getbbox()
    if caja:
        im = im.crop(caja)

    # La pastilla no es perfectamente cuadrada (444x427): se centra en un lienzo
    # cuadrado transparente para no deformarla.
    n = max(im.size)
    cuadrado = Image.new('RGBA', (n, n), (0, 0, 0, 0))
    cuadrado.alpha_composite(im, ((n - im.width) // 2, (n - im.height) // 2))
    return cuadrado.resize((lado, lado), Image.LANCZOS)


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
    # --- Donde el sistema pone SU propia mascara: cuadrado y opaco ---------
    # iOS rellena de blanco lo transparente y despues redondea. Si le mandamos
    # el icono ya redondeado, queda un halo blanco alrededor del verde.
    base_cuadrada(180).save(os.path.join(DESTINO, 'apple-touch-icon.png'))
    # Android recorta el maskable con la forma del launcher (circulo, gota...).
    con_zona_segura(512).save(os.path.join(DESTINO, 'pwa-512-maskable.png'))

    # --- Donde el icono se muestra tal cual: con las esquinas de la marca ---
    # La pestana del navegador y el manifest SI respetan la transparencia, asi
    # que aca va la pastilla redondeada y no un cuadrado verde.
    con_esquinas_redondeadas(192).save(os.path.join(DESTINO, 'favicon_192.png'))
    con_esquinas_redondeadas(512).save(os.path.join(DESTINO, 'pwa-512.png'))
    con_esquinas_redondeadas(64).save(os.path.join(DESTINO, 'favicon.png'))

    # El .ico lleva varios tamanos adentro y el navegador elige uno. Se generan
    # a mano, uno por uno: dejando que PIL derive las variantes solas, el
    # remuestreo ensucia el borde justo en 16x16, que es el que se ve.
    capas = [con_esquinas_redondeadas(lado) for lado in (16, 32, 48, 64)]
    capas[-1].save(os.path.join(DESTINO, 'favicon.ico'), format='ICO',
                   sizes=[(c.width, c.height) for c in capas],
                   append_images=capas[:-1])

    print('Iconos generados:')
    redondeados = {'favicon_192.png', 'pwa-512.png', 'favicon.png', 'favicon.ico'}
    for f in ('apple-touch-icon.png', 'pwa-512-maskable.png',
              'favicon_192.png', 'pwa-512.png', 'favicon.png', 'favicon.ico'):
        ruta = os.path.join(DESTINO, f)
        forma = 'redondeado' if f in redondeados else 'cuadrado (lo enmascara el SO)'
        print(f'  {f:<26} {os.path.getsize(ruta) // 1024:>3} KB   {forma}')


if __name__ == '__main__':
    main()
