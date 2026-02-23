"""
Pipeline personalizado para social-auth-app-django (Google OAuth2).
Guarda el nombre/apellido de Google en el CustomUser,
y redirige al usuario a completar perfil si le faltan datos.
"""
from django.shortcuts import redirect


def save_google_profile(backend, user, response, *args, **kwargs):
    """
    Paso 1: Guarda nombre y apellido desde el perfil de Google si el usuario
    todavía no los tiene (usuario nuevo), y lo marca como verificado.
    """
    if backend.name == 'google-oauth2':
        # Marcar como verificado (Google ya confirmó el email)
        if not user.is_verified:
            user.is_verified = True

        # Asignar nombre desde Google si el campo está vacío
        if not user.nombre:
            user.nombre = response.get('given_name', '')

        # Asignar apellido desde Google si el campo está vacío
        if not user.apellido:
            user.apellido = response.get('family_name', '')

        user.save()


def require_profile_completion(backend, user, *args, **kwargs):
    """
    Paso 2: Si al usuario le faltan campos obligatorios (división, género,
    teléfono), interrumpir el pipeline y redirigir al formulario de
    completar perfil.
    """
    fields_missing = (
        not user.division_id or
        not user.numero_telefono
    )

    if fields_missing:
        return redirect('/accounts/completar-perfil/')
