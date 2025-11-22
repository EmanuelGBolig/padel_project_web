from django.apps import AppConfig


class TorneosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'torneos'

    def ready(self):
        import torneos.signals
