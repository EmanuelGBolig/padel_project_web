import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division

print("=== All Divisions ===")
for div in Division.objects.all():
    print(f"ID: {div.id}, Name: '{div.nombre}'")

# Check for duplicates
names = [d.nombre for d in Division.objects.all()]
duplicates = set([n for n in names if names.count(n) > 1])
if duplicates:
    print(f"\n=== DUPLICATES FOUND ===")
    for dup in duplicates:
        print(f"- {dup}")
else:
    print("\nNo duplicates found")
