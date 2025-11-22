import os
import sys
import django

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model

def create_superuser():
    User = get_user_model()
    
    # Valores por defecto o desde variables de entorno
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'emanuel')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'egomezbolig@gmail.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'emanuel2001')
    
    print("--- Verificando Superusuario ---")
    
    if not User.objects.filter(email=email).exists():
        print(f"  Creando superusuario: {email}")
        try:
            # Usamos create_superuser del manager
            user = User.objects.create_superuser(
                email=email,
                password=password,
                nombre='Admin',
                apellido='System'
            )
            print(f"  [+] Superusuario creado exitosamente.")
            print(f"  Email: {email}")
            print(f"  Password: {password}")
        except Exception as e:
            print(f"  [!] Error creando superusuario: {e}")
    else:
        print(f"  [ ] El superusuario {email} ya existe.")

if __name__ == "__main__":
    create_superuser()
