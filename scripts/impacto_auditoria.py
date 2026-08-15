"""Mide el impacto de los cambios de la auditoría sobre los datos que YA existen.

No modifica nada: sólo cuenta. La misma información está en la página de
diagnóstico (`/torneos/admin/revisar/`, sección "Impacto de los últimos
cambios"), que es la vía para mirarla en producción sin shell. Este script es
para verla desde la terminal en local.

Uso:  python scripts/impacto_auditoria.py
"""
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.services.impacto import revisar_impacto  # noqa: E402

imp = revisar_impacto()

print('=' * 62)
print('IMPACTO DE LOS CAMBIOS SOBRE LOS DATOS ACTUALES')
print('=' * 62)

am = imp['americanos']
print('\n1) Americanos sin club asignado')
print(f'   total: {am["total"]}  |  sin club: {am["cantidad"]}')
if am['cantidad']:
    print('   >> Sus organizadores van a recibir 404 al gestionarlos.')
    for a in am['huerfanos']:
        print(f'      #{a.pk} {a.nombre} ({a.estado})')
else:
    print('   OK: ninguno queda huerfano.')

tel = imp['telefonos']
print('\n2) Enganche por telefono (antes 8 digitos, ahora 10 normalizados)')
print(f'   con telefono: {tel["total"]}  |  comparables: {tel["normalizables"]}')
print(f'   demasiado cortos: {tel["cantidad_cortos"]}')
for c in tel['cortos']:
    print(f'      {c["nombre"]}: "{c["numero"]}" ({c["digitos"]} digitos)')
print(f'   numeros en 2+ cuentas: {tel["cantidad_compartidos"]}')
for g in tel['compartidos']:
    cuentas = ', '.join(f'{n} (#{pk})' for pk, n, _ in g['cuentas'])
    print(f'      ...{g["cola"]}: {cuentas}')
if not tel['cantidad_cortos'] and not tel['cantidad_compartidos']:
    print('   OK: ningun telefono queda afectado.')

print(f'\n3) Cuentas ya fusionadas: {imp["fusionadas"]}')
print('   (el alta dejo de devolverlas: es el arreglo, no un riesgo)')

print('\n' + '=' * 62)
print('REQUIERE ACCION ANTES DE DESPLEGAR' if imp['requiere_accion']
      else 'NADA PARA HACER: ningun dato existente queda afectado')
print('=' * 62)
