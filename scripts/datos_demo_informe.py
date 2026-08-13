"""Prepara datos de vitrina para las capturas del informe.

Crea/reusa un usuario 'demo.informe@todopadel.club' con notificaciones y una
invitacion de pareja pendiente. No borra ni toca nada preexistente.
"""
import os
import sys

import django

sys.path.insert(0, r'C:\Users\egome\Documents\ClaudeCode\padel_project_web')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.utils import timezone  # noqa: E402
from datetime import timedelta  # noqa: E402

from accounts.models import CustomUser, Division, Notificacion  # noqa: E402
from equipos.models import Invitation  # noqa: E402
from torneos.models import Torneo  # noqa: E402

EMAIL = 'demo.informe@todopadel.club'
CLAVE = 'DemoInforme2026'

div = Division.objects.first()

u, creado = CustomUser.objects.get_or_create(
    email=EMAIL,
    defaults={'nombre': 'Martina', 'apellido': 'Rossi',
              'tipo_usuario': 'PLAYER', 'division': div,
              'numero_telefono': '+54 9 223 555-1234'},
)
u.set_password(CLAVE)
u.debe_cambiar_password = False
u.division = div
u.save()
print(('creado' if creado else 'reusado'), u.email, 'pk', u.pk)

# --- Quien invita ---
inv_user, _ = CustomUser.objects.get_or_create(
    email='demo.companero@todopadel.club',
    defaults={'nombre': 'Sofía', 'apellido': 'Ferrari',
              'tipo_usuario': 'PLAYER', 'division': div},
)
inv_user.division = div
inv_user.save()

# El equipo del invitado tiene que estar vacio para que la caja se muestre.
if u.equipo:
    print('  OJO: ya tiene equipo, la caja de invitacion no se va a ver')

Invitation.objects.filter(invited=u, status='PENDING').delete()
Invitation.objects.filter(inviter=inv_user, invited=u).delete()
Invitation.objects.create(inviter=inv_user, invited=u, status='PENDING')
print('  invitacion pendiente de', inv_user.full_name)

# --- Notificaciones de vitrina ---
torneo = Torneo.objects.filter(estado='AB').first()
url_torneo = f'/torneos/{torneo.pk}/' if torneo else '/'

Notificacion.objects.filter(usuario=u).delete()
ahora = timezone.now()
guion = [
    ('🎾 ¡Invitación aceptada!',
     'Sofía Ferrari aceptó. Ya tienen equipo: Rossi / Ferrari.',
     '/equipos/mi-equipo/', False, timedelta(minutes=8)),
    ('⏰ Jugás en 2 horas',
     'Zona A · 18:30 · contra Pérez / Gómez.',
     url_torneo, False, timedelta(hours=3)),
    ('📋 Salieron las zonas',
     'Ya está armada la fase de grupos de Abierto Demo. Fijate cuándo jugás.',
     url_torneo, False, timedelta(hours=20)),
    ('✅ Pago confirmado',
     'El organizador confirmó tu inscripción a Abierto Demo.',
     url_torneo, True, timedelta(days=1, hours=4)),
    ('🏆 Ganaste tu partido',
     'Cargaron el resultado: 6-3 / 6-4. Pasás a cuartos.',
     url_torneo, True, timedelta(days=2)),
]
for titulo, cuerpo, url, leida, atras in guion:
    n = Notificacion.objects.create(usuario=u, titulo=titulo, cuerpo=cuerpo,
                                    url=url, leida=leida)
    # `creada` es auto_now_add: se pisa despues para escalonar las fechas.
    Notificacion.objects.filter(pk=n.pk).update(creada=ahora - atras)
print('  notificaciones:', Notificacion.objects.filter(usuario=u).count(),
      '| sin leer:', Notificacion.objects.filter(usuario=u, leida=False).count())

from django.core.cache import cache  # noqa: E402
cache.delete(f'notifications_count_{u.pk}')
print('LISTO')
