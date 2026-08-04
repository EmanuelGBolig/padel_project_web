import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
import traceback

c = Client()
User = get_user_model()

# We need a user who is a PLAYER (to pass PlayerRequiredMixin)
u = User.objects.filter(tipo_usuario='PLAYER').first()
if not u:
    print("NO PLAYER USER FOUND!")
else:
    c.force_login(u)
    # To catch exceptions directly during template rendering, we can set DEBUG = True temporarily
    from django.conf import settings
    settings.DEBUG = True

    try:
        res = c.get('/torneos/mis-torneos/')
        print("STATUS:", res.status_code)
        if res.status_code == 500:
            print("HTTP 500 Error encountered! Parsing traceback...")
            if res.context and hasattr(res.context, 'template'):
                print("Context:", res.context)
    except Exception as e:
        traceback.print_exc()
