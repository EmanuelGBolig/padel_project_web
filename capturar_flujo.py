"""Captura las pantallas del informe para clientes.

Recorre los pasos de verdad (no son maquetas): abre la ficha, completa el
formulario en sus dos pasos, llega a la confirmación y a la pantalla de pago.
También captura el panel de notificaciones, la planilla de horarios y las cajas
de invitación de pareja.

Cada captura es de la pantalla ENTERA (full_page) salvo las que se marcan como
recorte, que son de una zona puntual para poder mostrar dos por fila.

Antes de correrlo hay que tener datos de vitrina:
    python scripts/datos_demo_informe.py

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python capturar_flujo.py
"""
import os
import time

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'
SALIDA = os.path.join('docs', 'reporte', 'img')
TORNEO = 3                  # el que tiene precio y cupo, para el alta
TORNEO_CON_HORARIOS = 2     # el de 24 parejas, para que la planilla se vea llena
DEMO_EMAIL = 'demo.informe@todopadel.club'
DEMO_CLAVE = 'DemoInforme2026'

# Las capturas de página completa dibujan los elementos pegados (header, barra
# inferior) en la posición del scroll, y salen repetidos en el medio de la foto.
# Se los vuelve estáticos sólo para la captura.
SIN_PEGADOS = """
    header, nav, .navbar, .btm-nav,
    [class*="sticky"], [class*="fixed"] {
        position: static !important;
    }
"""


def main():
    os.makedirs(SALIDA, exist_ok=True)
    sello = str(int(time.time()))[-5:]   # email y telefono unicos en cada corrida

    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': 390, 'height': 844},
                              color_scheme='dark')
        pag = ctx.new_page()

        def foto(nombre, desc, *, completa=True, recorte=None, quieto=True):
            pag.wait_for_timeout(900)
            if quieto:
                pag.add_style_tag(content=SIN_PEGADOS)
                pag.wait_for_timeout(300)
            ruta = os.path.join(SALIDA, nombre)
            if recorte is not None:
                pag.locator(recorte).first.screenshot(path=ruta)
            else:
                pag.screenshot(path=ruta, full_page=completa)
            kb = os.path.getsize(ruta) // 1024
            print(f'  OK  {nombre:<28} {kb:>4} KB   {desc}')

        def entrar():
            pag.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
            pag.fill('input[name=username]', DEMO_EMAIL)
            pag.fill('input[name=password]', DEMO_CLAVE)
            # El botón no lleva type=submit explícito: dentro de un <form> el
            # default de <button> ya es submit.
            pag.click('form button.btn-primary')
            pag.wait_for_load_state('networkidle')

        # ============ FLUJO DE INSCRIPCIÓN SIN CUENTA ============

        # 1. La ficha del torneo, con el botón de anotarse arriba de todo.
        pag.goto(f'{BASE}/torneos/{TORNEO}/', wait_until='networkidle')
        foto('f1-ficha-torneo.png', 'Paso 1 · Abre el torneo')
        # Recorte de la parte de arriba: se usa para mostrarlo al lado de otra.
        foto('f1b-cta-arriba.png', 'Paso 1 · recorte del botón',
             recorte='.hero')

        # 2 y 3. El popup, en sus dos pasos. Se recorta a la ventana del
        # formulario: en el informe van de a dos por fila, y con la barra de
        # navegación, el banner y el pie no se leía nada.
        pag.goto(f'{BASE}/torneos/{TORNEO}/anotarme-sin-cuenta/', wait_until='networkidle')
        foto('f2-paso1-vacio.png', 'Paso 2 · Tus datos (vacío)', recorte='.card')

        pag.fill('input[name=nombre]', 'Emanuel')
        pag.fill('input[name=apellido]', 'Gomez')
        pag.fill('input[name=email]', f'demo{sello}@mail.com')
        pag.fill('input[name=telefono]', f'+54 9 223 5{sello}1')
        foto('f2b-paso1-lleno.png', 'Paso 2 · Tus datos (completo)', recorte='.card')

        pag.click('#alta-siguiente')
        pag.wait_for_timeout(700)
        foto('f3-paso2-vacio.png', 'Paso 3 · Tu compañero/a', recorte='.card')

        pag.fill('input[name=companero_nombre]', 'Leandro')
        pag.fill('input[name=companero_apellido]', 'Buccella')
        pag.fill('input[name=companero_email]', f'socio{sello}@mail.com')
        pag.fill('input[name=companero_telefono]', f'+54 9 223 6{sello}2')
        foto('f3b-paso2-lleno.png', 'Paso 3 · Compañero cargado', recorte='.card')

        # 4. La confirmación, con el WhatsApp listo.
        pag.click('button[type=submit]')
        pag.wait_for_load_state('networkidle')
        foto('f4-confirmacion.png', 'Paso 4 · Anotados + WhatsApp listo')

        # 5. Cómo pagar.
        pag.goto(f'{BASE}/torneos/{TORNEO}/', wait_until='networkidle')
        try:
            pag.locator('text=Cómo pagar la inscripción').scroll_into_view_if_needed()
        except Exception:
            pass
        foto('f5-como-pagar.png', 'Paso 5 · Los datos para transferir')

        # ============ NOTIFICACIONES ============
        entrar()
        # Los banners de "agregá tu foto" y "formá tu pareja" son descartables y
        # acá sólo tapan lo que se quiere mostrar. Se marcan como descartados.
        pag.evaluate("""
            sessionStorage.setItem('dismissed_banner-foto', '1');
            sessionStorage.setItem('dismissed_banner-equipo', '1');
        """)
        pag.goto(f'{BASE}/accounts/notificaciones/', wait_until='networkidle')
        foto('n1-notificaciones.png', 'Panel de notificaciones')

        # ============ INVITACIÓN DE PAREJA ============
        pag.goto(f'{BASE}/accounts/perfil/', wait_until='networkidle')
        try:
            pag.locator('#invitaciones-recibidas').scroll_into_view_if_needed()
            foto('i1-invitacion.png', 'Caja de invitación de pareja',
                 recorte='#invitaciones-recibidas')
        except Exception as e:
            print(f'  -- sin invitaciones a la vista ({e})')

        # ============ PLANILLA DE HORARIOS ============
        # Se usa el torneo con muchos partidos: con dos o tres no se ve el punto.
        pag.goto(f'{BASE}/torneos/{TORNEO_CON_HORARIOS}/programacion/',
                 wait_until='networkidle')
        # Sólo lo que entra en la pantalla: la planilla completa son 4000px de
        # alto y al lado de otra captura en el informe quedaba una tira ilegible.
        pag.evaluate("window.scrollTo(0, 380)")
        foto('h1-programacion.png', 'Horarios en el celular', completa=False,
             quieto=False)

        # El PDF de verdad, generado por el navegador igual que con el botón, y
        # pasado a imagen para poder mostrarlo en el informe.
        ancha = ctx.new_page()
        ancha.set_viewport_size({'width': 1100, 'height': 1400})
        ancha.goto(f'{BASE}/torneos/{TORNEO_CON_HORARIOS}/programacion/',
                   wait_until='networkidle')
        pdf = os.path.join(SALIDA, 'planilla.pdf')
        ancha.pdf(path=pdf, format='A4', print_background=True)
        ancha.close()

        import fitz
        doc = fitz.open(pdf)
        ruta = os.path.join(SALIDA, 'h2-programacion-pdf.png')
        # alpha=False: si no, el margen de la hoja queda transparente y después,
        # al pasarlo a RGB, se compone sobre negro y la planilla sale enmarcada
        # en un borde negro que no existe.
        doc[0].get_pixmap(dpi=110, alpha=False).save(ruta)
        doc.close()
        os.remove(pdf)
        print(f'  OK  h2-programacion-pdf.png    '
              f'{os.path.getsize(ruta) // 1024:>4} KB   La hoja del PDF, tal cual sale')

        nav.close()

    print(f'\nCapturas en: {os.path.abspath(SALIDA)}')


if __name__ == '__main__':
    main()
