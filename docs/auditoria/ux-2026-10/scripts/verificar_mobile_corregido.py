# -*- coding: utf-8 -*-
"""verificar_mobile.py CORREGIDO.

Tres bugs del original, los tres verificados contra el server real:

 1. LOGIN MUDO. Entra con `t@t.com` / `test12345`, que no existe: el POST vuelve
    a /accounts/login/ y el `except` no se dispara porque no hay excepcion.
    Despues, 5 de las 15 rutas de admin redirigen a `/` con status 200 y una a
    la pantalla de login. O sea: el script dice que audita 15 pantallas y en
    realidad mide la home 6 veces. Acá se loguea con el rol que corresponde a
    cada ruta y se VERIFICA la URL final.

 2. BOTONES INVISIBLES CONTADOS COMO DESALINEADOS. La barra se marca mal si sus
    .btn no miden todos lo mismo, pero no se filtran los que no se ven. El
    "Registrarse" del navbar es `hidden md:inline-flex`: a 375px mide 0px de
    ancho y rompe el conteo de CUALQUIER barra que lo contenga. Resultado
    medido: 15/15 paginas marcadas como problematicas; filtrando invisibles,
    0/15.

 3. UNA BARRA DE UN SOLO BOTON NO ES UNA BARRA. Si al sacar los invisibles
    queda un solo boton, no hay nada que alinear: no se cuenta.

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python verificar_mobile_corregido.py
"""
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'

CUENTAS = {
    'jugador': ('jugador1a@ejemplo.com', 'ManualDemo2026'),
    'organizador': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'admin': ('admin.demo@todopadel.club', 'AdminDemo2026'),
}

# (rol necesario, ruta). El rol None es publico.
RUTAS = [
    (None, '/'),
    (None, '/torneos/abiertos/'),
    (None, '/torneos/en-juego/'),
    (None, '/torneos/finalizados/'),
    (None, '/torneos/2/'),
    ('organizador', '/torneos/admin/2/gestionar/'),
    ('organizador', '/torneos/admin/listado/'),
    ('jugador', '/accounts/perfil/'),
    ('organizador', '/torneos/admin/dashboard/'),
    ('organizador', '/torneos/admin/formatos/'),
    (None, '/torneos/circuitos/'),
    ('admin', '/equipos/admin/listado/'),
    (None, '/accounts/organizadores/'),
    ('organizador', '/torneos/admin/embudo/'),
    ('jugador', '/equipos/buscar-companero/'),
]

MEDIR = r"""() => {
  const W = window.innerWidth;

  // Visible de verdad: ni 0px, ni display:none, ni visibility:hidden, ni
  // opacity:0, ni dibujado fuera de la pantalla (el drawer cerrado).
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return false;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      return false;
    if (r.right <= 0 || r.left >= W) return false;
    return true;
  };

  const fuera = [];
  document.querySelectorAll('button, a.btn, .btn, .collapse-title, table, .card').forEach(el => {
    if (!visible(el)) return;
    // Un contenedor con scroll horizontal propio puede ser mas ancho a proposito
    // (el cuadro de la llave). Cuenta tanto la clase como el style inline.
    if (el.closest('.overflow-x-auto, [style*="overflow-x"], .drawer-side, aside, dialog')) return;
    const r = el.getBoundingClientRect();
    if (r.left < 0) return;
    if (r.right > W + 1) {
      const cls = (el.className || '').toString().split(' ').slice(0, 2).join('.');
      fuera.push(el.tagName + '.' + cls + ' der=' + Math.round(r.right));
    }
  });

  let desalineadas = 0, barras = 0;
  const detalle = [];
  document.querySelectorAll('.flex').forEach(el => {
    let btns = [...el.children].filter(c => c.classList && c.classList.contains('btn'));
    if (el.classList.contains('join')) return;
    // (2) fuera los que no se ven
    btns = btns.filter(visible);
    // (3) con menos de dos botones visibles no hay barra que alinear
    if (btns.length < 2) return;
    if (btns.every(b => ['btn-circle','btn-square','btn-xs'].some(c => b.classList.contains(c)))) return;
    barras++;
    const anchos = [...new Set(btns.map(b => Math.round(b.getBoundingClientRect().width)))];
    if (anchos.length > 1) {
      desalineadas++;
      detalle.push(anchos.join('/') + 'px :: ' +
                   btns.map(b => (b.textContent || '').trim().slice(0, 14) || '(icono)').join(' | '));
    }
  });

  return {
    desborde: Math.max(0, document.documentElement.scrollWidth - W),
    fuera: [...new Set(fuera)].slice(0, 4),
    barras: barras,
    desalineadas: desalineadas,
    detalle: detalle.slice(0, 3),
  };
}"""


def sesion(nav, rol):
    ctx = nav.new_context(viewport={'width': 375, 'height': 812})
    pg = ctx.new_page()
    if rol is None:
        return pg
    email, clave = CUENTAS[rol]
    pg.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
    pg.fill('input[name=username]', email)
    pg.fill('input[name=password]', clave)
    pg.click('form button.btn-primary')
    pg.wait_for_load_state('networkidle')
    # (1) verificar que el login ANDUVO
    if '/accounts/login' in pg.url:
        raise RuntimeError(f'el login como {rol} fallo: sigue en {pg.url}')
    return pg


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        sesiones = {}
        malas = 0
        medidas = 0
        for rol, ruta in RUTAS:
            if rol not in sesiones:
                try:
                    sesiones[rol] = sesion(nav, rol)
                except RuntimeError as e:
                    print(f'  LOGIN  {e}')
                    sesiones[rol] = None
            pg = sesiones[rol]
            if pg is None:
                continue
            try:
                r = pg.goto(BASE + ruta, wait_until='networkidle', timeout=30000)
                pg.wait_for_timeout(600)
                if r.status != 200:
                    print(f'  [{r.status}]    {ruta}')
                    continue
                # (1) si el server redirigio, NO estamos midiendo lo que creemos
                destino = pg.url.replace(BASE, '') or '/'
                if destino.split('?')[0] != ruta:
                    print(f'  REDIRIGE  {ruta:<34} -> {destino}  (no se mide)')
                    continue
                medidas += 1
                d = pg.evaluate(MEDIR)
                mal = d['desborde'] > 2 or d['fuera'] or d['desalineadas']
                if mal:
                    malas += 1
                estado = 'PROBLEMA' if mal else 'ok'
                print(f"  {estado:<9} {ruta:<34} desborde={d['desborde']}px "
                      f"barras={d['barras']} desal={d['desalineadas']}")
                for e in d['fuera']:
                    print(f'              -> se pasa: {e}')
                for e in d['detalle']:
                    print(f'              -> barra despareja: {e}')
            except Exception as e:
                print(f'  ERROR {ruta}: {str(e)[:70]}')
        nav.close()
        print(f'\npaginas con problemas: {malas}/{medidas} medidas de verdad '
              f'(de {len(RUTAS)} en la lista)')


if __name__ == '__main__':
    main()
