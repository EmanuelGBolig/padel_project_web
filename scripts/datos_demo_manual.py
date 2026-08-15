"""Prepara el elenco y los datos de vitrina para las capturas del MANUAL.

Crea (o reusa) usuarios de demostración con contraseñas conocidas, uno por rol,
y deja la base de desarrollo en un estado que se vea bien en las capturas:
resultados cargados, pagos en distintos estados, avisos de búsqueda de
compañero, notificaciones.

Sólo toca datos de prueba de la base LOCAL. No borra nada.

Uso:  python scripts/datos_demo_manual.py
"""
import os
import sys
import random

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.utils import timezone  # noqa: E402

from accounts.models import CustomUser, Division, Organizacion  # noqa: E402
from equipos.models import BusquedaCompanero  # noqa: E402
from torneos.models import Inscripcion, PartidoGrupo, Torneo  # noqa: E402

random.seed(21)  # capturas reproducibles

ORG = Organizacion.objects.get(nombre='Club Demo')
DIV = Division.objects.first()

ELENCO = {
    # rol            email                                clave
    'ORGANIZER': ('organizador.demo@todopadel.club', 'OrganizadorDemo2026'),
    'ADMIN':     ('admin.demo@todopadel.club',       'AdminDemo2026'),
}

print('--- Usuarios del manual ---')
for tipo, (email, clave) in ELENCO.items():
    u, creado = CustomUser.objects.get_or_create(
        email=email,
        defaults={'nombre': 'Demo', 'apellido': tipo.capitalize(),
                  'tipo_usuario': tipo, 'division': DIV},
    )
    u.tipo_usuario = tipo
    u.organizacion = ORG if tipo == 'ORGANIZER' else u.organizacion
    u.is_staff = (tipo == 'ADMIN')
    u.set_password(clave)
    u.debe_cambiar_password = False
    u.save()
    print(f'  {"creado " if creado else "reusado"} {tipo:<10} {email}')

# El jugador con historial: uno del torneo de 24 parejas (usuario de seed del
# repo, base local). Se le pone una clave conocida para poder loguearlo en las
# capturas de "Mi equipo" / "Mis torneos" / estadísticas.
j = CustomUser.objects.get(email='jugador1a@ejemplo.com')
j.set_password('ManualDemo2026')
j.debe_cambiar_password = False
j.save()
print(f'  clave seteada          jugador1a@ejemplo.com (equipo {j.equipo})')

# --- Torneo 2 (en juego): cargar todos los resultados de zona que falten ----
t2 = Torneo.objects.get(pk=2)
pendientes = PartidoGrupo.objects.filter(grupo__torneo=t2, ganador__isnull=True)
print(f'--- Torneo {t2.pk}: cargando {pendientes.count()} resultados de zona ---')
for p in pendientes:
    if random.random() < 0.5:
        g, s1, s2 = p.equipo1, (6, 3), (6, 4)
    else:
        g, s1, s2 = p.equipo2, (3, 6), (4, 6)
    p.e1_set1, p.e2_set1 = s1
    p.e1_set2, p.e2_set2 = s2
    p.ganador = g
    p.save()
print('  listo (las posiciones se recalculan solas por signal)')

# --- Torneo 3 (abierto con precio): pagos en los tres estados ---------------
t3 = Torneo.objects.get(pk=3)
ins = list(Inscripcion.objects.filter(torneo=t3).order_by('pk'))
print(f'--- Torneo {t3.pk}: {len(ins)} inscripciones, repartiendo estados de pago ---')
for i, insc in enumerate(ins):
    if i % 3 == 0:
        insc.estado_pago, insc.monto_pagado = 'PA', t3.precio_inscripcion
        insc.fecha_pago = timezone.now()
    elif i % 3 == 1:
        insc.estado_pago, insc.monto_pagado = 'SE', t3.senia
        insc.fecha_pago = timezone.now()
    else:
        insc.estado_pago, insc.monto_pagado = 'PE', 0
        insc.fecha_pago = None
    insc.save()
print('  pagos: 1/3 pagado, 1/3 señado, 1/3 pendiente')

# --- Un torneo FINALIZADO, para la ficha con campeones ----------------------
import datetime  # noqa: E402

campeon = j.equipo
t_fi, creado = Torneo.objects.get_or_create(
    nombre='Clausura Demo 2025',
    defaults={
        'division': DIV,
        'fecha_inicio': datetime.date(2025, 11, 22),
        'fecha_limite_inscripcion': datetime.date(2025, 11, 20),
        'estado': 'FI',
        'organizacion': ORG,
        'ganador_del_torneo': campeon,
        'ciudad': 'Mar del Plata',
    },
)
if not creado and not t_fi.ganador_del_torneo:
    t_fi.ganador_del_torneo = campeon
    t_fi.save(update_fields=['ganador_del_torneo'])
print(f'--- Torneo finalizado: {t_fi.nombre} (pk {t_fi.pk}), campeón {campeon} ---')

# --- Un abierto de la MISMA división que el equipo demo ---------------------
# Para la captura de "anotarse con cuenta": el Abierto Demo es de Primera y el
# equipo demo de Séptima, así que ahí la app (con razón) no lo deja anotarse.
t_ab7, _ = Torneo.objects.get_or_create(
    nombre='Apertura Séptima 2026',
    defaults={
        'division': j.division,
        'fecha_inicio': timezone.now().date() + datetime.timedelta(days=10),
        'fecha_limite_inscripcion': timezone.now().date() + datetime.timedelta(days=8),
        'estado': 'AB',
        'organizacion': ORG,
        'ciudad': 'Mar del Plata',
    },
)
print(f'--- Abierto de {j.division}: {t_ab7.nombre} (pk {t_ab7.pk}) ---')

# --- Un circuito que agrupe los torneos del club ----------------------------
from torneos.models import Circuito  # noqa: E402

circ, creado = Circuito.objects.get_or_create(
    nombre='Circuito Club Demo 2026',
    defaults={
        'descripcion': 'Las cuatro fechas del año en el club. Los puntos de '
                       'cada fecha se acumulan en la tabla general.',
        'organizacion': ORG,
        'activo': True,
    },
)
circ.torneos.set([t2, t3, t_fi])
print(f'--- Circuito: {circ.nombre} con {circ.torneos.count()} torneos ---')

# --- Avisos de "busco compañero" -------------------------------------------
print('--- Búsqueda de compañero ---')
BusquedaCompanero.objects.all().delete()
for email, texto in [
    ('demo.companero@todopadel.club',
     'Busco compañera para el Abierto Demo. Juego de revés, disponibilidad '
     'sábados por la tarde.'),
    ('jugador3a@ejemplo.com',
     'Somos de Mar del Plata, busco compañero de séptima para torneos de fin '
     'de semana.'),
]:
    autor = CustomUser.objects.filter(email=email).first()
    if autor:
        BusquedaCompanero.objects.create(jugador=autor, nota=texto,
                                         division=autor.division or DIV,
                                         ciudad='Mar del Plata', activa=True)
        print(f'  aviso de {autor.full_name}')

print('LISTO')
