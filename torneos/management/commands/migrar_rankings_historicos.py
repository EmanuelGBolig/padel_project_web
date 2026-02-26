import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.core.management.base import BaseCommand
from accounts.models import Division
from equipos.models import RankingJugador, RankingEquipo
from accounts.utils import get_division_rankings
from equipos.views import RankingListView
from django.test import RequestFactory
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
            
            self.stdout.write(f"     [OK] {len(jugadores_data)} Jugadores migrados.")

            # --- EQUIPOS ---
            self.stdout.write("  -> Migrando Equipos...")
            # Simulamos el request factory para usar la view sin refactorizarla completamente primero
            factory = RequestFactory()
            request = factory.get(f'/equipos/rankings/?division={division.id}')
            view = RankingListView()
            view.request = request
            
            # Esto devuelve array por division, buscamos la que toca
            rankings_todas_divs = view.get_queryset(force_recalc=True)
            equipos_data = []
            for r in rankings_todas_divs:
                if r['division'].id == division.id:
                    equipos_data = r['equipos']
                    break
                    
            for index, item in enumerate(equipos_data):
                equipo = item['equipo']
                puntos = item['puntos']
                torneos = item['torneos_ganados']
                victorias = item['victorias']
                partidos = item['partidos_jugados']
                
                # Actualizar o Crear fila en DB
                RankingEquipo.objects.update_or_create(
                    equipo=equipo,
                    division=division,
                    defaults={
                        'puntos': puntos,
                        'torneos_ganados': torneos,
                        'victorias': victorias,
                        'partidos_jugados': partidos
                    }
                )
                
            self.stdout.write(f"     [OK] {len(equipos_data)} Equipos migrados.")

        self.stdout.write(self.style.SUCCESS("\n--- MIGRACIÓN DE RANKINGS COMPLETADA CON ÉXITO ---"))
