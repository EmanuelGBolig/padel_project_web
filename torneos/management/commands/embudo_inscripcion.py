"""Mide dónde se cae la gente en el camino a inscribirse a un torneo.

Correr en el shell de Render (Dashboard -> Shell):

    python manage.py embudo_inscripcion

Es de SOLO LECTURA: no modifica nada.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count, Q
from django.utils import timezone

from equipos.models import Equipo, Invitation
from torneos.models import Inscripcion


def _pct(n, d):
    return f"{round(100 * n / d)}%" if d else "—"


class Command(BaseCommand):
    help = "Embudo: cuenta -> pareja -> inscripción. Solo lectura."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=0,
            help="Mirar solo usuarios creados en los últimos N días (0 = todos).",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        dias = options['dias']

        jugadores = User.objects.filter(tipo_usuario='PLAYER', is_dummy=False)
        if dias:
            desde = timezone.now() - timezone.timedelta(days=dias)
            jugadores = jugadores.filter(date_joined__gte=desde)

        total = jugadores.count()
        if not total:
            self.stdout.write("No hay jugadores para medir.")
            return

        ids = set(jugadores.values_list('id', flat=True))

        # 2. Los que llegaron a formar pareja
        en_pareja = set()
        for j1, j2 in Equipo.objects.values_list('jugador1', 'jugador2'):
            if j1:
                en_pareja.add(j1)
            if j2:
                en_pareja.add(j2)
        con_pareja = len(en_pareja & ids)

        # 3. Los que llegaron a inscribirse
        equipos_inscriptos = set(Inscripcion.objects.values_list('equipo_id', flat=True))
        inscriptos = set()
        for eid, j1, j2 in Equipo.objects.values_list('id', 'jugador1', 'jugador2'):
            if eid in equipos_inscriptos:
                if j1:
                    inscriptos.add(j1)
                if j2:
                    inscriptos.add(j2)
        con_inscripcion = len(inscriptos & ids)

        titulo = f"EMBUDO DE INSCRIPCIÓN{f' (últimos {dias} días)' if dias else ''}"
        self.stdout.write(self.style.SUCCESS(f"\n=== {titulo} ===\n"))
        self.stdout.write(f"  1. Crearon cuenta            {total:>5}   100%")
        self.stdout.write(
            f"  2. Formaron pareja           {con_pareja:>5}   {_pct(con_pareja, total):>4}"
            f"   (se caen {total - con_pareja})")
        self.stdout.write(
            f"  3. Se inscribieron a un torneo {con_inscripcion:>3}   {_pct(con_inscripcion, total):>4}"
            f"   (se caen {con_pareja - con_inscripcion} más)")

        # --- Invitaciones: acá se ve si la espera es el cuello ---
        estados = dict(
            Invitation.objects.values_list('status').annotate(n=Count('id'))
        )
        total_inv = sum(estados.values())
        self.stdout.write(f"\n=== INVITACIONES DE PAREJA ({total_inv}) ===")
        if total_inv:
            for estado, n in sorted(estados.items(), key=lambda x: -x[1]):
                self.stdout.write(f"  {str(estado):<12} {n:>5}   {_pct(n, total_inv)}")
            pendientes = estados.get('PENDING', 0) or estados.get('pending', 0)
            if pendientes:
                self.stdout.write(self.style.WARNING(
                    f"\n  -> {pendientes} invitaciones colgadas esperando que el otro acepte."
                ))
        else:
            self.stdout.write("  (ninguna)")

        # --- Parejas que nunca compitieron ---
        equipos = Equipo.objects.filter(es_dummy=False)
        sin_torneo = equipos.exclude(id__in=equipos_inscriptos).count()
        self.stdout.write(f"\n=== PAREJAS ===")
        self.stdout.write(f"  total                  {equipos.count():>5}")
        self.stdout.write(f"  nunca se inscribieron  {sin_torneo:>5}")

        # --- Jugadores con teléfono: sirve para saber si el flujo por WhatsApp es viable ---
        con_tel = jugadores.exclude(numero_telefono='').exclude(
            numero_telefono__isnull=True).count()
        self.stdout.write(
            f"\n  jugadores con teléfono cargado: {con_tel} de {total} ({_pct(con_tel, total)})")
        self.stdout.write(
            "  (importante: si es alto, el flujo de invitar por WhatsApp es viable)\n")
