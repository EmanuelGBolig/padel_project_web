"""Captura el flujo completo de inscripción sin cuenta, con pago.

Recorre los pasos de verdad (no son maquetas): abre la ficha, completa el
formulario, llega a la confirmación y a la pantalla de pago. Cada captura es de
la pantalla ENTERA (full_page), no solo lo que entra en el viewport.

Uso:  python manage.py runserver 8010   (en otra terminal)
      python capturar_flujo.py
"""
import os
import time

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'
SALIDA = os.path.join('docs', 'reporte', 'img')
TORNEO = 3


def main():
    os.makedirs(SALIDA, exist_ok=True)
    sello = str(int(time.time()))[-5:]   # email y telefono unicos en cada corrida

    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': 390, 'height': 844},
                              color_scheme='dark')
        pag = ctx.new_page()

        def foto(nombre, desc):
            pag.wait_for_timeout(900)
            ruta = os.path.join(SALIDA, nombre)
            pag.screenshot(path=ruta, full_page=True)
            kb = os.path.getsize(ruta) // 1024
            print(f'  OK  {nombre:<28} {kb:>4} KB   {desc}')

        # --- 1. La ficha del torneo, como la ve alguien sin cuenta ---
        pag.goto(f'{BASE}/torneos/{TORNEO}/', wait_until='networkidle')
        foto('f1-ficha-torneo.png', 'Paso 1 · Abre el torneo')

        # --- 2. El formulario ---
        pag.goto(f'{BASE}/torneos/{TORNEO}/anotarme-sin-cuenta/', wait_until='networkidle')
        foto('f2-formulario-vacio.png', 'Paso 2 · El formulario')

        # --- 3. El formulario ya completado ---
        pag.fill('input[name=nombre]', 'Emanuel')
        pag.fill('input[name=apellido]', 'Gomez')
        pag.fill('input[name=email]', f'demo{sello}@mail.com')
        pag.fill('input[name=telefono]', f'+54 9 223 5{sello}1')
        pag.fill('input[name=companero_nombre]', 'Leandro')
        pag.fill('input[name=companero_apellido]', 'Buccella')
        pag.fill('input[name=companero_email]', f'socio{sello}@mail.com')
        pag.fill('input[name=companero_telefono]', f'+54 9 223 6{sello}2')
        foto('f3-formulario-lleno.png', 'Paso 2 · Con los datos cargados')

        # --- 4. La confirmación, con el WhatsApp listo ---
        pag.click('button[type=submit]')
        pag.wait_for_load_state('networkidle')
        foto('f4-confirmacion.png', 'Paso 3 · Anotados + WhatsApp listo')

        # --- 5. Cómo pagar ---
        pag.goto(f'{BASE}/torneos/{TORNEO}/', wait_until='networkidle')
        try:
            pag.locator('text=Cómo pagar la inscripción').scroll_into_view_if_needed()
        except Exception:
            pass
        foto('f5-como-pagar.png', 'Paso 4 · Los datos para transferir')

        nav.close()

    print(f'\nCapturas en: {os.path.abspath(SALIDA)}')


if __name__ == '__main__':
    main()
