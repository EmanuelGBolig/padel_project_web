"""Embudo de inscripción: dónde se cae la gente antes de anotarse a un torneo.

Lo consumen el management command `embudo_inscripcion` y la vista web
(para quien no tiene shell en Render).
"""
from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone

from equipos.models import Equipo, Invitation
from torneos.models import Inscripcion


def calcular_embudo(dias=0):
    """Devuelve el embudo completo. Es de sólo lectura."""
    User = get_user_model()

    jugadores = User.objects.filter(tipo_usuario='PLAYER', is_dummy=False)
    # Cota: un `dias` enorme desborda el cálculo de fecha (OverflowError). 20 años
    # es lo mismo que "desde siempre" para este producto.
    dias = max(0, min(int(dias or 0), 365 * 20))
    if dias:
        jugadores = jugadores.filter(
            date_joined__gte=timezone.now() - timezone.timedelta(days=dias)
        )

    total = jugadores.count()
    ids = set(jugadores.values_list('id', flat=True))

    # Escalón 2: llegaron a formar pareja
    en_pareja = set()
    for j1, j2 in Equipo.objects.values_list('jugador1', 'jugador2'):
        if j1:
            en_pareja.add(j1)
        if j2:
            en_pareja.add(j2)
    con_pareja = len(en_pareja & ids)

    # Escalón 3: llegaron a inscribirse
    equipos_inscriptos = set(Inscripcion.objects.values_list('equipo_id', flat=True))
    inscriptos = set()
    for eid, j1, j2 in Equipo.objects.values_list('id', 'jugador1', 'jugador2'):
        if eid in equipos_inscriptos:
            if j1:
                inscriptos.add(j1)
            if j2:
                inscriptos.add(j2)
    con_inscripcion = len(inscriptos & ids)

    invitaciones = dict(
        Invitation.objects.values_list('status').annotate(n=Count('id'))
    )
    total_inv = sum(invitaciones.values())
    pendientes = sum(
        n for estado, n in invitaciones.items()
        if str(estado).upper().startswith('P')
    )

    con_telefono = jugadores.exclude(
        numero_telefono=''
    ).exclude(numero_telefono__isnull=True).count()

    equipos = Equipo.objects.filter(es_dummy=False)
    total_equipos = equipos.count()

    def pct(n):
        return round(100 * n / total) if total else 0

    return {
        'dias': dias,
        'total': total,
        'con_pareja': con_pareja,
        'con_inscripcion': con_inscripcion,
        'pct_pareja': pct(con_pareja),
        'pct_inscripcion': pct(con_inscripcion),
        'caen_en_pareja': total - con_pareja,
        'caen_en_inscripcion': con_pareja - con_inscripcion,
        'invitaciones': sorted(invitaciones.items(), key=lambda x: -x[1]),
        'total_invitaciones': total_inv,
        'invitaciones_pendientes': pendientes,
        'con_telefono': con_telefono,
        'pct_telefono': pct(con_telefono),
        'total_equipos': total_equipos,
        'equipos_sin_torneo': equipos.exclude(id__in=equipos_inscriptos).count(),
    }
