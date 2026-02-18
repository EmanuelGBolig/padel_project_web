from django.db import models
from django.conf import settings
from django.db.models import F
from equipos.models import Equipo
from accounts.models import Division

# --- NO IMPORTAR .models AQUÍ ---


class Torneo(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = 'AB', 'Inscripción Abierta'
        EN_JUEGO = 'EJ', 'En Juego'
        FINALIZADO = 'FN', 'Finalizado'

    class TipoTorneo(models.TextChoices):
        ELIMINATORIA = 'E', 'Eliminación Directa'
        GRUPOS = 'G', 'Fase de Grupos + Eliminatoria'

    nombre = models.CharField(max_length=200)
    division = models.ForeignKey(
        Division, 
        on_delete=models.PROTECT,
        null=True,  # Permite torneos "libres" sin restricción de división
        blank=True,
        help_text="Dejar vacío para torneos libres (cualquier división)"
    )
    fecha_inicio = models.DateField()
    fecha_limite_inscripcion = models.DateTimeField()
    cupos_totales = models.PositiveIntegerField(default=16)

    # Campo para definir cuántos pasan por grupo a la siguiente fase (Si no hay formato manual)
    # Por defecto, el sistema intentará grupos de 3 o 4 según el total de inscritos.
    equipos_por_grupo = models.PositiveIntegerField(default=3)

    forzar_grupos_de_3 = models.BooleanField(
        default=False,
        help_text="Si se activa, el sistema exigirá que el total de equipos sea divisible por 3."
    )

    estado = models.CharField(
        max_length=2, choices=Estado.choices, default=Estado.ABIERTO
    )
    tipo_torneo = models.CharField(
        max_length=1, choices=TipoTorneo.choices, default=TipoTorneo.GRUPOS
    )
    
    class Categoria(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO = 'F', 'Femenino'
        MIXTO = 'X', 'Mixto'

    categoria = models.CharField(
        max_length=1, 
        choices=Categoria.choices, 
        default=Categoria.MIXTO,
        help_text="Categoría del torneo (Masculino, Femenino, Mixto)"
    )

    ganador_del_torneo = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="torneos_ganados",
    )
    
    organizacion = models.ForeignKey(
        'accounts.Organizacion',
        on_delete=models.CASCADE,
        related_name="torneos",
        null=True,
        blank=True
    )

    # Relación inversa para acceder a inscripciones fácilmente
    equipos_inscritos = models.ManyToManyField(
        Equipo, through='Inscripcion', related_name='torneos_participados'
    )

    def __str__(self):
        division_nombre = self.division.nombre if self.division else "Libre/General"
        return f"{self.nombre} ({division_nombre})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('torneos:detail', kwargs={'pk': self.pk})


class Inscripcion(models.Model):
    equipo = models.ForeignKey(
        Equipo, on_delete=models.CASCADE, related_name='inscripciones'
    )
    torneo = models.ForeignKey(
        Torneo, on_delete=models.CASCADE, related_name='inscripciones'
    )
    fecha_inscripcion = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['equipo', 'torneo'], name='inscripcion_unica'
            )
        ]

    def __str__(self):
        return f"{self.equipo.nombre} en {self.torneo.nombre}"


# --- MODELOS FASE DE GRUPOS ---


class Grupo(models.Model):
    torneo = models.ForeignKey(Torneo, on_delete=models.CASCADE, related_name="grupos")
    nombre = models.CharField(max_length=100)  # Ej: "Grupo A"

    # Relación muchos a muchos para saber qué equipos están en el grupo
    equipos = models.ManyToManyField(
        Equipo, through='EquipoGrupo', related_name='grupos_asignados'
    )

    def __str__(self):
        return f"{self.torneo.nombre} - {self.nombre}"


class EquipoGrupo(models.Model):
    """Tabla de Posiciones del Grupo"""

    grupo = models.ForeignKey(Grupo, on_delete=models.CASCADE, related_name="tabla")
    equipo = models.ForeignKey(Equipo, on_delete=models.CASCADE)
    numero = models.PositiveSmallIntegerField(default=0)  # 1, 2, 3, 4... para formar A1, A2

    partidos_jugados = models.PositiveSmallIntegerField(default=0)
    partidos_ganados = models.PositiveSmallIntegerField(default=0)
    partidos_perdidos = models.PositiveSmallIntegerField(default=0)

    # Sets
    sets_a_favor = models.PositiveSmallIntegerField(default=0)
    sets_en_contra = models.PositiveSmallIntegerField(default=0)

    # Games
    games_a_favor = models.PositiveSmallIntegerField(default=0)
    games_en_contra = models.PositiveSmallIntegerField(default=0)

    @property
    def diferencia_sets(self):
        return self.sets_a_favor - self.sets_en_contra

    @property
    def diferencia_games(self):
        return self.games_a_favor - self.games_en_contra

    def __str__(self):
        return f"{self.equipo} en {self.grupo}"

    class Meta:
        # Ordenamos la tabla según reglas de desempate de Padel
        ordering = [
            '-partidos_ganados',  # 1. Más partidos ganados
            '-sets_a_favor',
            'sets_en_contra',
        ]


class PartidoGrupo(models.Model):
    """Partido dentro de la Fase de Grupos"""

    grupo = models.ForeignKey(
        Grupo, on_delete=models.CASCADE, related_name="partidos_grupo"
    )
    equipo1 = models.ForeignKey(
        Equipo, on_delete=models.CASCADE, related_name="partidos_grupo_e1"
    )
    equipo2 = models.ForeignKey(
        Equipo, on_delete=models.CASCADE, related_name="partidos_grupo_e2"
    )

    # Resultados detallados (Padel: hasta 3 sets)
    e1_set1 = models.PositiveSmallIntegerField(null=True, blank=True)
    e2_set1 = models.PositiveSmallIntegerField(null=True, blank=True)
    e1_set2 = models.PositiveSmallIntegerField(null=True, blank=True)
    e2_set2 = models.PositiveSmallIntegerField(null=True, blank=True)
    e1_set3 = models.PositiveSmallIntegerField(null=True, blank=True)
    e2_set3 = models.PositiveSmallIntegerField(null=True, blank=True)

    # Fecha y Hora del Partido
    fecha_hora = models.DateTimeField(null=True, blank=True)

    ganador = models.ForeignKey(
        Equipo, on_delete=models.SET_NULL, null=True, blank=True, related_name="partidos_grupo_ganados"
    )

    @property
    def resultado(self):
        """Devuelve el resultado formateado como string (Ej: '6-4 6-2')"""
        if self.e1_set1 is None:
            return ""
        
        res = f"{self.e1_set1}-{self.e2_set1}"
        if self.e1_set2 is not None:
            res += f" {self.e1_set2}-{self.e2_set2}"
        if self.e1_set3 is not None:
            res += f" {self.e1_set3}-{self.e2_set3}"
        return res

    # Totales calculados (se llenan al guardar)
    e1_sets_ganados = models.PositiveSmallIntegerField(default=0)
    e2_sets_ganados = models.PositiveSmallIntegerField(default=0)
    e1_games_ganados = models.PositiveSmallIntegerField(default=0)
    e2_games_ganados = models.PositiveSmallIntegerField(default=0)

    def __str__(self):
        return f"{self.grupo}: {self.equipo1} vs {self.equipo2}"


# --- MODELOS FASE ELIMINATORIA (BRACKET) ---


class Partido(models.Model):
    """Partido de Eliminación Directa (Octavos, Cuartos, Final)"""

    torneo = models.ForeignKey(
        'Torneo', on_delete=models.CASCADE, related_name="partidos"
    )
    ronda = models.PositiveSmallIntegerField()  # 4=Final, 3=Semi, 2=Cuartos, 1=Octavos
    orden_partido = models.PositiveSmallIntegerField()

    equipo1 = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partidos_bracket_e1",
    )
    equipo2 = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partidos_bracket_e2",
    )

    ganador = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partidos_bracket_ganados",
    )

    # Resultado en texto (Ej: "6-4, 6-2")
    resultado = models.CharField(max_length=100, blank=True, null=True)

    # Fecha y Hora del Partido
    fecha_hora = models.DateTimeField(null=True, blank=True)

    # NUEVOS CAMPOS: Para guardar el detalle de sets en el bracket
    sets_local = models.JSONField(default=list, blank=True)
    sets_visitante = models.JSONField(default=list, blank=True)

    # Identificadores de cruce (Ej: "1A", "2B") para mostrar antes de que clasifiquen
    placeholder_e1 = models.CharField(max_length=50, blank=True, null=True)
    placeholder_e2 = models.CharField(max_length=50, blank=True, null=True)

    # Enlace al siguiente partido en el bracket
    siguiente_partido = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partidos_previos",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_ganador = self.ganador

    @property
    def nombre_ronda(self):
        """Devuelve el nombre legible de la ronda"""
        from django.db.models import Max
        # Intentar obtener el max_ronda del torneo
        # Nota: Esto hace una query extra por cada partido si no se optimiza,
        # pero es necesario para la visualización correcta en formularios individuales.
        max_ronda = self.torneo.partidos.aggregate(Max('ronda'))['ronda__max']
        
        if not max_ronda:
            return f"Ronda {self.ronda}"
            
        diff = max_ronda - self.ronda
        
        if diff == 0:
            return 'Final'
        elif diff == 1:
            return 'Semifinal'
        elif diff == 2:
            return 'Cuartos de Final'
        elif diff == 3:
            return 'Octavos de Final'
        elif diff == 4:
            return '16vos de Final'
        else:
            return f"Ronda {self.ronda}"

    def save(self, *args, **kwargs):
        # Lógica de avance automático
        
        # 1. Asegurar que si es la FINAL y hay ganador, se actualice el torneo
        # (Esto corre siempre que se grabe el partido final con ganador, por si falló antes)
        if self.ganador and self.siguiente_partido is None:
             if self.torneo.ganador_del_torneo != self.ganador:
                 self.torneo.ganador_del_torneo = self.ganador
                 self.torneo.estado = 'FN'
                 self.torneo.save()

        # 2. Avance en el bracket (Solo si cambió el ganador)
        if self.ganador != self.__original_ganador and self.ganador is not None:

            if self.siguiente_partido:  # Avanza
                siguiente = self.siguiente_partido
                if self.orden_partido % 2 == 1:
                    siguiente.equipo1 = self.ganador
                else:
                    siguiente.equipo2 = self.ganador
                siguiente.save()

        super().save(*args, **kwargs)
        self.__original_ganador = self.ganador

    def __str__(self):
        e1 = self.equipo1.nombre if self.equipo1 else "TBD"
        e2 = self.equipo2.nombre if self.equipo2 else "TBD"
        return f"{self.nombre_ronda}: {e1} vs {e2}"

    class Meta:
        ordering = ['ronda', 'orden_partido']
