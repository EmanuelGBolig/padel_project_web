"""Backend de autenticación para cuentas fusionadas (TP-20, etapa 2).

Permite entrar con CUALQUIERA de los mails de una persona cuyas cuentas se
unificaron. La cuenta absorbida (`merged_into` seteado, desactivada) sigue
guardando su email; al intentar entrar con ese mail, se resuelve a la cuenta
canónica y se valida contra la contraseña de la canónica.

Modelo mental: "todos tus mails abren tu cuenta principal, con la contraseña
de tu cuenta principal".
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model


def resolver_canonica(user, _profundidad=0):
    """Sigue la cadena merged_into hasta la cuenta canónica (con tope anti-ciclos)."""
    visto = set()
    actual = user
    while actual.merged_into_id and actual.merged_into_id not in visto and _profundidad < 10:
        visto.add(actual.id)
        actual = actual.merged_into
        _profundidad += 1
    return actual


class MergedAccountBackend(ModelBackend):
    """Resuelve el login de un mail de cuenta fusionada hacia su cuenta canónica.

    Para cuentas normales (activas, sin fusionar) devuelve None y deja que el
    ModelBackend estándar haga su trabajo.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        email = username or kwargs.get(User.USERNAME_FIELD)
        if not email or password is None:
            return None

        try:
            user = User.objects.get(email__iexact=email)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

        # Solo nos ocupamos de cuentas fusionadas; el resto lo maneja ModelBackend.
        if not user.merged_into_id:
            return None

        canonica = resolver_canonica(user)
        if canonica.pk == user.pk:
            return None  # cadena rota; no hay canónica distinta

        # Validamos contra la contraseña de la cuenta canónica.
        if canonica.check_password(password) and self.user_can_authenticate(canonica):
            return canonica
        return None
