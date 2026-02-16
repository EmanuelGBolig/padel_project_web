
import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'padel_project.settings')
django.setup()

from torneos.models import Torneo
from django.urls import reverse

print("--- Verifying SEO Configuration ---")

# 1. Check App Installed
from django.conf import settings
if 'django.contrib.sitemaps' in settings.INSTALLED_APPS:
    print("✅ 'django.contrib.sitemaps' is installed.")
else:
    print("❌ 'django.contrib.sitemaps' is NOT installed.")

# 2. Check get_absolute_url
t = Torneo.objects.first()
if t:
    try:
        url = t.get_absolute_url()
        print(f"✅ Torneo.get_absolute_url() works: {url}")
    except Exception as e:
        print(f"❌ Torneo.get_absolute_url() failed: {e}")
else:
    print("⚠️ No tournaments found to test URL generation.")

# 3. Test Sitemap Generation
from django.contrib.sitemaps import Sitemap
from padel_project.sitemaps import TorneoSitemap

try:
    sitemap = TorneoSitemap()
    items = sitemap.items()
    print(f"✅ Sitemap items count: {items.count()}")
    if items.exists():
         print(f"   Sample item: {items.first()}")
         print(f"   Sample location: {sitemap.location(items.first())}")
except Exception as e:
    print(f"❌ Sitemap generation failed: {e}")
