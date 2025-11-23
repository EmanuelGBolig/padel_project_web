"""
Django management command para crear un torneo de 24 equipos con grupos de 3.
Uso: python manage.py crear_torneo_24
Crea el torneo y equipos, pero NO simula resultados.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import string

from torneos.models import Torneo, Inscripcion
from equipos.models import Equipo
from accounts.models import Division
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Crea un torneo de 24 equipos con grupos de 3 (sin simular resultados)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Creando Torneo de 24 Equipos ---'))

        # 1. Crear División si no existe
        division, _ = Division.objects.get_or_create(nombre="Séptima")
        
        # 2. Limpiar datos de prueba antiguos
        self.stdout.write("Limpiando datos de prueba anteriores...")
        # Eliminar torneos de prueba anteriores
        Torneo.objects.filter(nombre__startswith="Torneo 24 Equipos").delete()
        # Eliminar usuarios de prueba
        User.objects.filter(email__contains='@ejemplo.com').delete()
        
        # 3. Crear Torneo
        torneo_nombre = f"Torneo 24 Equipos - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        torneo = Torneo.objects.create(
            nombre=torneo_nombre,
            division=division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(days=7),
            cupos_totales=24,
            equipos_por_grupo=3,  # Grupos de 3
            estado=Torneo.Estado.ABIERTO
        )
        self.stdout.write(f"✓ Torneo creado: {torneo.nombre} (ID: {torneo.id})")

        # 4. Crear 24 equipos
        equipos_creados = 0
        for i in range(1, 25):
            # Crear jugadores
            sufijo = string.ascii_lowercase[i % 26] if i > 26 else ''
            email1 = f"jugador{i}a{sufijo}@ejemplo.com"
            email2 = f"jugador{i}b{sufijo}@ejemplo.com"
            
            jugador1 = User.objects.create_user(
                email=email1,
                nombre=f'Jugador{i}A',
                apellido=f'Sim{i}A',  # Apellido único
                division=division,
                tipo_usuario='PLAYER',
                password='sim123456'
            )
            
            jugador2 = User.objects.create_user(
                email=email2,
                nombre=f'Jugador{i}B',
                apellido=f'Sim{i}B',  # Apellido único
                division=division,
                tipo_usuario='PLAYER',
                password='sim123456'
            )
            
            # Crear equipo (nombre se genera automáticamente)
            equipo = Equipo.objects.create(
                jugador1=jugador1,
                jugador2=jugador2,
                division=division
            )
            
            # Inscribir en torneo
            Inscripcion.objects.create(
                torneo=torneo,
                equipo=equipo
            )
            equipos_creados += 1
        
        self.stdout.write(f"✓ {equipos_creados} equipos creados e inscritos")
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Torneo creado exitosamente!"))
        self.stdout.write(f"ID del torneo: {torneo.id}")
        self.stdout.write(f"URL: /torneos/{torneo.id}/")
        self.stdout.write(f"\nPasos siguientes:")
        self.stdout.write(f"1. Ve a /torneos/admin/{torneo.id}/manage/")
        self.stdout.write(f"2. Haz clic en 'Iniciar Torneo' para crear los grupos")
        self.stdout.write(f"3. Carga los resultados de los partidos")
        self.stdout.write(f"4. Genera el bracket de eliminatoria")
