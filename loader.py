import os
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
os.environ['DATABASE_URL'] = "postgresql://postgres.fpzdvjcypvpmuamyazhs:iZ-%zJsm3U3xUPW@aws-1-us-east-1.pooler.supabase.com:6543/postgres"

django.setup()

def load_data():
    try:
        call_command('loaddata', 'backup_render_final.json', verbosity=2)
        print("Data loaded perfectly.")
    except Exception as e:
        print(f"Error loading: {e}")

if __name__ == '__main__':
    load_data()
