"""Auditoria general de UI: botones, targets tactiles, accesibilidad y consistencia.

Recorre las pantallas principales a 375px (celular) y reporta problemas concretos.

Uso:  python manage.py runserver 8010   (en otra terminal)
      python auditoria_ui.py
"""
from collections import Counter

from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8010'

RUTAS = [
    '/', '/torneos/abiertos/', '/torneos/en-juego/', '/torneos/finalizados/',
    '/torneos/2/', '/torneos/admin/2/gestionar/', '/torneos/admin/listado/',
    '/accounts/perfil/', '/torneos/admin/dashboard/', '/torneos/admin/formatos/',
    '/torneos/circuitos/', '/equipos/admin/listado/', '/accounts/organizadores/',
    '/torneos/admin/embudo/', '/equipos/buscar-companero/', '/torneos/admin/crear/',
]

AUDITAR = """() => {
  const W = innerWidth;
  const visible = el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';
  };

  const botones = [...document.querySelectorAll('button, a.btn, .btn, [role=button]')].filter(visible);

  // 1) Target tactil chico (guia: 44x44 minimo)
  const chicos = botones.filter(b => {
    const r = b.getBoundingClientRect();
    return (r.height < 40 || r.width < 40) && !b.closest('table, .join, .tabs');
  }).map(b => ({
    txt: (b.textContent || '').trim().slice(0, 24) || '(icono)',
    w: Math.round(b.getBoundingClientRect().width),
    h: Math.round(b.getBoundingClientRect().height),
  }));

  // 2) Botones de solo icono sin nombre accesible
  const sinNombre = botones.filter(b => {
    const txt = (b.textContent || '').trim();
    return !txt && !b.getAttribute('aria-label') && !b.getAttribute('title');
  }).length;

  // 3) Variedad de tamanos de boton usados (consistencia)
  const tamanos = {};
  botones.forEach(b => {
    const c = [...b.classList].filter(x => ['btn-xs','btn-sm','btn-md','btn-lg'].includes(x))[0] || 'btn-(base)';
    tamanos[c] = (tamanos[c] || 0) + 1;
  });

  // 4) Inputs sin label asociado
  const inputs = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')].filter(visible);
  const sinLabel = inputs.filter(i => {
    if (i.getAttribute('aria-label') || i.getAttribute('placeholder')) return false;
    if (i.id && document.querySelector('label[for="' + CSS.escape(i.id) + '"]')) return false;
    return !i.closest('label');
  }).length;

  // 5) Texto muy chico
  const textoChico = [...document.querySelectorAll('p, span, div, td, li')].filter(el => {
    if (!visible(el) || !el.textContent.trim()) return false;
    if (el.children.length) return false;
    return parseFloat(getComputedStyle(el).fontSize) < 11;
  }).length;

  // 6) Imagenes sin alt
  const imgs = [...document.querySelectorAll('img')].filter(visible);
  const sinAlt = imgs.filter(i => !i.hasAttribute('alt')).length;

  return {
    botones: botones.length,
    targetsChicos: chicos.length,
    ejemplosChicos: chicos.slice(0, 3),
    botonesSinNombre: sinNombre,
    tamanos,
    inputs: inputs.length,
    inputsSinLabel: sinLabel,
    textoMuyChico: textoChico,
    imagenes: imgs.length,
    imagenesSinAlt: sinAlt,
  };
}"""


def main():
    global_tamanos = Counter()
    totales = Counter()
    filas = []

    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={'width': 375, 'height': 812})
        pag = ctx.new_page()

        pag.goto(BASE + '/accounts/login/', wait_until='networkidle')
        pag.fill('input[name=username]', 't@t.com')
        pag.fill('input[name=password]', 'test12345')
        pag.press('input[name=password]', 'Enter')
        pag.wait_for_load_state('networkidle')

        for ruta in RUTAS:
            try:
                r = pag.goto(BASE + ruta, wait_until='networkidle', timeout=25000)
                if r.status != 200:
                    continue
                pag.wait_for_timeout(500)
                d = pag.evaluate(AUDITAR)
                global_tamanos.update(d['tamanos'])
                for k in ('botones', 'targetsChicos', 'botonesSinNombre', 'inputs',
                          'inputsSinLabel', 'textoMuyChico', 'imagenes', 'imagenesSinAlt'):
                    totales[k] += d[k]
                filas.append((ruta, d))
            except Exception as e:
                print(f'  ERROR {ruta}: {str(e)[:60]}')

        nav.close()

    print('=' * 78)
    print('AUDITORIA DE UI — 375px (celular)')
    print('=' * 78)
    print(f"\n{'pantalla':<34} {'botones':>7} {'chicos':>7} {'s/nombre':>9} {'inputs s/label':>14}")
    print('-' * 78)
    for ruta, d in filas:
        print(f"{ruta:<34} {d['botones']:>7} {d['targetsChicos']:>7} "
              f"{d['botonesSinNombre']:>9} {d['inputsSinLabel']:>14}")

    print('\n--- TOTALES ---')
    print(f"  botones auditados         {totales['botones']}")
    print(f"  con target < 40px         {totales['targetsChicos']}")
    print(f"  de solo icono sin nombre  {totales['botonesSinNombre']}")
    print(f"  inputs sin label          {totales['inputsSinLabel']} de {totales['inputs']}")
    print(f"  texto < 11px              {totales['textoMuyChico']}")
    print(f"  imagenes sin alt          {totales['imagenesSinAlt']} de {totales['imagenes']}")
    print(f"\n  tamanos de boton usados: {dict(global_tamanos)}")


if __name__ == '__main__':
    main()
