from django.apps import AppConfig


class EquiposConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'equipos'
    
    def ready(self):
        import equipos.signals  # noqa
