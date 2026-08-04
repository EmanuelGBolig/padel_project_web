import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.models import CustomUser
from django.core.management import call_command

print(f"Checking CustomUser.division field...")
field = CustomUser._meta.get_field('division')
print(f"Field null: {field.null}")
print(f"Field blank: {field.blank}")

print("\nChecking for pending migrations...")
try:
    call_command('makemigrations', 'accounts', dry_run=True)
except Exception as e:
    print(f"Error checking migrations: {e}")
