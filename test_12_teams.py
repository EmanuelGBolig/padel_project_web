import os
import django
from django.utils import timezone
from datetime import timedelta
import random

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from accounts.models import Division
from equipos.models import Equipo
from torneos.models import Torneo, Inscripcion, Grupo, Partido, EquipoGrupo
from torneos.views import generar_partidos_grupos
from torneos.formats import get_format

User = get_user_model()

def run_test():
    print("=== TEST TORNEO 12 PAREJAS ===")
    
    # 1. Preparar Datos
    div_name = "TestDiv12"
    div, _ = Division.objects.get_or_create(nombre=div_name)
    
    # Limpiar datos anteriores de prueba
    print("Limpiando datos anteriores...")
    Torneo.objects.filter(nombre="Torneo Test 12").delete()
    User.objects.filter(email__startswith="test12_").delete()
    
    # Crear Torneo
    torneo = Torneo.objects.create(
        nombre="Torneo Test 12",
        division=div,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=7),
        cupos_totales=12,
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Torneo creado: {torneo}")

    # Crear 12 Equipos e Inscribirlos
    print("Creando 12 equipos...")
    equipos = []
    for i in range(12):
        # Usamos un sufijo aleatorio para evitar colisiones si el script falla a medias
        suffix = random.randint(1000, 9999)
        u1 = User.objects.create_user(
            email=f"test12_u{i}a_{suffix}@example.com", 
            nombre=f"Jugador{i}A", 
            apellido=f"Test{i}A", 
            division=div, 
            password="pass"
        )
        u2 = User.objects.create_user(
            email=f"test12_u{i}b_{suffix}@example.com", 
            nombre=f"Jugador{i}B", 
            apellido=f"Test{i}B", 
            division=div, 
            password="pass"
        )
        eq = Equipo.objects.create(jugador1=u1, jugador2=u2, division=div)
        equipos.append(eq)
        Inscripcion.objects.create(torneo=torneo, equipo=eq)
    
    print(f"Inscritos: {torneo.inscripciones.count()} equipos.")

    # 2. Iniciar Torneo (Generar Grupos)
    print("\n--- INICIANDO TORNEO (Generación de Grupos) ---")
    
    # Simular lógica de la vista iniciar_torneo_logica
    fmt = get_format(12)
    if not fmt:
        print("ERROR: No se encontró formato para 12 equipos.")
        return

    print(f"Formato detectado: {fmt.groups} grupos de {fmt.teams_per_group}")
    
    letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    sizes = [fmt.teams_per_group] * fmt.groups
    
    current_team_idx = 0
    grupos_creados = []
    
    for i in range(fmt.groups):
        group_size = sizes[i]
        grupo = Grupo.objects.create(torneo=torneo, nombre=f"Zona {letras[i]}")
        grupos_creados.append(grupo)
        
        equipos_del_grupo = []
        for _ in range(group_size):
            equipos_del_grupo.append(equipos[current_team_idx])
            current_team_idx += 1
            
        for idx, eq in enumerate(equipos_del_grupo, start=1):
            EquipoGrupo.objects.create(grupo=grupo, equipo=eq, numero=idx)
            
        generar_partidos_grupos(torneo, equipos_del_grupo, grupo)
        print(f"  > {grupo.nombre} creado con {len(equipos_del_grupo)} equipos.")

    torneo.estado = Torneo.Estado.EN_JUEGO
    torneo.save()

    print("\n=== TORNEO CREADO EXITOSAMENTE ===")
    print(f"ID del Torneo: {torneo.pk}")
    print("Ahora puedes ir al panel de administración, cargar los resultados de los grupos y luego generar el bracket manualmente.")

if __name__ == "__main__":
    run_test()
