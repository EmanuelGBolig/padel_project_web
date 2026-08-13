"""Middlewares de cuentas."""
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse


class CambioDePasswordObligatorio:
    """Obliga a cambiar la contraseña automática antes de usar la app.

    Las cuentas que se crean al "anotarse sin cuenta" salen con una contraseña
    generada que se dicta por WhatsApp. Es cómoda para entrar la primera vez,
    pero viajó por un chat: hay que reemplazarla por una que elija la persona.

    Sin esto, la contraseña dictada quedaría vigente para siempre.
    """

    # Lo que sí puede usar sin haber cambiado la contraseña.
    LIBRES = (
        '/accounts/cambiar-password/',
        '/accounts/logout/',
        '/accounts/login/',
        '/static/',
        '/media/',
        '/sw.js',
        '/manifest.webmanifest',
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, 'user', None)

        if (usuario is not None
                and usuario.is_authenticated
                and getattr(usuario, 'debe_cambiar_password', False)
                and not request.path.startswith(self.LIBRES)):
            # Los pedidos de fondo (htmx, fetch) no se redirigen a una pantalla:
            # devolverían HTML donde se espera otra cosa.
            if request.headers.get('HX-Request') or request.headers.get(
                    'X-Requested-With') == 'XMLHttpRequest':
                return self.get_response(request)

            messages.info(
                request,
                "Elegí una contraseña tuya para terminar de activar la cuenta."
            )
            return redirect(reverse('accounts:cambiar_password'))

        return self.get_response(request)
