"""
Django management command para simular un torneo de 24 equipos con grupos de 3.
Uso: python manage.py simular_torneo_24
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random

from torneos.models import Torneo, Inscripcion, Grupo, EquipoGrupo, PartidoGrupo, Partido
from equipos.models import Equipo
from accounts.models import Division
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Simula un torneo completo de 24 equipos con grupos de 3, genera bracket y simula resultados'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Iniciando Simulación de Torneo de 24 Equipos ---'))

        # 1. Crear División si no existe
        division, _ = Division.objects.get_or_create(nombre="Séptima")
        
        # 2. Crear Torneo
        torneo_nombre = f"Torneo 24 Equipos - {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        torneo = Torneo.objects.create(
            nombre=torneo_nombre,
            division=division,
            fecha_inicio=timezone.now().date(),
            fecha_limite_inscripcion=timezone.now() + timedelta(hours=1),
            cupos_totales=24,
            equipos_por_grupo=3,  # Grupos de 3
            estado=Torneo.Estado.ABIERTO
        )
        self.stdout.write(f"✓ Torneo creado: {torneo.nombre} (ID: {torneo.id})")

        # 3. Limpiar datos de simulaciones anteriores
        self.stdout.write("Limpiando datos de simulaciones anteriores...")
        User.objects.filter(email__contains='@ejemplo.com').delete()
        
        # 4. Crear equipos e inscribirlos
        equipos_inscritos = []
        for i in range(1, 25):
            # Crear jugadores si no existen
            email1 = f"jugador{i}a@ejemplo.com"
            email2 = f"jugador{i}b@ejemplo.com"
            
            jugador1, _ = User.objects.get_or_create(
                email=email1,
                defaults={
                    'nombre': f'Jugador{i}A',
                    'apellido': 'Simulado',
                    'division': division,
                    'tipo_usuario': 'PLAYER',
                    'password': 'pbkdf2_sha256$600000$dummy$dummy'
                }
            )
            
            jugador2, _ = User.objects.get_or_create(
                email=email2,
                defaults={
                    'nombre': f'Jugador{i}B',
                    'apellido': 'Simulado',
                    'division': division,
                    'tipo_usuario': 'PLAYER',
                    'password': 'pbkdf2_sha256$600000$dummy$dummy'
                }
            )
            
            # Crear equipo (nombre se genera automáticamente)
            # Intentar obtener equipo existente primero
            try:
                equipo = Equipo.objects.get(jugador1=jugador1, jugador2=jugador2)
                created = False
            except Equipo.DoesNotExist:
                equipo = Equipo.objects.create(
                    jugador1=jugador1,
                    jugador2=jugador2,
                    division=division
                )
                created = True
            
            # Inscribir en torneo
            Inscripcion.objects.get_or_create(
                torneo=torneo,
                equipo=equipo
            )
            equipos_inscritos.append(equipo)
        
        self.stdout.write(f"✓ {len(equipos_inscritos)} equipos creados e inscritos")

        # 4. Iniciar torneo (crear grupos)
        torneo.estado = Torneo.Estado.EN_JUEGO
        torneo.save()
        
        # Mezclar equipos
        random.shuffle(equipos_inscritos)
        
        # Crear 8 grupos de 3 equipos
        num_grupos = 8
        letras = 'ABCDEFGH'
        
        for i in range(num_grupos):
            grupo = Grupo.objects.create(
                torneo=torneo,
                nombre=f"Grupo {letras[i]}"
            )
            
            # Asignar 3 equipos al grupo
            for j in range(3):
                idx = i * 3 + j
                equipo = equipos_inscritos[idx]
                EquipoGrupo.objects.create(
                    grupo=grupo,
                    equipo=equipo,
                    numero=j + 1
                )
            
            # Crear partidos (todos contra todos = 3 partidos por grupo)
            equipos_grupo = list(grupo.tabla.values_list('equipo', flat=True))
            equipos_obj = Equipo.objects.filter(id__in=equipos_grupo)
            
            # Partidos: 1vs2, 1vs3, 2vs3
            pairs = [(0, 1), (0, 2), (1, 2)]
            for pair in pairs:
                PartidoGrupo.objects.create(
                    grupo=grupo,
                    equipo1=equipos_obj[pair[0]],
                    equipo2=equipos_obj[pair[1]]
                )
        
        self.stdout.write(f"✓ {num_grupos} grupos de 3 equipos creados")

        # 5. Simular resultados de fase de grupos
        partidos_grupo = PartidoGrupo.objects.filter(grupo__torneo=torneo)
        for partido in partidos_grupo:
            # Simular resultado aleatorio (2 sets para ganar)
            # Set 1
            partido.e1_set1 = random.choice([6, 7])
            partido.e2_set1 = random.choice([0, 1, 2, 3, 4, 5, 6]) if partido.e1_set1 == 6 else random.choice([5, 6])
            
            # Decidir si hay set 2 y quién gana
            if random.random() > 0.5:  # Equipo 1 gana 2-0
                partido.e1_set2 = random.choice([6, 7])
                partido.e2_set2 = random.choice([0, 1, 2, 3, 4, 5, 6]) if partido.e1_set2 == 6 else random.choice([5, 6])
                partido.ganador = partido.equipo1
            else:  # Equipo 1 pierde el set 2, puede ganar o perder el set 3
                partido.e1_set2 = random.choice([0, 1, 2, 3, 4, 5, 6])
                partido.e2_set2 = random.choice([6, 7])
                
                # Set 3 (desempate)
                if random.random() > 0.5:
                    partido.e1_set3 = random.choice([6, 7])
                    partido.e2_set3 = random.choice([0, 1, 2, 3, 4, 5, 6]) if partido.e1_set3 == 6 else random.choice([5, 6])
                    partido.ganador = partido.equipo1
                else:
                    partido.e1_set3 = random.choice([0, 1, 2, 3, 4, 5, 6])
                    partido.e2_set3 = random.choice([6, 7])
                    partido.ganador = partido.equipo2
            
            partido.save()
        
        self.stdout.write(f"✓ {partidos_grupo.count()} partidos de grupos simulados")

        # 6. Generar bracket (16vos con 16 clasificados)
        clasificados = []
        for grupo in Grupo.objects.filter(torneo=torneo).order_by('nombre'):
            tabla = grupo.tabla.all()[:2]  # Top 2 de cada grupo
            for pos in tabla:
                clasificados.append(pos.equipo)
        
        self.stdout.write(f"✓ {len(clasificados)} equipos clasificados para eliminatorias")

        # Crear bracket de 16
        bracket_size = 16
        ronda_inicio = "16vos"
        
        # Crear partidos de 16vos
        partidos_creados = []
        for i in range(8):
            partido = Partido.objects.create(
                torneo=torneo,
                ronda=ronda_inicio,
                orden_partido=i + 1,
                equipo1=clasificados[i * 2],
                equipo2=clasificados[i * 2 + 1]
            )
            partidos_creados.append(partido)
            
            # Simular resultado
            ganador = random.choice([partido.equipo1, partido.equipo2])
            partido.ganador = ganador
            partido.resultado = "2-0" if random.random() > 0.5 else "2-1"
            partido.save()
        
        self.stdout.write(f"✓ {len(partidos_creados)} partidos de 16vos creados y simulados")

        # 7. Crear y simular Cuartos de Final
        ganadores_16vos = [p.ganador for p in partidos_creados]
        partidos_cuartos = []
        for i in range(4):
            partido = Partido.objects.create(
                torneo=torneo,
                ronda="Cuartos",
                orden_partido=i + 1,
                equipo1=ganadores_16vos[i * 2],
                equipo2=ganadores_16vos[i * 2 + 1]
            )
            ganador = random.choice([partido.equipo1, partido.equipo2])
            partido.ganador = ganador
            partido.resultado = "2-0" if random.random() > 0.5 else "2-1"
            partido.save()
            partidos_cuartos.append(partido)
        
        self.stdout.write(f"✓ Cuartos de final simulados")

        # 8. Crear y simular Semifinales
        ganadores_cuartos = [p.ganador for p in partidos_cuartos]
        partidos_semis = []
        for i in range(2):
            partido = Partido.objects.create(
                torneo=torneo,
                ronda="Semifinal",
                orden_partido=i + 1,
                equipo1=ganadores_cuartos[i * 2],
                equipo2=ganadores_cuartos[i * 2 + 1]
            )
            ganador = random.choice([partido.equipo1, partido.equipo2])
            partido.ganador = ganador
            partido.resultado = "2-1"
            partido.save()
            partidos_semis.append(partido)
        
        self.stdout.write(f"✓ Semifinales simuladas")

        # 9. Crear y simular Final
        ganadores_semis = [p.ganador for p in partidos_semis]
        partido_final = Partido.objects.create(
            torneo=torneo,
            ronda="Final",
            orden_partido=1,
            equipo1=ganadores_semis[0],
            equipo2=ganadores_semis[1]
        )
        ganador_final = random.choice([partido_final.equipo1, partido_final.equipo2])
        partido_final.ganador = ganador_final
        partido_final.resultado = "2-1"
        partido_final.save()
        
        self.stdout.write(self.style.SUCCESS(f"✓ Final simulada"))
        self.stdout.write(self.style.SUCCESS(f"\n🏆 CAMPEÓN: {ganador_final.nombre}"))
        
        # 10. Finalizar torneo
        torneo.estado = Torneo.Estado.FINALIZADO
        torneo.save()
        
        self.stdout.write(self.style.SUCCESS(f"\n✅ Simulación completa!"))
        self.stdout.write(f"URL: /torneos/{torneo.id}/")
