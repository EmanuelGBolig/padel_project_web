import os
import sys
import django

# Add parent directory to sys.path to allow importing project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import Division

def seed_divisions():
    print("--- Verificando Divisiones ---")
    
    divisiones_iniciales = [
        "Primera",
        "Segunda",
        "Tercera",
        "Cuarta",
        "Quinta",
        "Sexta",
        "Séptima",
        "Octava"
    ]
    
    creadas = 0
    for nombre in divisiones_iniciales:
        division, created = Division.objects.get_or_create(nombre=nombre)
        if created:
            print(f"  [+] Creada división: {nombre}")
            creadas += 1
        else:
            print(f"  [ ] Ya existe: {nombre}")
            
    print(f"\nProceso completado. Se crearon {creadas} nuevas divisiones.")
    print(f"Total de divisiones en base de datos: {Division.objects.count()}")

if __name__ == "__main__":
    seed_divisions()
