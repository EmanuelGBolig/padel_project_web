import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.core.management.base import BaseCommand
from accounts.models import Division
from equipos.models import RankingJugador
from accounts.utils import get_division_rankings
from unittest.mock import patch

class Command(BaseCommand):
    help = 'Migra los puntajes calculados al vuelo hacia las nuevas tablas de base de datos RankingJugador y RankingEquipo'

    @patch('django.core.cache.cache.get', return_value=None)
    @patch('django.core.cache.cache.set')
    def handle(self, mock_set, mock_get, *args, **kwargs):
        self.stdout.write("--- Iniciando Migración de Rankings a BD ---")
        
        divisiones = Division.objects.all()
        
        for division in divisiones:
            self.stdout.write(f"\nProcesando División: {division.nombre}")
            
            # --- JUGADORES ---
            self.stdout.write("  -> Migrando Jugadores...")
            jugadores_data = get_division_rankings(division, force_recalc=True)
            
            for index, item in enumerate(jugadores_data):
                jugador = item['jugador']
                puntos = item['puntos']
                torneos = item['torneos_ganados']
                victorias = item['victorias']
                partidos = item['partidos_totales']
                
                # Actualizar o Crear fila en DB
                try:
                    RankingJugador.objects.update_or_create(
                        jugador=jugador,
                        division=division,
                        defaults={
                            'puntos': puntos,
                            'torneos_ganados': torneos,
                            'victorias': victorias,
                            'partidos_jugados': partidos
                        }
                    )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f"     [SKIP] Jugador {jugador.id} saltado: {e}"))
            
            self.stdout.write(f"     [OK] {len(jugadores_data)} Jugadores migrados.")

        self.stdout.write(self.style.SUCCESS("\n--- MIGRACIÓN DE RANKINGS COMPLETADA CON ÉXITO ---"))
