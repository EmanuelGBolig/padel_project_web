
import os
import django
import sys
from django.db.models import Count, Q

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser

print("--- Debugging View Annotation Logic ---")

# Finds a user with known wins (based on previous debug)
# Replace with a user ID you know has wins, or query for one
# From previous output, we saw a winner. Let's find a user with > 0 wins manually
users = CustomUser.objects.all()
target_user = None
for u in users:
    w1 = u.equipos_como_jugador1.filter(partidos_bracket_ganados__isnull=False).count()
    w2 = u.equipos_como_jugador2.filter(partidos_bracket_ganados__isnull=False).count()
    if w1 + w2 > 0:
        target_user = u
        break

if target_user:
    print(f"Testing User: {target_user.email} (ID: {target_user.id})")
    
    # Replicate the Annotation from accounts/views.py
    qs = CustomUser.objects.filter(id=target_user.id).annotate(
        # Victorias como jugador1 en partidos de eliminación
        victorias_j1_elim=Count(
            'equipos_como_jugador1__partidos_bracket_ganados',
            filter=Q(equipos_como_jugador1__partidos_bracket_ganados__isnull=False),
            distinct=True
        ),
        # Victorias como jugador2 en partidos de eliminación
        victorias_j2_elim=Count(
            'equipos_como_jugador2__partidos_bracket_ganados',
            filter=Q(equipos_como_jugador2__partidos_bracket_ganados__isnull=False),
            distinct=True
        )
    )
    
    data = qs.first()
    print(f"Annotated Victories J1: {data.victorias_j1_elim}")
    print(f"Annotated Victories J2: {data.victorias_j2_elim}")
    
    # Manual Check
    manual_j1 = target_user.equipos_como_jugador1.aggregate(
        total=Count('partidos_bracket_ganados', filter=Q(partidos_bracket_ganados__isnull=False))
    )['total']
    manual_j2 = target_user.equipos_como_jugador2.aggregate(
        total=Count('partidos_bracket_ganados', filter=Q(partidos_bracket_ganados__isnull=False))
    )['total']
    
    print(f"Manual Victories J1: {manual_j1}")
    print(f"Manual Victories J2: {manual_j2}")
    
    if data.victorias_j1_elim != manual_j1 or data.victorias_j2_elim != manual_j2:
        print("MISMATCH DETECTED in Annotation vs Manual Aggregation!")
    else:
        print("Match confirmed. The logic seems consistent with DB state.")

else:
    print("No user with wins found to test.")
