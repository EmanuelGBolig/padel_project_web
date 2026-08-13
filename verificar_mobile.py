"""Barrido de UI en mobile: desborde horizontal y consistencia de botones.

Ignora el menú lateral cerrado (queda fuera de pantalla a propósito) y los
contenedores que ya tienen scroll horizontal propio.

Uso:  python manage.py runserver 8010   (en otra terminal)
      python verificar_mobile.py
"""
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'

RUTAS = [
    '/', '/torneos/abiertos/', '/torneos/en-juego/', '/torneos/finalizados/',
    '/torneos/2/', '/torneos/admin/2/gestionar/', '/torneos/admin/listado/',
    '/accounts/perfil/', '/torneos/admin/dashboard/', '/torneos/admin/formatos/',
    '/torneos/circuitos/', '/equipos/admin/listado/', '/accounts/organizadores/',
    '/torneos/admin/embudo/', '/equipos/buscar-companero/',
]

MEDIR = """() => {
  const W = window.innerWidth;
  const fuera = [];
  document.querySelectorAll('button, a.btn, .btn, .collapse-title, table, .card').forEach(el => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return;
    // Un contenedor con scroll horizontal propio puede ser mas ancho a proposito
    // (el cuadro de la llave). Cuenta tanto la clase como el style inline.
    if (el.closest('.overflow-x-auto, [style*=\\"overflow-x\\"], .drawer-side, aside, dialog')) return;
    if (r.left < 0) return;
    if (r.right > W + 1) {
      const cls = (el.className || '').toString().split(' ').slice(0, 2).join('.');
      fuera.push(el.tagName + '.' + cls + ' der=' + Math.round(r.right));
    }
  });
  let desalineadas = 0, barras = 0;
  document.querySelectorAll('.flex').forEach(el => {
    const btns = [...el.children].filter(c => c.classList && c.classList.contains('btn'));
    if (btns.length < 2 || el.classList.contains('join')) return;
    if (btns.every(b => ['btn-circle','btn-square','btn-xs'].some(c => b.classList.contains(c)))) return;
    barras++;
    if (new Set(btns.map(b => Math.round(b.getBoundingClientRect().width))).size > 1) desalineadas++;
  });
  return {
    desborde: Math.max(0, document.documentElement.scrollWidth - W),
    fuera: [...new Set(fuera)].slice(0, 4),
    barras: barras,
    desalineadas: desalineadas,
  };
}"""


def main():
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': 375, 'height': 812})
        pag = ctx.new_page()

        pag.goto(BASE + '/accounts/login/', wait_until='networkidle')
        try:
            pag.fill('input[name=username]', 't@t.com')
            pag.fill('input[name=password]', 'test12345')
            pag.press('input[name=password]', 'Enter')
            pag.wait_for_load_state('networkidle')
        except Exception as e:
            print('login:', e)

        malas = 0
        for ruta in RUTAS:
            try:
                r = pag.goto(BASE + ruta, wait_until='networkidle', timeout=25000)
                pag.wait_for_timeout(600)
                if r.status != 200:
                    print(f'  [{r.status}]    {ruta}')
                    continue
                d = pag.evaluate(MEDIR)
                mal = d['desborde'] > 2 or d['fuera'] or d['desalineadas']
                if mal:
                    malas += 1
                estado = 'PROBLEMA' if mal else 'ok'
                print(f"  {estado:<9} {ruta:<34} desborde={d['desborde']}px "
                      f"barras={d['barras']} desal={d['desalineadas']}")
                for e in d['fuera']:
                    print(f'              -> {e}')
            except Exception as e:
                print(f'  ERROR {ruta}: {str(e)[:60]}')

        nav.close()
        print(f'\npaginas con problemas: {malas}/{len(RUTAS)}')


if __name__ == '__main__':
    main()
