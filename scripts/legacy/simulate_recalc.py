import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division, CustomUser
from accounts.utils import get_division_rankings

div = Division.objects.get(id=1) # Sexta
print(f"Recalculating for {div.nombre} (ID: {div.id})...")

data = get_division_rankings(div, force_recalc=True)
print(f"Result count: {len(data)}")

# Check if some known users are missing
all_players_ids = set(CustomUser.objects.filter(division=div, tipo_usuario='PLAYER').values_list('id', flat=True))
data_player_ids = set(item['jugador'].id for item in data)

missing = all_players_ids - data_player_ids
print(f"Players in div but missing in ranking result: {len(missing)}")
if missing:
    print(f"First 5 missing IDs: {list(missing)[:5]}")

# Why are they missing?
if missing:
    first_missing = CustomUser.objects.get(id=list(missing)[0])
    print(f"Debug first missing: {first_missing.email}, Division: {first_missing.division}")
