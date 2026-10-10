# -*- coding: utf-8 -*-
"""Contraste REAL (ratio WCAG 2.1) en los dos temas, a 390px.

Diferencias con auditoria_modo_claro.py:

  1. Calcula el **ratio de contraste WCAG** ((L1+0.05)/(L2+0.05) con luminancia
     relativa linealizada), no una resta de luminancias gamma. Una resta de 45
     sobre 255 puede ser un ratio de 1.4:1 (ilegible) o de 12:1 segun donde
     caiga en la escala: el umbral viejo no detecta nada en los grises medios,
     que es justo donde vive el texto secundario de la app.
  2. Tiene en cuenta el **alpha del color del texto**. Tailwind/DaisyUI escriben
     `text-base-content/60` como un color con alpha; el script viejo leia la
     luminancia a alpha 1 y por eso daba 0 problemas.
  3. Compone los **fondos semitransparentes** (`bg-base-200/50`) sobre su
     ancestro en vez de quedarse con el primer fondo "opaco".
  4. Corre en **los dos temas** y en viewport de celular.
  5. Aplica el umbral de WCAG segun tamano: 3:1 para texto grande
     (>=24px, o >=18.66px y bold), 4.5:1 para el resto.
  6. Mide tambien el contraste de los **bordes de los controles** (1.5:1 real
     contra el fondo) para detectar inputs que no se ven.

Uso: python audit_contraste.py <corporate|business> <salida.json>
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from paginas import BASE, PAGINAS, hacer_sesion  # noqa: E402

from playwright.sync_api import sync_playwright  # noqa: E402

TEMA = sys.argv[1] if len(sys.argv) > 1 else 'corporate'
SALIDA = sys.argv[2] if len(sys.argv) > 2 else 'contraste.json'

MEDIDOR = r"""() => {
  // --- resolver cualquier notacion de color (incluido oklch) a rgba real ---
  // No se parsea a mano: `oklch(0.22 0.03 278)` leido con una regex y tratado
  // como rgb da cualquier cosa (el 3er numero es el angulo de tono, 0-360).
  const cv = document.createElement('canvas');
  cv.width = cv.height = 1;
  const cx = cv.getContext('2d', {willReadFrequently: true});
  const cache = new Map();
  const rgba = (c) => {
    if (!c) return null;
    if (cache.has(c)) return cache.get(c);
    cx.clearRect(0, 0, 1, 1);
    cx.fillStyle = 'rgba(0,0,0,0)';
    try { cx.fillStyle = c; } catch (e) { cache.set(c, null); return null; }
    if (cx.fillStyle === 'rgba(0, 0, 0, 0)' && !/transparent|rgba\(0, 0, 0, 0\)/.test(c)) {
      // fillStyle no acepto el valor
    }
    cx.globalCompositeOperation = 'copy';
    cx.fillRect(0, 0, 1, 1);
    cx.globalCompositeOperation = 'source-over';
    const d = cx.getImageData(0, 0, 1, 1).data;
    const v = {r: d[0], g: d[1], b: d[2], a: d[3] / 255};
    cache.set(c, v);
    return v;
  };

  // luminancia relativa WCAG (canales linealizados)
  const lumRel = (c) => {
    const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => {
    const la = lumRel(a), lb = lumRel(b);
    return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
  };
  // componer fg (con alpha) sobre bg opaco
  const sobre = (fg, bg) => ({
    r: fg.r * fg.a + bg.r * (1 - fg.a),
    g: fg.g * fg.a + bg.g * (1 - fg.a),
    b: fg.b * fg.a + bg.b * (1 - fg.a),
    a: 1,
  });

  // fondo efectivo de un elemento: compone todos los fondos semitransparentes
  // de la cadena de ancestros hasta encontrar uno opaco (o el html).
  const fondoDe = (el) => {
    const capas = [];
    let n = el;
    while (n && n.nodeType === 1) {
      const cs = getComputedStyle(n);
      const c = rgba(cs.backgroundColor);
      if (c && c.a > 0.001) {
        capas.push({c: c, op: parseFloat(cs.opacity)});
        if (c.a >= 0.999) break;
      }
      // una imagen/gradiente de fondo tapa: se marca y se corta
      if (cs.backgroundImage && cs.backgroundImage !== 'none') {
        capas.push({grad: true});
        break;
      }
      n = n.parentElement;
    }
    const conGrad = capas.some(x => x.grad);
    let base = {r: 255, g: 255, b: 255, a: 1};
    const rev = capas.filter(x => !x.grad).reverse();
    for (const capa of rev) base = sobre(capa.c, base);
    return {color: base, gradiente: conGrad};
  };

  // opacidad heredada acumulada
  const opAcum = (el) => {
    let o = 1, n = el;
    while (n && n.nodeType === 1) { o *= parseFloat(getComputedStyle(n).opacity); n = n.parentElement; }
    return o;
  };

  const vis = el => {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) return false;
    if (el.checkVisibility && !el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true}))
      return false;
    return true;
  };

  // Un .drawer-side cerrado se dibuja FUERA de pantalla con translate, no con
  // display:none: checkVisibility dice que es visible. Se marca aparte para no
  // mezclar lo que el usuario ve hoy con lo que vera cuando abra el menu.
  const fueraDePantalla = el => {
    const r = el.getBoundingClientRect();
    return r.right <= 0 || r.left >= innerWidth;
  };

  const malos = [], todos = [];
  const SEL = 'h1,h2,h3,h4,h5,h6,p,span,a,button,td,th,label,li,div,small,strong,b,em,figcaption,legend,summary,option';
  document.querySelectorAll(SEL).forEach(el => {
    // solo nodos con texto propio
    const propio = [...el.childNodes].filter(n => n.nodeType === 3)
                    .map(n => n.textContent).join('').trim();
    if (!propio) return;
    if (!vis(el)) return;
    const cs = getComputedStyle(el);
    const px = parseFloat(cs.fontSize);
    const peso = parseInt(cs.fontWeight, 10) || 400;
    const grande = px >= 24 || (px >= 18.66 && peso >= 700);
    const umbral = grande ? 3.0 : 4.5;

    const fg0 = rgba(cs.color);
    if (!fg0) return;
    const f = fondoDe(el);
    const op = opAcum(el);
    // alpha efectivo del texto = alpha del color * opacidad heredada
    const fg = sobre({r: fg0.r, g: fg0.g, b: fg0.b, a: Math.min(1, fg0.a * op)}, f.color);
    const rt = ratio(fg, f.color);
    const reg = {
      txt: propio.slice(0, 48).replace(/\s+/g, ' '),
      px: Math.round(px * 10) / 10, peso: peso, ratio: Math.round(rt * 100) / 100,
      umbral: umbral, color: cs.color, fondo: `rgb(${Math.round(f.color.r)},${Math.round(f.color.g)},${Math.round(f.color.b)})`,
      grad: f.gradiente,
      cls: (el.className || '').toString().slice(0, 60),
      tag: el.tagName.toLowerCase(),
      oculto: fueraDePantalla(el) || !!el.closest('.drawer-side'),
    };
    todos.push({ratio: reg.ratio, px: reg.px, ok: rt >= umbral, oculto: reg.oculto});
    if (rt < umbral && !f.gradiente) malos.push(reg);
  });

  // bordes de controles (WCAG 1.4.11 componentes no textuales: 3:1)
  const bordes = [];
  document.querySelectorAll('input:not([type=hidden]),select,textarea').forEach(el => {
    if (!vis(el)) return;
    const cs = getComputedStyle(el);
    if (parseFloat(cs.borderTopWidth) === 0) {
      bordes.push({tipo: el.tagName.toLowerCase(), name: el.name || '', sinBorde: true,
                   ratio: null, cls: (el.className || '').toString().slice(0, 40)});
      return;
    }
    const b = rgba(cs.borderTopColor);
    const f = fondoDe(el.parentElement || el);
    if (!b) return;
    const comp = sobre(b, f.color);
    const rt = ratio(comp, f.color);
    bordes.push({tipo: el.tagName.toLowerCase(), name: el.name || '',
                 ratio: Math.round(rt * 100) / 100,
                 cls: (el.className || '').toString().slice(0, 40)});
  });

  const vistos = todos.filter(t => !t.oculto);
  return {malos: malos, total: todos.length, totalVisible: vistos.length,
          bajo3: vistos.filter(t => t.ratio < 3).length,
          bajo45: vistos.filter(t => !t.ok).length,
          enMenu: todos.filter(t => t.oculto && !t.ok).length,
          bordes: bordes,
          tema: document.documentElement.getAttribute('data-theme')};
}"""


def main():
    todo = {'tema': TEMA, 'paginas': {}}
    with sync_playwright() as p:
        nav = p.chromium.launch()
        sesiones = {}
        for rol, ruta, nombre in PAGINAS:
            if rol not in sesiones:
                sesiones[rol] = hacer_sesion(
                    nav, rol, {'width': 390, 'height': 844}, tema=TEMA,
                    color_scheme='light' if TEMA == 'corporate' else 'dark')
            pg = sesiones[rol]
            try:
                r = pg.goto(f'{BASE}{ruta}', wait_until='networkidle', timeout=30000)
                if r.status != 200:
                    print('  !!', nombre, r.status)
                    continue
                pg.wait_for_timeout(500)
                d = pg.evaluate(MEDIDOR)
                d['ruta'] = ruta
                todo['paginas'][nombre] = d
                print(f"  {nombre:<24} nodos={d['totalVisible']:<5} "
                      f"bajo_umbral={d['bajo45']:<4} bajo_3:1={d['bajo3']:<4} "
                      f"(menu cerrado: {d['enMenu']})")
            except Exception as e:
                print('  !!', nombre, str(e)[:70])
        nav.close()
    with io.open(SALIDA, 'w', encoding='utf-8') as fh:
        fh.write(json.dumps(todo, ensure_ascii=False))
    print('escrito', SALIDA)


if __name__ == '__main__':
    main()
