import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division, CustomUser
from equipos.models import RankingJugador

with open('divisions_debug.txt', 'w', encoding='utf-8') as f:
    f.write("All Divisions in DB:\n")
    for d in Division.objects.all().order_by('id'):
        p_count = CustomUser.objects.filter(division=d, tipo_usuario='PLAYER').count()
        r_count = RankingJugador.objects.filter(division=d).count()
        f.write(f"- ID: {d.id}, Nombre: '{d.nombre}', Jugadores: {p_count}, Rankings: {r_count}, Orden: {d.orden}\n")
    
    f.write("\nSexta (ID: 6) Players (if exists):\n")
    sexta_6 = Division.objects.filter(id=6).first()
    if sexta_6:
        f.write(f"Division 6 name: '{sexta_6.nombre}'\n")
        players = CustomUser.objects.filter(division=sexta_6, tipo_usuario='PLAYER')
        for p in players[:5]:
            f.write(f"  - {p.email} ({p.full_name})\n")
    
    f.write("\nSexta (ID: 1) Players (if exists):\n")
    sexta_1 = Division.objects.filter(id=1).first()
    if sexta_1:
         f.write(f"Division 1 name: '{sexta_1.nombre}'\n")
         players = CustomUser.objects.filter(division=sexta_1, tipo_usuario='PLAYER')
         for p in players[:5]:
             f.write(f"  - {p.email} ({p.full_name})\n")
