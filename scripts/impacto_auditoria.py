"""Mide el impacto de los cambios de la auditoría sobre los datos que YA existen.

No modifica nada: sólo cuenta. Sirve para saber, antes de desplegar, si algún
cambio de comportamiento afecta a algo que hoy funciona.

Uso:  python scripts/impacto_auditoria.py
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser  # noqa: E402
from torneos.models import Americano  # noqa: E402
from torneos.services.alta_sin_cuenta import _cola_telefono, _solo_digitos  # noqa: E402

print('=' * 62)
print('IMPACTO DE LOS CAMBIOS SOBRE LOS DATOS ACTUALES')
print('=' * 62)

# --- 1. Americanos sin club: sus organizadores perderían el panel ------------
print('\n1) Americanos sin club asignado')
huerfanos = Americano.objects.filter(organizacion__isnull=True)
print(f'   total de americanos: {Americano.objects.count()}')
print(f'   sin organizacion:    {huerfanos.count()}')
if huerfanos.exists():
    print('   >> ATENCION: sus organizadores van a recibir 404 al gestionarlos.')
    print('      Hay que asignarles club antes de desplegar. Son:')
    for a in huerfanos[:20]:
        print(f'        #{a.pk} {a.nombre} (estado {a.estado})')
else:
    print('   OK: ninguno queda huerfano.')

# --- 2. Teléfonos que dejan de engancharse automáticamente ------------------
print('\n2) Enganche por telefono (antes 8 digitos, ahora 10 normalizados)')
con_tel = CustomUser.objects.exclude(numero_telefono='').exclude(
    numero_telefono__isnull=True)
total = con_tel.count()
normalizables, cortos = 0, []
colas = {}
for pk, numero in con_tel.values_list('id', 'numero_telefono'):
    cola = _cola_telefono(numero)
    if cola:
        normalizables += 1
        colas.setdefault(cola, []).append(pk)
    else:
        cortos.append((pk, numero, len(_solo_digitos(numero))))
print(f'   usuarios con telefono cargado: {total}')
print(f'   se normalizan a 10 digitos:    {normalizables}')
print(f'   quedan cortos (no enganchan):  {len(cortos)}')
if cortos:
    print('   >> Esos numeros ya NO enganchan solos: el alta va a crear cuenta')
    print('      nueva en vez de reusar la existente (se arregla fusionando).')
    for pk, numero, n in cortos[:10]:
        print(f'        usuario {pk}: "{numero}" ({n} digitos)')

ambiguos = {c: ids for c, ids in colas.items() if len(ids) > 1}
print(f'   numeros compartidos por 2+ cuentas: {len(ambiguos)}')
if ambiguos:
    print('   >> Con el criterio nuevo NO se engancha ninguno (antes agarraba')
    print('      el primero, al azar). Son duplicados reales para fusionar:')
    for cola, ids in list(ambiguos.items())[:10]:
        print(f'        ...{cola}: cuentas {ids}')

# --- 3. Cuentas fusionadas que antes se "resucitaban" -----------------------
print('\n3) Cuentas ya fusionadas (ahora se excluyen de las busquedas del alta)')
fusionadas = CustomUser.objects.filter(merged_into__isnull=False)
print(f'   cuentas fusionadas: {fusionadas.count()}')
print('   >> Antes el alta podia devolverlas y revivir un duplicado que un')
print('      admin ya habia unificado. Ahora se saltean. Es el fix, no un riesgo.')

print('\n' + '=' * 62)
