"""Recordatorios de partido antes de que se jueguen.

Hasta acá toda la notificación del producto era reactiva a un evento (se creó un
torneo, alguien se inscribió, se cargó un resultado). Esto es lo primero
disparado por tiempo: lo ejecuta un cron a través del management command
`enviar_recordatorios`.

Es idempotente: cada partido registra en `recordatorios_enviados` qué ventanas
ya se notificaron, así el cron puede correr las veces que quiera sin spamear.
"""
import logging

from django.utils import timezone

from accounts.push import jugadores_de_equipos, send_push_to_users

from ..models import Partido, PartidoGrupo

logger = logging.getLogger(__name__)

# (clave, horas antes, texto). El orden importa: se evalúa de la más lejana a la
# más cercana, y sólo se manda la ventana más específica que aplique.
VENTANAS = [
    ('24h', 24, 'Mañana jugás'),
    ('2h', 2, 'En un rato jugás'),
]

# Margen de tolerancia: si el cron corre cada 30 min, un partido puede caer en
# cualquier punto de la ventana. Sin holgura se perderían recordatorios.
HOLGURA_MINUTOS = 45


def _rivales(partido):
    """(equipo1, equipo2) del partido, sea de zona o de llave."""
    return partido.equipo1, partido.equipo2


def _texto(partido, prefijo):
    e1, e2 = _rivales(partido)
    nombre1 = e1.nombre if e1 else 'A definir'
    nombre2 = e2.nombre if e2 else 'A definir'
    hora = timezone.localtime(partido.fecha_hora).strftime('%H:%M')
    return f"{prefijo} a las {hora}: {nombre1} vs {nombre2}"


def partidos_a_recordar(ahora=None):
    """Partidos con horario que caen en alguna ventana y aún no se notificaron.

    Devuelve una lista de (partido, clave_ventana).
    """
    ahora = ahora or timezone.now()
    from datetime import timedelta

    pendientes = []
    for modelo in (Partido, PartidoGrupo):
        base = modelo.objects.filter(
            fecha_hora__isnull=False,
            ganador__isnull=True,          # si ya se jugó, no tiene sentido
            fecha_hora__gte=ahora,         # ni los que ya pasaron
        ).select_related('equipo1', 'equipo2')

        for partido in base:
            faltan = partido.fecha_hora - ahora
            ya_enviados = partido.recordatorios_enviados or []
            for clave, horas, _prefijo in VENTANAS:
                if clave in ya_enviados:
                    continue
                objetivo = timedelta(hours=horas)
                holgura = timedelta(minutes=HOLGURA_MINUTOS)
                if objetivo - holgura <= faltan <= objetivo + holgura:
                    pendientes.append((partido, clave))
                    break  # una sola ventana por corrida
    return pendientes


def enviar_recordatorios(ahora=None, dry_run=False):
    """Manda los recordatorios que correspondan. Devuelve (partidos, jugadores)."""
    pendientes = partidos_a_recordar(ahora)
    total_jugadores = 0

    for partido, clave in pendientes:
        prefijo = dict((c, p) for c, _h, p in VENTANAS)[clave]
        e1, e2 = _rivales(partido)
        jugadores = jugadores_de_equipos(e1, e2)
        if not jugadores:
            continue

        torneo = getattr(partido, 'torneo', None) or partido.grupo.torneo

        if not dry_run:
            try:
                send_push_to_users(
                    jugadores,
                    title=f"🎾 {torneo.nombre}",
                    body=_texto(partido, prefijo),
                    url=f"/torneos/{torneo.pk}/",
                    tag=f"recordatorio-{partido.__class__.__name__}-{partido.pk}-{clave}",
                )
            except Exception:
                logger.exception("Fallo el push del recordatorio del partido %s", partido.pk)

            # Marcamos incluso si el push falló: no queremos reintentar en loop
            # cada 30 minutos si, por ejemplo, VAPID no está configurado.
            enviados = list(partido.recordatorios_enviados or [])
            enviados.append(clave)
            partido.recordatorios_enviados = enviados
            partido.save(update_fields=['recordatorios_enviados'])

        total_jugadores += len(jugadores)

    return len(pendientes), total_jugadores
