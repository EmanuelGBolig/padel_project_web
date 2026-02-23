"""
Pipeline personalizado para social-auth-app-django (Google OAuth2).
Guarda el nombre/apellido de Google en el CustomUser y lo marca como verificado.

IMPORTANTE: No hacer redirects desde el pipeline. En este punto el usuario aún no
está autenticado en la sesión de Django. Los usuarios nuevos se redirigen via
SOCIAL_AUTH_NEW_USER_REDIRECT_URL en settings.py, una vez completado el login.
"""


def save_google_profile(backend, user, response, is_new=False, *args, **kwargs):
    """
    Guarda nombre y apellido desde el perfil de Google si el usuario
    todavía no los tiene (usuario nuevo), y lo marca como verificado.
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

        if changed:
            user.save()
