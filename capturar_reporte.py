"""Captura las pantallas del reporte para clientes.

Usa Playwright contra el servidor de desarrollo. Uso:

    python manage.py runserver 8010     (en otra terminal)
    python capturar_reporte.py
"""
import os
import sys

BASE = 'http://localhost:8010'
SALIDA = os.path.join('docs', 'reporte', 'img')

# (archivo, ruta, ancho, alto, descripcion)
PANTALLAS = [
    ('01-home-mobile.png',        '/',                             390, 844, 'Inicio en celular'),
    ('02-torneos-filtros.png',    '/torneos/abiertos/',            390, 844, 'Filtros de torneos'),
    ('03-ficha-torneo.png',       '/torneos/2/',                   390, 844, 'Ficha del torneo'),
    ('04-gestion-mobile.png',     '/torneos/admin/2/gestionar/',   390, 844, 'Gestion en celular'),
    ('05-dashboard.png',          '/torneos/admin/dashboard/',     390, 844, 'Panel del organizador'),
    ('06-embudo.png',             '/torneos/admin/embudo/',        390, 844, 'Embudo de inscripcion'),
    ('07-home-desktop.png',       '/',                            1280, 800, 'Inicio en escritorio'),
    ('08-llave-desktop.png',      '/torneos/2/',                  1280, 900, 'Cuadro de la fase final'),
]

EMAIL = 't@t.com'
PASSWORD = 'test12345'


def main():
    from playwright.sync_api import sync_playwright

    os.makedirs(SALIDA, exist_ok=True)

    with sync_playwright() as p:
        navegador = p.chromium.launch()
        # La app se usa en tema oscuro: las capturas tienen que mostrar eso.
        ctx = navegador.new_context(viewport={'width': 390, 'height': 844},
                                   color_scheme='dark')
        pagina = ctx.new_page()

        # Login para poder ver las pantallas de gestion
        pagina.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
        try:
            pagina.fill('input[name="username"]', EMAIL)
            pagina.fill('input[name="password"]', PASSWORD)
            pagina.press('input[name="password"]', 'Enter')
            pagina.wait_for_load_state('networkidle')
            print('login OK')
        except Exception as e:
            print('aviso: no se pudo loguear:', e)

        for archivo, ruta, ancho, alto, desc in PANTALLAS:
            try:
                pagina.set_viewport_size({'width': ancho, 'height': alto})
                pagina.goto(BASE + ruta, wait_until='networkidle', timeout=30000)
                pagina.wait_for_timeout(1200)   # que termine el CSS/JS
                destino = os.path.join(SALIDA, archivo)
                pagina.screenshot(path=destino, full_page=False)
                kb = os.path.getsize(destino) // 1024
                print(f'  OK  {archivo:<26} {ancho}x{alto}  {kb} KB   {desc}')
            except Exception as e:
                print(f'  FALLO  {archivo}: {e}')

        navegador.close()
    print('\nCapturas en:', os.path.abspath(SALIDA))


if __name__ == '__main__':
    sys.exit(main())
