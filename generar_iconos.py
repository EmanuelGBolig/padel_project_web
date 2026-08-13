"""Genera los iconos de la PWA a partir de la pala del icono actual.

El problema que resuelve: `favicon_192.png` traía las esquinas redondeadas
"pintadas" y transparentes por fuera. iOS NO soporta transparencia en el
apple-touch-icon: la rellena de blanco y después aplica su propia máscara
redondeada, así que quedaba un halo blanco alrededor del verde.

La regla es: el icono se entrega **cuadrado, opaco y a sangre**. El sistema
operativo se encarga de redondearlo.

Uso:  python generar_iconos.py            # genera las 3 propuestas
      python generar_iconos.py --aplicar 2  # deja la opcion 2 como definitiva
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter

DESTINO = 'theme/static/img'
PRUEBAS = 'docs/reporte/iconos'

VERDE = (16, 185, 129)        # el primary de la app
VERDE_OSCURO = (4, 120, 87)
CARBON = (13, 27, 24)
PELOTA = (205, 221, 94)


def dibujar_pala(tamano):
    """Dibuja la pala a 4x y baja de escala: bordes limpios, sin escalones.

    Es una pala de pádel, no una raqueta de tenis: cabeza redondeada y maciza,
    perforada, con puente triangular y mango corto.
    """
    S = tamano * 4
    capa = Image.new('L', (S, S), 0)
    d = ImageDraw.Draw(capa)

    # Cabeza: ovalo ancho
    cx = S * 0.5
    top, bot = S * 0.06, S * 0.60
    izq, der = S * 0.16, S * 0.84
    d.ellipse([izq, top, der, bot], fill=255)

    # Puente: triangulo que une cabeza y mango
    d.polygon([(S * 0.36, S * 0.55), (S * 0.64, S * 0.55), (S * 0.5, S * 0.78)], fill=255)

    # Mango: una sola pieza que se ensancha hacia el remate, como una pala real.
    a1, a2 = S * 0.062, S * 0.085
    d.polygon([(cx - a1, S * 0.70), (cx + a1, S * 0.70),
               (cx + a2, S * 0.95), (cx - a2, S * 0.95)], fill=255)
    d.ellipse([cx - a2, S * 0.915, cx + a2, S * 0.975], fill=255)

    # Agujeros de la cabeza (lo que hace reconocible una pala)
    r = S * 0.021
    paso = S * 0.072
    ecx, ecy = (izq + der) / 2, (top + bot) / 2
    ra, rb = (der - izq) / 2 - r * 3.4, (bot - top) / 2 - r * 3.4
    y = ecy - rb
    fila = 0
    while y <= ecy + rb:
        x = ecx - ra + (paso / 2 if fila % 2 else 0)
        while x <= ecx + ra:
            if ((x - ecx) / ra) ** 2 + ((y - ecy) / rb) ** 2 <= 1:
                d.ellipse([x - r, y - r, x + r, y + r], fill=0)
            x += paso
        y += paso * 0.87
        fila += 1

    # Hueco del puente
    d.polygon([(S * 0.44, S * 0.585), (S * 0.56, S * 0.585), (S * 0.5, S * 0.715)], fill=0)

    capa = capa.rotate(-32, resample=Image.BICUBIC, expand=False, center=(S / 2, S / 2))
    return capa.resize((tamano, tamano), Image.LANCZOS)


def lienzo(tamano, color_a, color_b=None):
    """Fondo cuadrado, opaco. Con degradado vertical si se pasan dos colores."""
    fondo = Image.new('RGB', (tamano, tamano), color_a)
    if color_b:
        grad = Image.new('RGB', (1, tamano))
        d = ImageDraw.Draw(grad)
        for y in range(tamano):
            t = y / max(1, tamano - 1)
            d.point((0, y), fill=tuple(
                round(color_a[i] + (color_b[i] - color_a[i]) * t) for i in range(3)))
        fondo = grad.resize((tamano, tamano), Image.BICUBIC)
    return fondo


def pegar_pala(fondo, mascara, color, escala, dy=0):
    """Pega la pala centrada, ocupando `escala` del lado."""
    lado = fondo.width
    tam = round(lado * escala)
    pala = mascara.resize((tam, tam), Image.LANCZOS)
    capa = Image.new('RGBA', fondo.size, (0, 0, 0, 0))
    pos = ((lado - tam) // 2, (lado - tam) // 2 + round(lado * dy))
    tinta = Image.new('RGBA', (tam, tam), color + (255,))
    capa.paste(tinta, pos, pala)
    salida = fondo.convert('RGBA')
    salida.alpha_composite(capa)
    return salida.convert('RGB')


def opcion_1(tamano, mascara):
    """Pala grande sobre verde con profundidad. Simple y contundente."""
    fondo = lienzo(tamano, (18, 200, 140), VERDE_OSCURO)
    return pegar_pala(fondo, mascara, (255, 255, 255), 0.74)


def opcion_2(tamano, mascara):
    """Pala + pelota: el amarillo corta contra el verde y se lee de lejos."""
    fondo = lienzo(tamano, (18, 200, 140), VERDE_OSCURO)
    im = pegar_pala(fondo, mascara, (255, 255, 255), 0.70, dy=-0.03)
    d = ImageDraw.Draw(im)
    r = round(tamano * 0.115)
    cx, cy = round(tamano * 0.755), round(tamano * 0.775)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PELOTA)
    return im


def opcion_3(tamano, mascara):
    """Fondo oscuro, pala verde. En una pantalla llena de iconos claros, resalta."""
    fondo = lienzo(tamano, (18, 38, 32), CARBON)
    return pegar_pala(fondo, mascara, (34, 201, 141), 0.76)


OPCIONES = {1: opcion_1, 2: opcion_2, 3: opcion_3}


def con_zona_segura(im, escala=0.72):
    """Version 'maskable' para Android: el arte va en el 72% central.

    Android recorta el icono con formas distintas segun el launcher (circulo,
    squircle, gota). Lo que quede fuera de ese circulo central se pierde.
    """
    lado = im.width
    fondo = im.resize((lado, lado), Image.LANCZOS).filter(ImageFilter.GaussianBlur(0))
    chico = im.resize((round(lado * escala),) * 2, Image.LANCZOS)
    base = Image.new('RGB', (lado, lado), im.getpixel((2, 2)))
    base.paste(chico, ((lado - chico.width) // 2, (lado - chico.height) // 2))
    return base


def generar_pruebas():
    os.makedirs(PRUEBAS, exist_ok=True)
    mascara = dibujar_pala(512)
    for n, fn in OPCIONES.items():
        im = fn(512, mascara)
        ruta = os.path.join(PRUEBAS, f'opcion-{n}.png')
        im.save(ruta)
        print(f'  opcion {n}: {ruta}')
    print(f'\nMiralas y elegi:  python generar_iconos.py --aplicar <n>')


def aplicar(n):
    mascara = dibujar_pala(512)
    fn = OPCIONES[n]

    # apple-touch-icon: 180x180, CUADRADO y OPACO. iOS lo redondea solo.
    fn(180, mascara).save(os.path.join(DESTINO, 'apple-touch-icon.png'))
    # Iconos de la PWA
    fn(192, mascara).save(os.path.join(DESTINO, 'favicon_192.png'))
    fn(512, mascara).save(os.path.join(DESTINO, 'pwa-512.png'))
    con_zona_segura(fn(512, mascara)).save(os.path.join(DESTINO, 'pwa-512-maskable.png'))
    # Favicon del navegador
    fn(64, mascara).save(os.path.join(DESTINO, 'favicon.png'))
    # El .ico se arma pegando cada tamano sobre un fondo opaco: si se deja que
    # PIL genere las variantes solo, mete alfa en algunas y quedan esquinas
    # transparentes justo en el tamano que elige el navegador.
    capas = []
    for lado in (16, 32, 48, 64):
        base = Image.new('RGB', (lado, lado), (18, 200, 140))
        base.paste(fn(lado, mascara), (0, 0))
        capas.append(base)
    capas[-1].save(os.path.join(DESTINO, 'favicon.ico'),
                   format='ICO', sizes=[(c.width, c.height) for c in capas],
                   append_images=capas[:-1])

    print(f'Aplicada la opcion {n}. Archivos generados:')
    for f in ('apple-touch-icon.png', 'favicon_192.png', 'pwa-512.png',
              'pwa-512-maskable.png', 'favicon.png', 'favicon.ico'):
        ruta = os.path.join(DESTINO, f)
        print(f'  {f:<26} {os.path.getsize(ruta) // 1024} KB')


if __name__ == '__main__':
    if '--aplicar' in sys.argv:
        aplicar(int(sys.argv[sys.argv.index('--aplicar') + 1]))
    else:
        generar_pruebas()
