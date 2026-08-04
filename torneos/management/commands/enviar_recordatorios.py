"""Manda los recordatorios de partido. Pensado para un cron.

En Render: Settings -> Cron Jobs -> cada 30 minutos:

    python manage.py enviar_recordatorios

Es idempotente: cada partido registra qué ventanas ya se notificaron, así que
correrlo de más no molesta a nadie.
"""
from django.core.management.base import BaseCommand

from torneos.services.recordatorios import enviar_recordatorios, partidos_a_recordar


class Command(BaseCommand):
    help = "Envía recordatorios push de los partidos próximos (24h y 2h antes)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help="Muestra qué se mandaría, sin mandar nada ni marcar los partidos.",
        )

    def handle(self, *args, **options):
        seco = options['dry_run']

        if seco:
            pendientes = partidos_a_recordar()
            self.stdout.write(f"[dry-run] {len(pendientes)} partido(s) a recordar:")
            for partido, clave in pendientes:
                e1 = partido.equipo1.nombre if partido.equipo1 else '?'
                e2 = partido.equipo2.nombre if partido.equipo2 else '?'
                self.stdout.write(f"   [{clave}] {partido.fecha_hora:%d/%m %H:%M}  {e1} vs {e2}")
            return

        partidos, jugadores = enviar_recordatorios()
        self.stdout.write(self.style.SUCCESS(
            f"Recordatorios enviados: {partidos} partido(s), {jugadores} jugador(es)."
        ))
