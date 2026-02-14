import socket
from django.core.mail.backends.smtp import EmailBackend
import threading

class IPv4EmailBackend(EmailBackend):
    def open(self):
        # Guardamos la referencia original
        original_getaddrinfo = socket.getaddrinfo

        # Definimos el wrapper que fuerza AF_INET
        def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            # Si el host es el de nuestro SMTP, forzamos IPv4
            # Esto evita afectar otras conexiones (DB, etc) si es posible
            if host == self.host:
                print(f"--- Forzando IPv4 para {host} ---")
                res = original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
                print(f"--- IPs resueltas: {res} ---")
                return res
            return original_getaddrinfo(host, port, family, type, proto, flags)

        # Aplicamos el patch
        socket.getaddrinfo = ipv4_getaddrinfo
        try:
            return super().open()
        except Exception as e:
            print(f"!!! Error en IPv4Backend open: {e}")
            raise e
        finally:
            # Restauramos SIEMPRE
            socket.getaddrinfo = original_getaddrinfo
