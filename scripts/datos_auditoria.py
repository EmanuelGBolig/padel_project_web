r"""Siembra, de forma ADITIVA, el elenco y los torneos que necesitan los scripts
de auditoría de UI (`verificar_mobile.py`, `auditoria_ui.py`, `auditoria_inputs.py`,
`auditoria_modo_claro.py`).

A diferencia de `seed_dev_data`, acá **no se borra nada**: todo es get_or_create.
Deja la base local con un club, las cuatro cuentas por rol que esperan los
scripts, y tres torneos en estados distintos (abierto, en juego, finalizado)
para que las pantallas no se auditen vacías.

Uso:  venv\Scripts\python.exe scripts/datos_auditoria.py
"""
import datetime
import os
import sys

import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from accounts.models import Division, Organizacion  # noqa: E402
from equipos.models import Equipo  # noqa: E402
from torneos.models import Inscripcion, Torneo  # noqa: E402

User = get_user_model()

ELENCO = [
    ('admin.demo@todopadel.club', 'AdminDemo2026', 'ADMIN', 'Ana', 'Demo', True),
    ('organizador.demo@todopadel.club', 'OrganizadorDemo2026', 'ORGANIZER', 'Oscar', 'Demo', False),
    ('jugador1a@ejemplo.com', 'ManualDemo2026', 'PLAYER', 'Juli', 'Ejemplo', False),
    ('demo.informe@todopadel.club', 'DemoInforme2026', 'PLAYER', 'Dani', 'Informe', False),
]


def main():
    org, _ = Organizacion.objects.get_or_create(
        nombre='Club Demo', defaults={'alias': 'club-demo'})
    division, _ = Division.objects.get_or_create(
        nombre='Sexta', defaults={'orden': 6})
    print(f'club: {org.nombre} (/{org.alias}) | division: {division.nombre}')

    for email, clave, tipo, nombre, apellido, staff in ELENCO:
        u = User.objects.filter(email=email).first()
        if not u:
            u = User.objects.create_user(
                email=email, password=clave, nombre=nombre, apellido=apellido)
        u.tipo_usuario = tipo
        u.is_staff = staff or tipo == 'ADMIN'
        u.is_superuser = tipo == 'ADMIN'
        if tipo == 'ORGANIZER':
            u.organizacion = org
        u.set_password(clave)          # idempotente: la clave queda siempre la conocida
        u.save()
        print(f'  {tipo:<10} {email}')

    # Los torneos existentes se adoptan al club, si no la gestión queda vacía.
    Torneo.objects.filter(organizacion__isnull=True).update(organizacion=org, division=division)

    equipos = list(Equipo.objects.all()[:16])
    hoy = timezone.now().date()

    PLAN = [
        ('ABIERTO AL PUBLICO - SEXTA', 'AB', hoy + datetime.timedelta(days=14)),
        ('COPA CLUB DEMO - EN JUEGO', 'EJ', hoy - datetime.timedelta(days=1)),
        ('TORNEO DE VERANO - FINALIZADO', 'FN', hoy - datetime.timedelta(days=30)),
    ]
    for nombre, estado, fecha in PLAN:
        t, creado = Torneo.objects.get_or_create(
            nombre=nombre,
            defaults={
                'fecha_inicio': fecha,
                'fecha_limite_inscripcion': timezone.make_aware(
                    datetime.datetime.combine(fecha - datetime.timedelta(days=2),
                                              datetime.time(20, 0))),
                'categoria': 'X',
                'estado': estado,
                'organizacion': org,
                'division': division,
            },
        )
        if creado and estado == 'AB':
            # Un torneo abierto sin inscriptos muestra la pantalla vacía, no la real.
            for e in equipos[:6]:
                Inscripcion.objects.get_or_create(torneo=t, equipo=e)
        print(f'  torneo pk={t.pk} [{estado}] {nombre}'
              f'{" (nuevo)" if creado else " (ya estaba)"}')

    print('\nTorneos en la base:')
    for t in Torneo.objects.order_by('pk'):
        print(f'   /torneos/{t.pk}/  [{t.estado}] {t.nombre}')


if __name__ == '__main__':
    main()
