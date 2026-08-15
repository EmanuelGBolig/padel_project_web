"""Barre las pantallas con formularios a 390px y busca inputs que se pasan.

Para cada página loguea con el rol que corresponde y mide todo input, select,
textarea, botón de formulario y widget (select2) que sobresalga de su tarjeta
contenedora o de la pantalla. También avisa si la página entera scrollea a lo
ancho.

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python auditoria_inputs.py
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

CUENTAS = {
    'jugador': ('jugador1a@ejemplo.com', 'ManualDemo2026'),
    'demo': ('demo.informe@todopadel.club', 'DemoInforme2026'),
    'organizador': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'admin': ('admin.demo@todopadel.club', 'AdminDemo2026'),
}

# (quién, ruta, nombre legible)
PAGINAS = [
    (None, '/accounts/registro/', 'Registro'),
    (None, '/accounts/login/', 'Login'),
    (None, '/torneos/3/anotarme-sin-cuenta/', 'Alta sin cuenta'),
    (None, '/torneos/abiertos/', 'Torneos abiertos (filtros)'),
    ('demo', '/torneos/3/anotarme-con-pareja/', 'Anotarse con compañero'),
    ('jugador', '/torneos/5/inscribirse/', 'Confirmar inscripción'),
    ('jugador', '/accounts/perfil/', 'Perfil (form de foto/datos)'),
    ('jugador', '/equipos/crear/', 'Crear pareja (jugador)'),
    ('jugador', '/equipos/buscar-companero/', 'Buscar compañero'),
    ('demo', '/accounts/cambiar-password/', 'Cambiar contraseña'),
    ('organizador', '/torneos/admin/crear/', 'Crear torneo'),
    ('organizador', '/torneos/admin/3/editar/', 'Editar torneo'),
    ('organizador', '/torneos/admin/2/gestionar/', 'Gestión en juego'),
    ('organizador', '/torneos/admin/3/gestionar/', 'Gestión abierto'),
    ('organizador', '/torneos/admin/3/cobros/', 'Cobros'),
    ('organizador', '/equipos/organizador/crear-pareja/', 'Crear pareja (org)'),
    ('organizador', '/accounts/organizador/crear-jugador-dummy/', 'Crear jugador'),
    ('organizador', '/accounts/organizacion/ajustes/', 'Ajustes organización'),
    ('organizador', '/accounts/organizacion/sponsors/', 'Sponsors'),
    ('organizador', '/torneos/admin/formatos/nuevo/', 'Formato nuevo'),
    ('organizador', '/torneos/americano/crear/', 'Americano nuevo'),
    ('admin', '/accounts/usuarios/merge/', 'Fusionar cuentas'),
    ('admin', '/accounts/jugador/1/editar/', 'Editar jugador'),
    ('admin', '/torneos/admin/circuitos/nuevo/', 'Circuito nuevo'),
]

MEDIDOR = """() => {
    const vw = document.documentElement.clientWidth;
    const problemas = [];
    if (document.documentElement.scrollWidth > vw + 1)
        problemas.push({que: 'LA PÁGINA ENTERA', detalle: 'scrollWidth ' +
                        document.documentElement.scrollWidth + ' > viewport ' + vw});
    const candidatos = document.querySelectorAll(
        'input, select, textarea, .select2-container, .input, .select, .file-input, .textarea');
    candidatos.forEach(el => {
        const r = el.getBoundingClientRect();
        if (!r.width) return;
        // Invisible (drawer cerrado, checkbox del tema, swap oculto): no cuenta.
        if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})) return;
        if (el.closest('.drawer-side, [aria-hidden="true"]')) return;
        // ¿se sale de la pantalla?
        if (r.right > vw + 1.5 || r.left < -1.5) {
            problemas.push({que: el.tagName.toLowerCase() +
                (el.name ? '[name=' + el.name + ']' : '.' + String(el.className).split(' ')[0]),
                detalle: 'fuera de pantalla ' + Math.round(Math.max(r.right - vw, -r.left)) + 'px'});
            return;
        }
        // ¿se sale de su tarjeta/contenedor con padding?
        let padre = el.parentElement;
        while (padre && padre !== document.body) {
            const cs = getComputedStyle(padre);
            if (cs.overflow !== 'visible' || padre.classList.contains('card-body')
                || padre.classList.contains('card') || padre.classList.contains('modal-box')) {
                const pr = padre.getBoundingClientRect();
                const der = pr.right - parseFloat(cs.paddingRight);
                const izq = pr.left + parseFloat(cs.paddingLeft);
                if (r.right > der + 1.5 || r.left < izq - 1.5) {
                    problemas.push({que: el.tagName.toLowerCase() +
                        (el.name ? '[name=' + el.name + ']' : '.' + String(el.className).split(' ')[0]),
                        detalle: 'se pasa ' + Math.round(Math.max(r.right - der, izq - r.left)) +
                                 'px de ' + padre.tagName.toLowerCase() + '.' +
                                 String(padre.className).split(' ')[0]});
                }
                break;
            }
            padre = padre.parentElement;
        }
    });
    // dedup
    const vistos = new Set();
    return problemas.filter(p => {
        const k = p.que + p.detalle;
        if (vistos.has(k)) return false;
        vistos.add(k); return true;
    }).slice(0, 8);
}"""


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        sesiones = {}

        def pagina_de(rol):
            if rol not in sesiones:
                ctx = nav.new_context(viewport={'width': 390, 'height': 844})
                pg = ctx.new_page()
                if rol is not None:
                    email, clave = CUENTAS[rol]
                    pg.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
                    pg.fill('input[name=username]', email)
                    pg.fill('input[name=password]', clave)
                    pg.click('form button.btn-primary')
                    pg.wait_for_load_state('networkidle')
                sesiones[rol] = pg
            return sesiones[rol]

        con_problemas = 0
        for rol, ruta, nombre in PAGINAS:
            pg = pagina_de(rol)
            try:
                pg.goto(f'{BASE}{ruta}', wait_until='networkidle')
                pg.wait_for_timeout(700)
                problemas = pg.evaluate(MEDIDOR)
            except Exception as e:
                print(f'!! {nombre:<30} no se pudo medir: {str(e)[:60]}')
                continue
            if problemas:
                con_problemas += 1
                print(f'XX {nombre}  ({ruta})')
                for pr in problemas:
                    print(f'     {pr["que"]:<38} {pr["detalle"]}')
            else:
                print(f'ok {nombre}')
        nav.close()
        print(f'\n{con_problemas} páginas con problemas de {len(PAGINAS)} revisadas')


if __name__ == '__main__':
    main()
