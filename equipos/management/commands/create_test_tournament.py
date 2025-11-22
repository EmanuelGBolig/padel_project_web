from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from accounts.models import CustomUser, Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion


class Command(BaseCommand):
    help = 'Crea un Torneo de prueba e inscribe a los 16 equipos existentes.'

    def handle(self, *args, **options):

        # --- 1. CONFIGURACIÓN DE PRUEBA ---
        DIVISION_NOMBRE = "Septima"
        TORNEO_NOMBRE = "Torneo Copa Test Final"
        CUPOS_TOTALES = 16
        torneo = None  # Inicializamos la variable para evitar errores si falla antes de crearse

        try:
            with transaction.atomic():
                self.stdout.write(
                    self.style.NOTICE("--- 1. Verificación de Datos Necesarios ---")
                )

                # Buscar División
                try:
                    division = Division.objects.get(nombre=DIVISION_NOMBRE)
                    self.stdout.write(
                        self.style.SUCCESS(f'División "{DIVISION_NOMBRE}" encontrada.')
                    )
                except Division.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(
                            f'ERROR: La división "{DIVISION_NOMBRE}" no existe. Ejecuta "python manage.py seed_dev_data" primero.'
                        )
                    )
                    return

                # Buscar Equipos
                equipos = Equipo.objects.filter(division=division)
                if equipos.count() < 16:
                    self.stdout.write(
                        self.style.ERROR(
                            f'ERROR: Se encontraron solo {equipos.count()} equipos. Se necesitan al menos 16. Ejecuta "python manage.py seed_dev_data".'
                        )
                    )
                    return

                # Tomamos solo los primeros 16 para llenar el cupo exacto para la fase de grupos perfecta
                equipos_a_inscribir = equipos[:16]
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Seleccionados {len(equipos_a_inscribir)} equipos para la inscripción.'
                    )
                )

                # Crear o buscar Admin de prueba
                admin_email = "admin@test.com"
                admin_user, created = CustomUser.objects.get_or_create(
                    email=admin_email,
                    defaults={
                        'nombre': 'Admin',
                        'apellido': 'Test',
                        'tipo_usuario': CustomUser.TipoUsuario.ADMIN,
                        'is_staff': True,
                        'is_superuser': True,
                    },
                )
                if created:
                    admin_user.set_password("admin1234")
                    admin_user.save()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'Administrador de prueba creado: {admin_email}/admin1234'
                        )
                    )

                # --- 2. CREAR TORNEO ---
                self.stdout.write(
                    self.style.NOTICE(f"--- 2. Creando Torneo: {TORNEO_NOMBRE} ---")
                )

                # Limpiar torneos anteriores con el mismo nombre para evitar duplicados
                Torneo.objects.filter(nombre=TORNEO_NOMBRE, division=division).delete()

                torneo = Torneo.objects.create(
                    nombre=TORNEO_NOMBRE,
                    division=division,
                    cupos_totales=CUPOS_TOTALES,
                    fecha_inicio=timezone.now().date() + timedelta(days=7),
                    fecha_limite_inscripcion=timezone.now() + timedelta(days=3),
                    equipos_por_grupo=2,  # Configuración por defecto: clasifican 2 por grupo
                    # CORRECCIÓN: Usamos las clases Enum definidas en tu nuevo models.py
                    estado=Torneo.Estado.ABIERTO,
                    tipo_torneo=Torneo.TipoTorneo.GRUPOS,
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Torneo "{torneo.nombre}" creado con PK: {torneo.pk}'
                    )
                )

                # --- 3. INSCRIBIR EQUIPOS ---
                self.stdout.write(
                    self.style.NOTICE(
                        f"--- 3. Inscribiendo {len(equipos_a_inscribir)} Equipos ---"
                    )
                )

                inscripciones = []
                for equipo in equipos_a_inscribir:
                    inscripciones.append(
                        Inscripcion(
                            torneo=torneo,
                            equipo=equipo,
                        )
                    )

                Inscripcion.objects.bulk_create(inscripciones)
                self.stdout.write(self.style.SUCCESS(f'Inscripción masiva completada.'))

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Ocurrió un error crítico durante la transacción: {e}"
                )
            )
            return  # Salimos de la función para no imprimir el resumen si hubo error

        # Resumen Final (Solo si 'torneo' se creó exitosamente)
        if torneo:
            self.stdout.write(self.style.NOTICE("--------------------------------"))
            self.stdout.write(self.style.NOTICE("--- Resumen de Acciones ---"))
            self.stdout.write(
                self.style.NOTICE(f" Torneo Creado: {TORNEO_NOMBRE} (PK: {torneo.pk})")
            )
            self.stdout.write(
                self.style.NOTICE(
                    f" Equipos Inscritos: {torneo.inscripciones.count()} de {CUPOS_TOTALES}"
                )
            )
            self.stdout.write(
                self.style.NOTICE(f" Admin de Prueba: {admin_email}/admin1234")
            )
            self.stdout.write(self.style.NOTICE("--------------------------------"))
            self.stdout.write(
                self.style.SUCCESS(
                    "¡LISTO! Ahora ve al Admin, entra a 'Gestionar' este torneo y presiona 'Generar Grupos'."
                )
            )
