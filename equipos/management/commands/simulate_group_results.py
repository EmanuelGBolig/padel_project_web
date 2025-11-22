from django.core.management.base import BaseCommand
from django.db import transaction
from torneos.models import Torneo, PartidoGrupo
import random

class Command(BaseCommand):
    help = 'Simula la carga de resultados para todos los partidos de grupo pendientes.'

    def handle(self, *args, **options):
        
        self.stdout.write(self.style.NOTICE("--- Iniciando Simulación de Resultados de Grupo ---"))
        
        # Buscar torneos EN JUEGO
        torneos = Torneo.objects.filter(estado=Torneo.Estado.EN_JUEGO)
        
        if not torneos.exists():
            self.stdout.write(self.style.WARNING("No hay torneos EN JUEGO para simular."))
            return

        # Seleccionamos el último torneo creado (o podrías pedir ID por argumento)
        torneo = torneos.last()
        self.stdout.write(self.style.SUCCESS(f"Simulando resultados para el torneo: {torneo.nombre}"))

        partidos_pendientes = PartidoGrupo.objects.filter(
            grupo__torneo=torneo, 
            ganador__isnull=True
        )
        
        if not partidos_pendientes.exists():
            self.stdout.write(self.style.SUCCESS("Todos los partidos de grupo ya tienen resultado."))
            return

        count = 0
        with transaction.atomic():
            for partido in partidos_pendientes:
                # Simular lógica de sets (al mejor de 3)
                # Posibles resultados de sets: 2-0 o 2-1
                sets_ganador = 2
                sets_perdedor = random.choice([0, 1])
                
                # Decidir quién gana (50/50)
                if random.choice([True, False]):
                    partido.ganador = partido.equipo1
                    partido.e1_sets_ganados = sets_ganador
                    partido.e2_sets_ganados = sets_perdedor
                    
                    # Generar games realistas
                    # Ganador siempre hace 6, perdedor entre 0 y 4 (o 5/7 si es reñido)
                    # Set 1
                    partido.e1_set1 = 6
                    partido.e2_set1 = random.randint(0, 4)
                    # Set 2
                    partido.e1_set2 = 6
                    partido.e2_set2 = random.randint(0, 4)
                    
                    if sets_perdedor == 1:
                        # Si hubo 3 sets, hacemos que el perdedor haya ganado el 2do
                        partido.e1_set2 = random.randint(3, 5) # Perdió el 2do
                        partido.e2_set2 = 6
                        # Set 3 (Desempate)
                        partido.e1_set3 = 6
                        partido.e2_set3 = random.randint(0, 4)
                    
                else:
                    partido.ganador = partido.equipo2
                    partido.e2_sets_ganados = sets_ganador
                    partido.e1_sets_ganados = sets_perdedor
                    
                    # Set 1
                    partido.e2_set1 = 6
                    partido.e1_set1 = random.randint(0, 4)
                    # Set 2
                    partido.e2_set2 = 6
                    partido.e1_set2 = random.randint(0, 4)

                    if sets_perdedor == 1:
                        # Perdedor (E1) gana el 2do
                        partido.e2_set2 = random.randint(3, 5)
                        partido.e1_set2 = 6
                        # Set 3
                        partido.e2_set3 = 6
                        partido.e1_set3 = random.randint(0, 4)

                # Calcular games totales (aproximado)
                partido.e1_games_ganados = (partido.e1_set1 or 0) + (partido.e1_set2 or 0) + (partido.e1_set3 or 0)
                partido.e2_games_ganados = (partido.e2_set1 or 0) + (partido.e2_set2 or 0) + (partido.e2_set3 or 0)
                
                partido.save()
                count += 1

        self.stdout.write(self.style.SUCCESS(f"¡Éxito! Se cargaron resultados para {count} partidos."))
        self.stdout.write(self.style.NOTICE("Ahora puedes ir al panel de administración y generar los Octavos de Final."))