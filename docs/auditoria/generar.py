# -*- coding: utf-8 -*-
"""Genera el informe de auditoría en HTML a partir de los hallazgos verificados.

Los hallazgos vienen de hallazgos.json (salida del workflow de auditoría, ya
deduplicada y con el veredicto del verificador adversarial). El marco editorial
—resumen, orden de ataque, qué salió limpio— se escribe acá.

Uso:  python docs/auditoria/generar.py
"""
import html
import json
import os

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATOS = os.path.join(RAIZ, 'docs', 'auditoria', 'hallazgos.json')
SALIDA = os.path.join(RAIZ, 'docs', 'auditoria', 'informe-auditoria.html')

SEV = {
    'critica': ('Crítico', '#c2410c'),
    'alta':    ('Alto',    '#a16207'),
    'media':   ('Medio',   '#0369a1'),
    'baja':    ('Bajo',    '#5d6d66'),
}
DIM = {
    'permisos-idor':     'Permisos',
    'logica-torneo':     'Lógica del torneo',
    'htmx-contratos':    'Templates',
    'rendimiento':       'Rendimiento',
    'formularios-datos': 'Datos',
    'frontend-visual':   'Visual',
}


def e(t):
    return html.escape(str(t or ''))


def tarjeta(f, n):
    etiqueta, color = SEV[f['severidad']]
    dim = DIM.get(f.get('dim', ''), 'General')
    arreglo = f.get('arreglo_sugerido', '')
    return f'''
    <article class="hallazgo sev-{f['severidad']}" id="h{n}">
      <div class="hallazgo-cab">
        <span class="chip" style="--c:{color}">{etiqueta}</span>
        <span class="dim">{e(dim)}</span>
        <span class="num">#{n}</span>
      </div>
      <h3>{e(f['titulo'])}</h3>
      <p class="donde"><code>{e(f['archivo'])}:{e(f['linea'])}</code></p>
      <p>{e(f['descripcion'])}</p>
      {f'<p class="arreglo"><b>Cómo se arregla.</b> {e(arreglo)}</p>' if arreglo else ''}
    </article>'''


def main():
    hallazgos = json.load(open(DATOS, encoding='utf-8'))
    orden = {'critica': 0, 'alta': 1, 'media': 2, 'baja': 3}
    hallazgos.sort(key=lambda f: (orden[f['severidad']], f['archivo']))
    cuenta = {k: sum(1 for f in hallazgos if f['severidad'] == k) for k in SEV}

    grupos = {k: [] for k in SEV}
    for i, f in enumerate(hallazgos, 1):
        grupos[f['severidad']].append(tarjeta(f, i))

    plantilla = open(os.path.join(RAIZ, 'docs', 'auditoria', 'plantilla.html'),
                     encoding='utf-8').read()
    salida = (plantilla
              .replace('{{CRITICOS}}', '\n'.join(grupos['critica']))
              .replace('{{ALTOS}}', '\n'.join(grupos['alta']))
              .replace('{{MEDIOS}}', '\n'.join(grupos['media']))
              .replace('{{BAJOS}}', '\n'.join(grupos['baja']))
              .replace('{{N_TOTAL}}', str(len(hallazgos)))
              .replace('{{N_CRITICOS}}', str(cuenta['critica']))
              .replace('{{N_ALTOS}}', str(cuenta['alta']))
              .replace('{{N_MEDIOS}}', str(cuenta['media']))
              .replace('{{N_BAJOS}}', str(cuenta['baja'])))
    open(SALIDA, 'w', encoding='utf-8').write(salida)
    print(f'{SALIDA}\n{len(hallazgos)} hallazgos · {os.path.getsize(SALIDA)//1024} KB')


if __name__ == '__main__':
    main()
