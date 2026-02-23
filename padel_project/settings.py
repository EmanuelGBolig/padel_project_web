"""
Django settings for padel_project project.
"""

import os
from pathlib import Path
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# --- Configuración de Despliegue (Render) ---
# SECRET_KEY se toma de las variables de entorno en producción
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-tu-secret-key-local')

# DEBUG es 'True' localmente, pero 'False' en producción
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# ALLOWED_HOSTS para Render
ALLOWED_HOSTS = []
RENDER_EXTERNAL_HOSTNAME = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CUSTOM_DOMAIN = os.environ.get('CUSTOM_DOMAIN')
if CUSTOM_DOMAIN:
    ALLOWED_HOSTS.append(CUSTOM_DOMAIN)
    # También permitir la versión www si no está ya incluida
    if not CUSTOM_DOMAIN.startswith('www.'):
        ALLOWED_HOSTS.append(f"www.{CUSTOM_DOMAIN}")

if not RENDER_EXTERNAL_HOSTNAME and not CUSTOM_DOMAIN:
    # Permitir local
    ALLOWED_HOSTS.append('127.0.0.1')
    ALLOWED_HOSTS.append('localhost')

# Confianza en el header de Render para HTTPS
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# Forzar HTTPS en redirects al estar en producción
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True


# Application definition
import platform

if platform.system() == 'Windows':
    NPM_BIN_PATH = r"C:\Program Files\nodejs\npm.cmd"
else:
    # En Render (Linux), npm suele estar en el PATH
    NPM_BIN_PATH = 'npm'

# settings.py

INSTALLED_APPS = [
    # --- Apps de Django ---
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.sitemaps',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',
    # --- Apps de terceros (¡AHORA ACTIVAS!) ---
    'theme',
    'tailwind',
    'crispy_forms',
    'crispy_tailwind',
    'dal',
    'dal_select2',
    "widget_tweaks",
    # --- Mis Apps (¡AHORA AÑADIDAS!) ---
    'core.apps.CoreConfig',
    'accounts.apps.AccountsConfig',
    'equipos.apps.EquiposConfig',
    'torneos.apps.TorneosConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Whitenoise
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'padel_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],  # Directorio de plantillas base
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'padel_project.context_processors.notifications', # Notificaciones Globales
            ],
        },
    },
]

WSGI_APPLICATION = 'padel_project.wsgi.application'


# --- Base de Datos ---
# Usa PostgreSQL en producción (Render) y SQLite localmente

if 'DATABASE_URL' in os.environ:
    DATABASES = {'default': dj_database_url.config(conn_max_age=600, ssl_require=True)}
else:
    # --- ¡ERROR CORREGIDO AQUÍ! ---
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'es-es'  # Español
TIME_ZONE = 'UTC'
USE_I18N = True  # <--- ¡CORREGIDO: DEBE SER I18N, NO I1N!
USE_TZ = True


# --- Cloudinary (Media Storage in Production) ---
# --- Cloudinary (Media Storage in Production) ---
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')

if CLOUDINARY_URL:
    # Strip quotes and whitespace that might be accidentally included
    CLOUDINARY_URL = CLOUDINARY_URL.strip().strip("'").strip('"')
    
    # Production: Use Cloudinary
    INSTALLED_APPS.append('cloudinary_storage')
    INSTALLED_APPS.append('cloudinary')
    
    # Parse CLOUDINARY_URL: cloudinary://<api_key>:<api_secret>@<cloud_name>
    import re
    match = re.match(r'cloudinary://([^:]+):([^@]+)@(.+)', CLOUDINARY_URL)
    if match:
        api_key, api_secret, cloud_name = match.groups()
        
        CLOUDINARY_STORAGE = {
            'CLOUD_NAME': cloud_name,
            'API_KEY': api_key,
            'API_SECRET': api_secret,
        }
        print(f"✅ Cloudinary Configured for Cloud Name: {cloud_name}")
    else:
        print("❌ Cloudinary URL format invalid. Expected: cloudinary://<key>:<secret>@<cloud_name>")
        # Fallback if URL format is unexpected
        CLOUDINARY_STORAGE = {
            'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME'),
            'API_KEY': os.environ.get('CLOUDINARY_API_KEY'),
            'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET'),
        }
    
    
    # DEFAULT_FILE_STORAGE es obsoleto en Django 5, usamos STORAGES
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    print(f"✅ USING CLOUDINARY STORAGE (Django 5 STORAGES)")
else:
    print("⚠️ No CLOUDINARY_URL found. Using local filesystem storage.")
    # Local: Use filesystem
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
    print(f"✅ USING LOCAL STORAGE (MEDIA_ROOT: {MEDIA_ROOT})")


# --- Cache Configuration ---
# DatabaseCache: shared across all Gunicorn workers (LocMemCache is per-process)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
        'TIMEOUT': 300,  # 5 minutos por defecto
        'OPTIONS': {
            'MAX_ENTRIES': 1000,
        }
    }
}


# --- Archivos Estáticos (Static files) ---
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = '/static/'
# Directorio donde `collectstatic` pondrá los archivos para producción
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Configuración de Whitenoise (Ya manejada en STORAGES)
# STATICFILES_STORAGE eliminado por obsoleto en Django 5

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Modelo de Usuario Personalizado (¡AHORA ACTIVO!) ---
AUTH_USER_MODEL = 'accounts.CustomUser'

# --- URLs de Autenticación ---
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:home'
LOGOUT_REDIRECT_URL = 'core:home'

# --- Configuración de Tailwind y Crispy Forms ---
TAILWIND_APP_NAME = 'theme'
INTERNAL_IPS = [
    "127.0.0.1",
]
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

#--- Logging Configuration ---
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}


# --- Email Configuration ---
if DEBUG:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
else:
    # Configuración para producción (Resend API Custom)
    EMAIL_BACKEND = 'accounts.resend_backend.ResendBackend'
    RESEND_API_KEY = os.environ.get('RESEND_API_KEY')
    
    # Gmail fuerza que el sender sea la cuenta autenticada, con Resend usamos el verificado
    # Asegúrate de verificar el dominio o email en Resend
    if CUSTOM_DOMAIN:
        DEFAULT_FROM_EMAIL = f'noreply@{CUSTOM_DOMAIN}'
    else:
        # Fallback de seguridad para producción: usamos el dominio verificado
        DEFAULT_FROM_EMAIL = 'noreply@todopadel.club'
