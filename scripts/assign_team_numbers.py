#!/usr/bin/env python
import os
import sys
import django

# Add parent directory to sys.path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo, EquipoGrupo

torneo_id = 6

try:
    torneo = Torneo.objects.get(pk=torneo_id)
    print(f"Actualizando torneo: {torneo.nombre}")
    
    grupos = torneo.grupos.all()
    for grupo in grupos:
        print(f"  Procesando {grupo.nombre}...")
        equipos_grupo = EquipoGrupo.objects.filter(grupo=grupo).order_by('id')
        
        for idx, eg in enumerate(equipos_grupo, start=1):
            eg.numero = idx
            eg.save()
            print(f"    - Asignado {eg.numero} a {eg.equipo.nombre}")
            
    print("\n✓ Actualización completada con éxito.")

except Torneo.DoesNotExist:
    print(f"✗ No se encontró el torneo con ID {torneo_id}")
except Exception as e:
    print(f"✗ Error: {e}")
