import random
from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser, Division
from equipos.models import Equipo
from django.contrib.auth.models import Group, Permission


class Command(BaseCommand):
    help = 'Crea 32 jugadores, 16 equipos y la división inicial para desarrollo.'

    def handle(self, *args, **options):

        # --- 1. CONFIGURACIÓN DE PRUEBA ---
        NUM_JUGADORES = 32
        DIVISION_NOMBRE = "Septima"
        PASSWORD_JUGADOR = "test1234"

        try:
            # --- 2. CREAR OBTENER LA DIVISIÓN ---
            self.stdout.write(
                self.style.NOTICE(
                    f"--- 1. Buscando/Creando División: {DIVISION_NOMBRE} ---"
                )
            )
            division, created = Division.objects.get_or_create(nombre=DIVISION_NOMBRE)
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'División "{DIVISION_NOMBRE}" creada.')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'División "{DIVISION_NOMBRE}" ya existe.')
                )

            # --- 3. CREAR JUGADORES ---
            self.stdout.write(
                self.style.NOTICE(f"--- 2. Creando {NUM_JUGADORES} Jugadores ---")
            )

            # Limpiar jugadores antiguos de la división para asegurar 32 nuevos
            CustomUser.objects.filter(division=division, tipo_usuario='PLAYER').delete()

            jugadores = []
            for i in range(1, NUM_JUGADORES + 1):
                nombre_base = f"Jugador{i}"
                jugadores.append(
                    CustomUser(
                        email=f"jugador{i}@ejemplo.com",
                        nombre=nombre_base,
                        apellido=f"Apellido{i}",
                        numero_telefono=f"555-010-{i:02d}",
                        genero=random.choice([c[0] for c in CustomUser.Genero.choices]),
                        division=division,
                        tipo_usuario=CustomUser.TipoUsuario.PLAYER,
                        is_active=True,
                    )
                )

            # Usar bulk_create para eficiencia
            CustomUser.objects.bulk_create(jugadores)

            # Setear contraseñas después de bulk_create
            for user in CustomUser.objects.filter(
                division=division, tipo_usuario='PLAYER'
            ):
                user.set_password(PASSWORD_JUGADOR)
                user.save()

            self.stdout.write(self.style.SUCCESS(f"Creados {NUM_JUGADORES} jugadores."))

            # --- 4. CREAR EQUIPOS (Emparejar a los 32 jugadores en 16 equipos) ---
            self.stdout.write(self.style.NOTICE("--- 3. Creando 16 Equipos ---"))

            jugadores_list = list(
                CustomUser.objects.filter(
                    division=division, tipo_usuario='PLAYER'
                ).order_by('id')
            )

            if len(jugadores_list) != NUM_JUGADORES:
                self.stdout.write(
                    self.style.ERROR("Error: No se encontraron 32 jugadores.")
                )
                return

            # Eliminar equipos existentes para empezar limpio
            Equipo.objects.all().delete()

            equipos_a_crear = []
            for i in range(0, NUM_JUGADORES, 2):
                jugador1 = jugadores_list[i]
                jugador2 = jugadores_list[i + 1]

                # Crear la instancia del equipo, el método save() del modelo se encargará del nombre/división
                equipo_nombre = f"{jugador1.apellido}/{jugador2.apellido}"

                equipos_a_crear.append(
                    Equipo(
                        jugador1=jugador1,
                        jugador2=jugador2,
                        division=division,
                        nombre=equipo_nombre,  # Se usará el nombre generado aquí
                    )
                )

            Equipo.objects.bulk_create(equipos_a_crear)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Creados {len(equipos_a_crear)} equipos. ¡Todo listo para el torneo!"
                )
            )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Ocurrió un error crítico: {e}"))

        self.stdout.write(self.style.NOTICE("--------------------------------"))
        self.stdout.write(self.style.NOTICE("--- Resumen de Acciones ---"))
        self.stdout.write(self.style.NOTICE(f" División Creada: {DIVISION_NOMBRE}"))
        self.stdout.write(self.style.NOTICE(f" Jugadores Creados: {NUM_JUGADORES}"))
        self.stdout.write(self.style.NOTICE(f" Equipos Creados: {NUM_JUGADORES // 2}"))
        self.stdout.write(
            self.style.NOTICE(f" Contraseña para todos: {PASSWORD_JUGADOR}")
        )
        self.stdout.write(self.style.NOTICE("--------------------------------"))
