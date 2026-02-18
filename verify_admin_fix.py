import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from accounts.forms import CustomUserCreationForm
from accounts.admin import CustomUserAdmin
from django.contrib.admin import AdminSite

from accounts.models import CustomUser

form = CustomUserCreationForm()
form_fields = set(form.fields.keys())

# Extract fields from add_fieldsets
admin = CustomUserAdmin(model=CustomUser, admin_site=AdminSite())
admin_add_fields = []
for title, data in admin.add_fieldsets:
    admin_add_fields.extend(data.get('fields', []))

print(f"Form fields: {form_fields}")
print(f"Admin add_fieldsets fields: {admin_add_fields}")

missing_in_form = [f for f in admin_add_fields if f not in form_fields]
if missing_in_form:
    print(f"FAILURE: Fields missing in form: {missing_in_form}")
else:
    print("SUCCESS: All fields in admin.add_fieldsets are present in the form.")
