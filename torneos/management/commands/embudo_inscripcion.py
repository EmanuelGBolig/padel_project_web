"""Mide dónde se cae la gente en el camino a inscribirse a un torneo.

Correr en el shell de Render (si tenés acceso):

    python manage.py embudo_inscripcion

Si no hay shell, la misma info está en la web: /torneos/admin/embudo/

Es de SOLO LECTURA: no modifica nada.
"""
from django.core.management.base import BaseCommand

from torneos.services.embudo import calcular_embudo


class Command(BaseCommand):
    help = "Embudo: cuenta -> pareja -> inscripción. Solo lectura."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=0,
            help="Mirar solo usuarios creados en los últimos N días (0 = todos).",
        )

    def handle(self, *args, **options):
        e = calcular_embudo(options['dias'])

        if not e['total']:
            self.stdout.write("No hay jugadores para medir.")
            return

        sufijo = f" (últimos {e['dias']} días)" if e['dias'] else ""
        self.stdout.write(self.style.SUCCESS(f"EMBUDO DE INSCRIPCIÓN{sufijo}"))
        self.stdout.write("")
        self.stdout.write(f"  1. Crearon cuenta              {e['total']:>5}   100%")
        self.stdout.write(
            f"  2. Formaron pareja             {e['con_pareja']:>5}   {e['pct_pareja']:>3}%"
            f"   (se caen {e['caen_en_pareja']})"
        )
        self.stdout.write(
            f"  3. Se inscribieron a un torneo {e['con_inscripcion']:>5}   {e['pct_inscripcion']:>3}%"
            f"   (se caen {e['caen_en_inscripcion']} más)"
        )

        self.stdout.write("")
        self.stdout.write(f"INVITACIONES DE PAREJA ({e['total_invitaciones']})")
        if e['total_invitaciones']:
            for estado, n in e['invitaciones']:
                self.stdout.write(f"  {str(estado):<12} {n:>5}")
            if e['invitaciones_pendientes']:
                self.stdout.write(self.style.WARNING(
                    f"  -> {e['invitaciones_pendientes']} colgadas esperando que el otro acepte."
                ))
        else:
            self.stdout.write("  (ninguna)")

        self.stdout.write("")
        self.stdout.write("PAREJAS")
        self.stdout.write(f"  total                  {e['total_equipos']:>5}")
        self.stdout.write(f"  nunca se inscribieron  {e['equipos_sin_torneo']:>5}")

        self.stdout.write("")
        self.stdout.write(
            f"  jugadores con teléfono: {e['con_telefono']} de {e['total']} "
            f"({e['pct_telefono']}%)"
        )
        self.stdout.write("  (si es alto, el flujo de invitar por WhatsApp es viable)")
