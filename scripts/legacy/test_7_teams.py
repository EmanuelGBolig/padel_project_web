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
    print("=== TEST TORNEO 7 PAREJAS ===")
    
    # 1. Preparar Datos
    div_name = "TestDiv7"
    div, _ = Division.objects.get_or_create(nombre=div_name)
    
    # Limpiar datos anteriores de prueba
    print("Limpiando datos anteriores...")
    Torneo.objects.filter(nombre="Torneo Test 7").delete()
    User.objects.filter(email__startswith="test7_").delete()
    
    # Crear Torneo
    torneo = Torneo.objects.create(
        nombre="Torneo Test 7",
        division=div,
        fecha_inicio=timezone.now().date(),
        fecha_limite_inscripcion=timezone.now() + timedelta(days=7),
        cupos_totales=7,
        estado=Torneo.Estado.ABIERTO
    )
    print(f"Torneo creado: {torneo}")

    # Crear 7 Equipos e Inscribirlos
    print("Creando 7 equipos...")
    equipos = []
    for i in range(7):
        suffix = random.randint(1000, 9999)
        u1 = User.objects.create_user(
            email=f"test7_u{i}a_{suffix}@example.com", 
            nombre=f"Jugador{i}A", 
            apellido=f"T7_{i}A", 
            division=div, 
            password="pass"
        )
        u2 = User.objects.create_user(
            email=f"test7_u{i}b_{suffix}@example.com", 
            nombre=f"Jugador{i}B", 
            apellido=f"T7_{i}B", 
            division=div, 
            password="pass"
        )
        eq = Equipo.objects.create(jugador1=u1, jugador2=u2, division=div)
        equipos.append(eq)
        Inscripcion.objects.create(torneo=torneo, equipo=eq)
    
    print(f"Inscritos: {torneo.inscripciones.count()} equipos.")

    # 2. Iniciar Torneo (Generar Grupos)
    print("\n--- INICIANDO TORNEO (Generación de Grupos) ---")
    
    fmt = get_format(7)
    if not fmt:
        print("ERROR: No se encontró formato para 7 equipos.")
        return

    print(f"Formato detectado: {fmt.groups} grupos. Tamaños: {fmt.teams_per_group}")
    
    # Simular lógica de views.py
    letras = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
    sizes = fmt.teams_per_group # [4, 3]
    
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
    print("Ahora puedes ir al panel de administración y generar el bracket.")
    print("Recuerda: El bracket de 7 equipos es asimétrico.")

if __name__ == "__main__":
    run_test()
