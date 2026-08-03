"""Crea el superusuario inicial de una instalación nueva.

Uso manual (NO va en el build; ver build.sh):

    DJANGO_SUPERUSER_EMAIL=... DJANGO_SUPERUSER_PASSWORD=... python scripts/create_initial_superuser.py

Es idempotente: si el email ya existe, no toca nada. Nunca cambia la contraseña
de una cuenta existente.
"""
import os
import sys

import django

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.contrib.auth import get_user_model  # noqa: E402


def create_superuser():
    User = get_user_model()

    # Sin valores por defecto: una credencial hardcodeada en el repo es una
    # credencial publicada. Si falta el dato, el script no crea nada.
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')

    print("--- Verificando Superusuario ---")

    if not email or not password:
        print("  [!] Faltan DJANGO_SUPERUSER_EMAIL y/o DJANGO_SUPERUSER_PASSWORD.")
        print("      No se crea ningún usuario.")
        sys.exit(1)

    if User.objects.filter(email=email).exists():
        # Nunca pisamos la contraseña de una cuenta que ya existe.
        print(f"  [ ] El superusuario {email} ya existe. No se modifica.")
        return

    print(f"  Creando superusuario: {email}")
    try:
        User.objects.create_superuser(
            email=email,
            password=password,
            nombre='Admin',
            apellido='System',
        )
        # No imprimimos la contraseña: los logs de build quedan guardados.
        print("  [+] Superusuario creado exitosamente.")
    except Exception as e:
        print(f"  [!] Error creando superusuario: {e}")
        sys.exit(1)


if __name__ == "__main__":
    create_superuser()
