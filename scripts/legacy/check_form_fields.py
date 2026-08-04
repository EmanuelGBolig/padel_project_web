import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.forms import CustomUserCreationForm

form = CustomUserCreationForm()
print("Fields in CustomUserCreationForm:")
for field in form.fields:
    print(f"- {field}")
