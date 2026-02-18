from django.contrib import admin
from .models import Division, Equipo





@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'jugador1', 'jugador2', 'division', 'fecha_creacion')
    list_filter = ('division',)
    search_fields = ('nombre', 'jugador1__email', 'jugador2__email')
    raw_id_fields = ('jugador1', 'jugador2')  # Para búsqueda de usuarios

    def get_readonly_fields(self, request, obj=None):
        # Hacer 'nombre' y 'division' solo lectura en el admin
        if obj:  # obj is not None, so this is an edit
            return ['nombre', 'division']
        return []
