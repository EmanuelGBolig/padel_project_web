"""Busca texto ilegible en MODO CLARO (el tema por defecto).

El bug tipico: `text-white` o `text-base-100` sobre una tarjeta `bg-base-100`.
En el tema oscuro base-100 es oscuro y se lee bien, asi que pasa desapercibido
si se prueba solo en oscuro — es como se colaron los formularios de "Crear
jugador" y "Crear pareja", con el titulo y TODAS las etiquetas invisibles.

Mide contraste real: luminancia del texto contra la del primer ancestro con
fondo opaco. Marca lo que queda por debajo del umbral.

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python auditoria_modo_claro.py
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
django.setup()

from playwright.sync_api import sync_playwright  # noqa: E402

BASE = 'http://localhost:8010'
UMBRAL = 45  # diferencia de luminancia (0-255) por debajo de la cual no se lee

CUENTAS = {
    'jugador': ('jugador1a@ejemplo.com', 'ManualDemo2026'),
    'organizador': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'admin': ('admin.demo@todopadel.club', 'AdminDemo2026'),
}

PAGINAS = [
    (None, '/'),
    (None, '/torneos/abiertos/'),
    (None, '/torneos/2/'),
    (None, '/torneos/2/vivo/'),
    (None, '/torneos/2/programacion/'),
    (None, '/torneos/3/anotarme-sin-cuenta/'),
    (None, '/accounts/registro/'),
    (None, '/accounts/login/'),
    (None, '/accounts/rankings/'),
    (None, '/torneos/circuitos/'),
    ('jugador', '/accounts/perfil/'),
    ('jugador', '/accounts/notificaciones/'),
    ('jugador', '/equipos/mi-equipo/'),
    ('jugador', '/equipos/buscar-companero/'),
    ('jugador', '/torneos/mis-torneos/'),
    ('organizador', '/torneos/admin/dashboard/'),
    ('organizador', '/torneos/admin/listado/'),
    ('organizador', '/torneos/admin/crear/'),
    ('organizador', '/torneos/admin/2/gestionar/'),
    ('organizador', '/torneos/admin/3/cobros/'),
    ('organizador', '/equipos/organizador/crear-pareja/'),
    ('organizador', '/accounts/organizador/crear-jugador-dummy/'),
    ('organizador', '/accounts/organizacion/ajustes/'),
    ('organizador', '/torneos/admin/embudo/'),
    ('admin', '/accounts/usuarios/duplicados/'),
    ('admin', '/accounts/usuarios/merge/'),
    ('admin', '/equipos/admin/listado/'),
]

MEDIDOR = """(umbral) => {
    // El color NO se parsea a mano: DaisyUI usa oklch() y leer los números
    // sueltos da cualquier cosa (el tercero es el ángulo de tono, 0-360, que
    // parseado como canal RGB dispara falsos positivos en toda la app).
    // Se deja que el navegador lo convierta pintando 1px en un canvas.
    const cv = document.createElement('canvas');
    cv.width = cv.height = 1;
    const cx = cv.getContext('2d', {willReadFrequently: true});

    const aRgba = (color) => {
        if (!color) return null;
        cx.clearRect(0, 0, 1, 1);
        cx.fillStyle = 'rgba(0,0,0,0)';
        try { cx.fillStyle = color; } catch (e) { return null; }
        cx.fillRect(0, 0, 1, 1);
        const d = cx.getImageData(0, 0, 1, 1).data;
        return {r: d[0], g: d[1], b: d[2], a: d[3] / 255};
    };
    const lumDe = (rgba) => 0.2126 * rgba.r + 0.7152 * rgba.g + 0.0722 * rgba.b;

    const lum = (c) => {
        const rgba = aRgba(c);
        if (!rgba || rgba.a < 0.15) return null;
        return lumDe(rgba);
    };
    const out = [];
    document.querySelectorAll('h1,h2,h3,h4,p,span,a,button,td,th,label,li,div').forEach(el => {
        const txt = el.textContent.trim();
        if (!txt || el.children.length) return;
        const cs = getComputedStyle(el);
        if (cs.visibility === 'hidden' || cs.display === 'none') return;
        const op = parseFloat(cs.opacity);
        if (op < 0.15) return;
        const r = el.getBoundingClientRect();
        if (!r.width || !r.height) return;
        let lt = lum(cs.color);
        if (lt === null) return;
        let padre = el, fondo = null;
        while (padre && padre !== document.documentElement) {
            const f = lum(getComputedStyle(padre).backgroundColor);
            if (f !== null) { fondo = f; break; }
            padre = padre.parentElement;
        }
        if (fondo === null) fondo = 255;
        // La opacidad acerca el texto al fondo: se aplica antes de comparar.
        const efectiva = fondo + (lt - fondo) * op;
        if (Math.abs(efectiva - fondo) < umbral) {
            out.push(txt.slice(0, 45).replace(/\\s+/g, ' '));
        }
    });
    return [...new Set(out)].slice(0, 5);
}"""


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        sesiones = {}

        def pagina(rol):
            if rol not in sesiones:
                ctx = nav.new_context(viewport={'width': 1280, 'height': 900},
                                      color_scheme='light')
                pg = ctx.new_page()
                if rol:
                    email, clave = CUENTAS[rol]
                    pg.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
                    pg.fill('input[name=username]', email)
                    pg.fill('input[name=password]', clave)
                    pg.click('form button.btn-primary')
                    pg.wait_for_load_state('networkidle')
                sesiones[rol] = pg
            return sesiones[rol]

        con_problemas = 0
        for rol, ruta in PAGINAS:
            pg = pagina(rol)
            try:
                pg.goto(f'{BASE}{ruta}', wait_until='networkidle')
                pg.wait_for_timeout(600)
                malos = pg.evaluate(MEDIDOR, UMBRAL)
            except Exception as e:
                print(f'!! {ruta:<45} {str(e)[:50]}')
                continue
            if malos:
                con_problemas += 1
                print(f'XX {ruta}')
                for m in malos:
                    print(f'      «{m}»')
            else:
                print(f'ok {ruta}')
        nav.close()
        print(f'\n{con_problemas} de {len(PAGINAS)} páginas con texto ilegible en modo claro')


if __name__ == '__main__':
    main()
