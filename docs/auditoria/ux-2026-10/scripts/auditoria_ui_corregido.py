# -*- coding: utf-8 -*-
"""auditoria_ui.py CORREGIDO + ampliado.

Qué estaba mal en el original (verificado contra el server real):

  * El login con `t@t.com` / `test12345` NO entra. Como el POST no lanza
    excepción, el script sigue como anónimo. De las 16 rutas, 6 terminan
    redirigidas a `/` con status 200 y 1 a la pantalla de login: el script
    mide la HOME seis veces y dice que auditó 16 pantallas. Por eso los
    totales ("266 botones", "73 textos < 11px") están inflados por repetición
    y no cubren las pantallas de gestión.
  * No distingue redirección de página real (`r.status == 200` también lo es
    una redirección seguida).
  * Cuenta como texto chico nodos del drawer cerrado, que está fuera de
    pantalla pero `display:block`.

Qué agrega:
  * Inventario del sistema de diseño: cuántos radios, sombras, tamaños de
    texto y alturas de botón distintos se usan de verdad.
  * Emoji usados como ícono, con su tamaño renderizado, al lado del inventario
    de SVG.
  * Jerarquía de headings (h1 ausente / saltos de nivel).
  * Tamaño de target contra los tres umbrales que importan: 24px (WCAG 2.5.8
    AA), 40px (la regla propia del proyecto) y 44px (Apple HIG / WCAG AAA).

Uso:  python manage.py runserver 8010 --noreload   (en otra terminal)
      python auditoria_ui_corregido.py
"""
import sys
from collections import Counter

from playwright.sync_api import sync_playwright

# En Windows la consola es cp1252 y cualquier emoji del reporte revienta el
# script con UnicodeEncodeError. Se fuerza UTF-8 en la salida.
try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass

BASE = 'http://localhost:8010'

CUENTAS = {
    'jugador': ('jugador1a@ejemplo.com', 'ManualDemo2026'),
    'organizador': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'admin': ('admin.demo@todopadel.club', 'AdminDemo2026'),
}

RUTAS = [
    (None, '/'),
    (None, '/torneos/abiertos/'),
    (None, '/torneos/en-juego/'),
    (None, '/torneos/finalizados/'),
    (None, '/torneos/2/'),
    (None, '/torneos/circuitos/'),
    (None, '/accounts/rankings/'),
    (None, '/accounts/organizadores/'),
    ('jugador', '/accounts/perfil/'),
    ('jugador', '/equipos/buscar-companero/'),
    ('jugador', '/torneos/mis-torneos/'),
    ('organizador', '/torneos/admin/dashboard/'),
    ('organizador', '/torneos/admin/listado/'),
    ('organizador', '/torneos/admin/crear/'),
    ('organizador', '/torneos/admin/2/gestionar/'),
    ('organizador', '/torneos/admin/formatos/'),
    ('organizador', '/torneos/admin/embudo/'),
    ('organizador', '/accounts/organizacion/ajustes/'),
    ('admin', '/equipos/admin/listado/'),
]

AUDITAR = r"""() => {
  const W = innerWidth;
  const visible = el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      return false;
    // el drawer cerrado se dibuja fuera de pantalla, no con display:none
    if (r.right <= 0 || r.left >= W) return false;
    return true;
  };

  const botones = [...document.querySelectorAll('button, a.btn, .btn, [role=button]')]
                   .filter(visible);

  const chicos = (lim) => botones.filter(b => {
    const r = b.getBoundingClientRect();
    return (r.height < lim || r.width < lim) && !b.closest('table, .join, .tabs');
  });

  const sinNombre = botones.filter(b => {
    const txt = (b.textContent || '').trim();
    return !txt && !b.getAttribute('aria-label') && !b.getAttribute('title');
  }).map(b => (b.className || '').toString().slice(0, 50));

  const tamanos = {};
  const alturas = {};
  botones.forEach(b => {
    const c = [...b.classList].filter(x => ['btn-xs','btn-sm','btn-md','btn-lg'].includes(x))[0]
              || 'btn-(base)';
    tamanos[c] = (tamanos[c] || 0) + 1;
    const h = Math.round(b.getBoundingClientRect().height);
    alturas[h] = (alturas[h] || 0) + 1;
  });

  const inputs = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
                  .filter(visible);
  const sinLabel = inputs.filter(i => {
    if (i.getAttribute('aria-label') || i.getAttribute('aria-labelledby')) return false;
    if (i.id && document.querySelector('label[for="' + CSS.escape(i.id) + '"]')) return false;
    return !i.closest('label');
  }).map(i => i.tagName.toLowerCase() + '[' + (i.name || '?') + ']');

  // --- tipografia, radios y sombras realmente usados ---
  const fuentes = {}, radios = {}, sombras = {}, ejemploChico = [];
  document.querySelectorAll('*').forEach(el => {
    if (!visible(el)) return;
    const cs = getComputedStyle(el);
    const propio = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim());
    if (propio) {
      const fs = Math.round(parseFloat(cs.fontSize) * 10) / 10;
      fuentes[fs] = (fuentes[fs] || 0) + 1;
      if (fs < 11 && ejemploChico.length < 6)
        ejemploChico.push(fs + 'px «' + el.textContent.trim().slice(0, 28) + '»');
    }
    const cls = (el.className || '').toString();
    if (/\b(card|collapse|alert|modal-box|stat|navbar|badge|btn|input|select|textarea|avatar)/.test(cls)) {
      const r = cs.borderTopLeftRadius;
      if (r !== '0px') radios[r] = (radios[r] || 0) + 1;
      if (cs.boxShadow && cs.boxShadow !== 'none')
        sombras[cs.boxShadow] = (sombras[cs.boxShadow] || 0) + 1;
    }
  });

  // --- iconografia: svg vs emoji ---
  const svgs = {};
  document.querySelectorAll('svg').forEach(s => {
    if (!visible(s)) return;
    const r = s.getBoundingClientRect();
    const k = Math.round(r.width) + 'x' + Math.round(r.height);
    svgs[k] = (svgs[k] || 0) + 1;
  });
  const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F2FF}\u{2B00}-\u{2BFF}\u{2190}-\u{21FF}]/gu;
  const emojis = {};
  document.querySelectorAll('*').forEach(el => {
    if (!visible(el)) return;
    const t = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('');
    if (!t) return;
    const px = Math.round(parseFloat(getComputedStyle(el).fontSize));
    let m;
    EMOJI.lastIndex = 0;
    while ((m = EMOJI.exec(t)) !== null) {
      const k = m[0] + '@' + px + 'px';
      emojis[k] = (emojis[k] || 0) + 1;
    }
  });

  // --- headings ---
  const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(visible)
              .map(h => +h.tagName[1]);
  let saltos = 0, prev = 0;
  hs.forEach(n => { if (prev && n > prev + 1) saltos++; prev = n; });

  const imgs = [...document.querySelectorAll('img')].filter(visible);

  return {
    botones: botones.length,
    chicos24: chicos(24).length,
    chicos40: chicos(40).length,
    chicos44: chicos(44).length,
    botonesSinNombre: sinNombre,
    tamanos, alturas, fuentes, radios, sombras, svgs, emojis,
    inputs: inputs.length,
    inputsSinLabel: sinLabel,
    textoMuyChico: Object.entries(fuentes).filter(([k]) => +k < 11)
                     .reduce((a, [, v]) => a + v, 0),
    ejemploChico,
    h1: hs.filter(n => n === 1).length,
    saltosHeading: saltos,
    imagenes: imgs.length,
    imagenesSinAlt: imgs.filter(i => !i.hasAttribute('alt')).length,
  };
}"""


def sesion(nav, rol):
    ctx = nav.new_context(viewport={'width': 390, 'height': 844})
    pg = ctx.new_page()
    if rol is None:
        return pg
    email, clave = CUENTAS[rol]
    pg.goto(f'{BASE}/accounts/login/', wait_until='networkidle')
    pg.fill('input[name=username]', email)
    pg.fill('input[name=password]', clave)
    pg.click('form button.btn-primary')
    pg.wait_for_load_state('networkidle')
    if '/accounts/login' in pg.url:
        raise RuntimeError(f'login como {rol} fallo (sigue en {pg.url})')
    return pg


def main():
    tot = Counter()
    g_tam, g_alt, g_fuentes, g_radios, g_sombras, g_svg, g_emoji = (Counter() for _ in range(7))
    sin_nombre, sin_label, ejemplos = [], [], []
    filas = []
    saltadas = []

    with sync_playwright() as p:
        nav = p.chromium.launch()
        sesiones = {}
        for rol, ruta in RUTAS:
            if rol not in sesiones:
                try:
                    sesiones[rol] = sesion(nav, rol)
                except RuntimeError as e:
                    print('  !!', e)
                    sesiones[rol] = None
            pg = sesiones[rol]
            if pg is None:
                saltadas.append((ruta, 'sin sesion'))
                continue
            try:
                r = pg.goto(BASE + ruta, wait_until='networkidle', timeout=30000)
                if r.status != 200:
                    saltadas.append((ruta, f'HTTP {r.status}'))
                    continue
                destino = (pg.url.replace(BASE, '') or '/').split('?')[0]
                if destino != ruta:
                    saltadas.append((ruta, f'redirige a {destino}'))
                    continue
                pg.wait_for_timeout(500)
                d = pg.evaluate(AUDITAR)
            except Exception as e:
                saltadas.append((ruta, str(e)[:50]))
                continue
            for k in ('botones', 'chicos24', 'chicos40', 'chicos44', 'inputs',
                      'textoMuyChico', 'imagenes', 'imagenesSinAlt', 'saltosHeading'):
                tot[k] += d[k]
            tot['sinH1'] += 1 if d['h1'] == 0 else 0
            tot['variosH1'] += 1 if d['h1'] > 1 else 0
            g_tam.update(d['tamanos'])
            g_alt.update({int(k): v for k, v in d['alturas'].items()})
            g_fuentes.update({float(k): v for k, v in d['fuentes'].items()})
            g_radios.update(d['radios'])
            g_sombras.update(d['sombras'])
            g_svg.update(d['svgs'])
            g_emoji.update(d['emojis'])
            sin_nombre += d['botonesSinNombre']
            sin_label += d['inputsSinLabel']
            ejemplos += d['ejemploChico']
            filas.append((ruta, d))
        nav.close()

    print('=' * 86)
    print('AUDITORIA DE UI — 390px (celular)')
    print('=' * 86)
    print(f"\n{'pantalla':<36} {'botones':>7} {'<40px':>6} {'<24px':>6} {'s/label':>8} {'txt<11':>7} {'h1':>3}")
    print('-' * 86)
    for ruta, d in filas:
        print(f"{ruta:<36} {d['botones']:>7} {d['chicos40']:>6} {d['chicos24']:>6} "
              f"{len(d['inputsSinLabel']):>8} {d['textoMuyChico']:>7} {d['h1']:>3}")
    if saltadas:
        print('\n  NO MEDIDAS (el original las contaba igual):')
        for ruta, por in saltadas:
            print(f'    {ruta:<40} {por}')

    print(f'\n--- TOTALES sobre {len(filas)} pantallas realmente medidas ---')
    print(f"  botones auditados                {tot['botones']}")
    print(f"  target < 44px (Apple HIG/AAA)    {tot['chicos44']}")
    print(f"  target < 40px (regla del repo)   {tot['chicos40']}")
    print(f"  target < 24px (WCAG 2.5.8 AA)    {tot['chicos24']}")
    print(f"  de solo icono sin nombre         {len(sin_nombre)}")
    print(f"  inputs sin label asociado        {len(sin_label)} de {tot['inputs']}")
    print(f"  texto < 11px                     {tot['textoMuyChico']}  ej: {ejemplos[:4]}")
    print(f"  imagenes sin alt                 {tot['imagenesSinAlt']} de {tot['imagenes']}")
    print(f"  pantallas sin <h1>               {tot['sinH1']} | con mas de un h1: {tot['variosH1']}"
          f" | saltos de nivel: {tot['saltosHeading']}")

    print('\n--- INVENTARIO DEL SISTEMA DE DISENO (cuanto mas chico, mas consistente) ---')
    print(f"  tamanos de boton (clase): {dict(g_tam.most_common())}")
    print(f"  alturas de boton distintas: {len(g_alt)} -> {dict(sorted(g_alt.items()))}")
    print(f"  tamanos de texto distintos: {len(g_fuentes)} -> {dict(sorted(g_fuentes.items()))}")
    print(f"  radios de borde distintos:  {len(g_radios)} -> {dict(g_radios.most_common(8))}")
    print(f"  sombras distintas:          {len(g_sombras)}")
    print(f"  tamanos de icono SVG:       {len(g_svg)} -> {dict(g_svg.most_common(8))}")
    print(f"  emoji usados como icono:    {len(g_emoji)} combinaciones caracter+tamano, "
          f"{sum(g_emoji.values())} apariciones")
    for k, v in g_emoji.most_common(10):
        print(f'     {k:<14} {v}')
    if sin_label:
        print(f'\n  inputs sin label: {sin_label[:16]}')


if __name__ == '__main__':
    main()
