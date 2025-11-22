from django.contrib import admin
from .models import Torneo, Inscripcion, Partido, Grupo, PartidoGrupo, EquipoGrupo

# --- INLINES ---


class InscripcionInline(admin.TabularInline):
    model = Inscripcion
    extra = 0
    autocomplete_fields = ['equipo']  # Usamos autocomplete si hay muchos equipos
    readonly_fields = ('fecha_inscripcion',)


class EquipoGrupoInline(admin.TabularInline):
    """Muestra la tabla de posiciones dentro del detalle del Grupo"""

    model = EquipoGrupo
    extra = 0
    readonly_fields = (
        'partidos_jugados',
        'partidos_ganados',
        'partidos_perdidos',
        'sets_a_favor',
        'sets_en_contra',
        'games_a_favor',
        'games_en_contra',
        'diferencia_sets',
        'diferencia_games',
    )
    can_delete = False
    ordering = ('-partidos_ganados',)


class PartidoGrupoInline(admin.TabularInline):
    """Muestra los partidos del grupo dentro del detalle del Grupo"""

    model = PartidoGrupo
    extra = 0
    fields = ('equipo1', 'equipo2', 'ganador', 'e1_sets_ganados', 'e2_sets_ganados')
    readonly_fields = ('ganador', 'e1_sets_ganados', 'e2_sets_ganados')
    can_delete = False


# --- ADMINS PRINCIPALES ---


@admin.register(Torneo)
class TorneoAdmin(admin.ModelAdmin):
    list_display = (
        'nombre',
        'division',
        'estado',
        'tipo_torneo',
        'fecha_inicio',
        'cupos_totales',
    )
    list_filter = ('estado', 'tipo_torneo', 'division')
    search_fields = ('nombre',)
    inlines = [InscripcionInline]

    # Configuración de campos para el formulario
    fieldsets = (
        (
            'Información General',
            {'fields': ('nombre', 'division', 'estado', 'tipo_torneo')},
        ),
        (
            'Fechas y Cupos',
            {
                'fields': (
                    'fecha_inicio',
                    'fecha_limite_inscripcion',
                    'cupos_totales',
                    'equipos_por_grupo',
                )
            },
        ),
        ('Ganador', {'fields': ('ganador_del_torneo',)}),
    )


@admin.register(Grupo)
class GrupoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'torneo')
    list_filter = ('torneo',)
    inlines = [
        EquipoGrupoInline,
        PartidoGrupoInline,
    ]  # Ver tabla y partidos al entrar al grupo


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    """Admin para partidos de eliminación (Bracket)"""

    # Actualizado con los campos NUEVOS (equipo1, equipo2, ronda, etc.)
    list_display = ('__str__', 'torneo', 'ronda', 'ganador', 'resultado')
    list_filter = ('torneo', 'ronda')
    search_fields = ('equipo1__nombre', 'equipo2__nombre')

    # Usamos raw_id_fields para evitar cargar todos los equipos en el select
    # Actualizado: 'partido_siguiente' -> 'siguiente_partido'
    raw_id_fields = ('equipo1', 'equipo2', 'ganador', 'torneo', 'siguiente_partido')

    fieldsets = (
        (
            'Información',
            {'fields': ('torneo', 'ronda', 'orden_partido', 'siguiente_partido')},
        ),
        ('Enfrentamiento', {'fields': ('equipo1', 'equipo2')}),
        ('Resultado', {'fields': ('ganador', 'resultado')}),
    )


@admin.register(PartidoGrupo)
class PartidoGrupoAdmin(admin.ModelAdmin):
    """Admin para partidos de fase de grupos"""

    list_display = ('__str__', 'grupo', 'ganador')
    list_filter = ('grupo__torneo', 'grupo')
    search_fields = ('equipo1__nombre', 'equipo2__nombre')
    # Campos detallados de sets
    fieldsets = (
        ('Grupo', {'fields': ('grupo',)}),
        ('Equipos', {'fields': ('equipo1', 'equipo2')}),
        (
            'Resultados (Sets)',
            {
                'fields': (
                    ('e1_set1', 'e2_set1'),
                    ('e1_set2', 'e2_set2'),
                    ('e1_set3', 'e2_set3'),
                )
            },
        ),
        ('Totales', {'fields': ('ganador', 'e1_sets_ganados', 'e2_sets_ganados')}),
    )


# Registramos modelos simples
admin.site.register(Inscripcion)
admin.site.register(EquipoGrupo)  # Opcional, ya se ve dentro de Grupo
