"""
Pipeline personalizado para social-auth-app-django (Google OAuth2).
Guarda el nombre/apellido de Google en el CustomUser y lo marca como verificado.

IMPORTANTE: No hacer redirects desde el pipeline. En este punto el usuario aún no
está autenticado en la sesión de Django. Los usuarios nuevos se redirigen via
SOCIAL_AUTH_NEW_USER_REDIRECT_URL en settings.py, una vez completado el login.
"""


import requests
from django.core.files.base import ContentFile

def save_google_profile(backend, user, response, is_new=False, *args, **kwargs):
    """
    Guarda nombre, apellido y foto desde el perfil de Google si el usuario
    todavía no los tiene, y lo marca como verificado.
    """
    if backend.name == 'google-oauth2':
        changed = False

        # Marcar como verificado (Google ya confirmó el email)
        if not user.is_verified:
            user.is_verified = True
            changed = True

        # Asignar nombre desde Google si el campo está vacío
        if not user.nombre:
            user.nombre = response.get('given_name', '')
            changed = True

        # Asignar apellido desde Google si el campo está vacío
        if not user.apellido:
            user.apellido = response.get('family_name', '')
            changed = True

        # Asignar foto desde Google si no tiene una
        if not user.imagen:
            picture_url = response.get('picture')
            if picture_url:
                try:
                    resp = requests.get(picture_url, timeout=10)
                    if resp.status_code == 200:
                        # Usamos la extensión según el Content-Type o default .jpg
                        ext = 'jpg'
                        if 'image/png' in resp.headers.get('Content-Type', ''):
                            ext = 'png'
                        
                        file_name = f"google_profile_{user.pk}.{ext}"
                        user.imagen.save(file_name, ContentFile(resp.content), save=False)
                        changed = True
                except Exception as e:
                    # No bloqueamos el login si falla la foto, solo lo reportamos
                    print(f"Error al guardar foto de Google para {user.email}: {e}")

        if changed:
            user.save()
