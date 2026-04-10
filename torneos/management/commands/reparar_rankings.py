from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion, EquipoGrupo, PartidoGrupo, Partido
from accounts.utils import actualizar_rankings_en_bd

class Command(BaseCommand):
    help = 'Repara anomalías en los rankings de los jugadores y fusiona parejas duplicadas.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando Reparación de Rankings y Datos ---"))
        
        # 1. Identificar pares únicos (J1, J2) independientemente del orden
        all_teams = list(Equipo.objects.filter(es_dummy=False).values('id', 'jugador1_id', 'jugador2_id'))
        
        pair_map = {} # (id_mas_pequeño, id_mas_grande) -> [lista de IDs de equipo]
        
        for team in all_teams:
            j1 = team['jugador1_id']
            j2 = team['jugador2_id']
            if not j1 or not j2: continue
            
            pair = tuple(sorted([j1, j2]))
            if pair not in pair_map:
                pair_map[pair] = []
            pair_map[pair].append(team['id'])
        
        merged_count = 0
        
        # 2. Fusionar duplicados
        for pair, team_ids in pair_map.items():
            if len(team_ids) > 1:
                self.stdout.write(f"Fusionando {len(team_ids)} equipos para la pareja {pair}...")
                
                # Usar el primer ID como canónico
                canonical_id = team_ids[0]
                others = team_ids[1:]
                
                with transaction.atomic():
                    for other_id in others:
                        # A. Mover Inscripciones (evitando duplicados)
                        other_inscriptions = Inscripcion.objects.filter(equipo_id=other_id)
                        for ins in other_inscriptions:
                            if Inscripcion.objects.filter(equipo_id=canonical_id, torneo_id=ins.torneo_id).exists():
                                ins.delete()
                            else:
                                ins.equipo_id = canonical_id
                                ins.save()
                        
                        # B. Mover EquipoGrupo
                        other_egs = EquipoGrupo.objects.filter(equipo_id=other_id)
                        for eg in other_egs:
                            if EquipoGrupo.objects.filter(equipo_id=canonical_id, grupo_id=eg.grupo_id).exists():
                                eg.delete()
                            else:
                                eg.equipo_id = canonical_id
                                eg.save()
                                
                        # C. Actualizar referencias en Partidos
                        PartidoGrupo.objects.filter(equipo1_id=other_id).update(equipo1_id=canonical_id)
                        PartidoGrupo.objects.filter(equipo2_id=other_id).update(equipo2_id=canonical_id)
                        PartidoGrupo.objects.filter(ganador_id=other_id).update(ganador_id=canonical_id)
                        
                        Partido.objects.filter(equipo1_id=other_id).update(equipo1_id=canonical_id)
                        Partido.objects.filter(equipo2_id=other_id).update(equipo2_id=canonical_id)
                        Partido.objects.filter(ganador_id=other_id).update(ganador_id=canonical_id)
                        
                        Torneo.objects.filter(ganador_del_torneo_id=other_id).update(ganador_del_torneo_id=canonical_id)
                        
                        # D. Elimar el registro de equipo extra
                        Equipo.objects.filter(id=other_id).delete()
                        merged_count += 1
                    
                    # Normalizar equipo canónico
                    canonical_team = Equipo.objects.get(id=canonical_id)
                    canonical_team.save()

        self.stdout.write(f"Se han fusionado {merged_count} registros de equipo duplicados.")

        self.stdout.write("\n--- Normalizando todos los equipos restantes ---")
        for team in Equipo.objects.filter(es_dummy=False):
            team.save()

        self.stdout.write("\n--- Recalculando Rankings para todas las Divisiones ---")
        for division in Division.objects.all():
            self.stdout.write(f"Recalculando {division.nombre}...")
            actualizar_rankings_en_bd(division)
        
        self.stdout.write(self.style.SUCCESS("\n--- ¡Reparación y Recalculación Completada con Éxito! ---"))
