from django.db import models
from django.conf import settings
from accounts.models import Division


class Equipo(models.Model):
    # Nombre autogenerado (Ej: "Gomez/Perez")
    nombre = models.CharField(max_length=100, unique=True, blank=True)

    jugador1 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="equipos_como_jugador1",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    jugador2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="equipos_como_jugador2",
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    division = models.ForeignKey(Division, on_delete=models.PROTECT, null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    esta_activo = models.BooleanField(default=True, verbose_name="Esta Activo")

    class Meta:
        # Evita que los mismos dos jugadores formen otro equipo ACTIVO
        constraints = [
            models.UniqueConstraint(
                fields=['jugador1', 'jugador2'], 
                condition=models.Q(esta_activo=True), 
                name='unique_active_team'
            )
        ]

    class Categoria(models.TextChoices):
        MASCULINO = 'M', 'Masculino'
        FEMENINO = 'F', 'Femenino'
        MIXTO = 'X', 'Mixto'

    categoria = models.CharField(
        max_length=1, 
        choices=Categoria.choices, 
        default=Categoria.MIXTO,
        verbose_name="Categoría del Equipo"
    )

    es_dummy = models.BooleanField(
        default=False,
        verbose_name="Es Pareja Libre (Dummy)",
        help_text="Equipo creado automáticamente para rellenar grupos."
    )

    def save(self, *args, **kwargs):
        # Lógica adaptada:
        if self.es_dummy:
             pass
        elif self.jugador1 and self.jugador2:
            # NORMALIZACIÓN: Asegurar orden único de IDs para evitar duplicados (J1 < J2)
            if self.jugador1_id > self.jugador2_id:
                self.jugador1, self.jugador2 = self.jugador2, self.jugador1
            
            # 1. Usamos 'apellido' (nuestro campo) en lugar de 'last_name'
            # Si no tienen apellido, usamos el email como fallback
            j1_nombre = self.jugador1.apellido or self.jugador1.email.split('@')[0]
            j2_nombre = self.jugador2.apellido or self.jugador2.email.split('@')[0]

            # 2. Ordenamos alfabéticamente para consistencia
            nombres_ordenados = sorted([j1_nombre, j2_nombre])
            base_nombre = f"{nombres_ordenados[0]}/{nombres_ordenados[1]}"
            
            if not self.nombre or not self.nombre.startswith(base_nombre):
                self.nombre = base_nombre
                
            original_nombre = self.nombre
            counter = 1
            while Equipo.objects.filter(nombre=self.nombre).exclude(pk=self.pk).exists():
                self.nombre = f"{original_nombre} ({counter})"
                counter += 1

            # 3. Asignar división automáticamente basada en el mejor ranking (menor orden)
            if not self.division_id and self.jugador1 and self.jugador2:
                d1 = self.jugador1.division
                d2 = self.jugador2.division
                
                if d1 and d2:
                    # Elegimos la división con menor 'orden' (ej: 4ta=4 vs 6ta=6 -> elegimos 4ta)
                    self.division = d1 if d1.orden <= d2.orden else d2
                elif d1:
                    self.division = d1
                elif d2:
                    self.division = d2

        super().save(*args, **kwargs)

    def __str__(self):
        if self.jugador1 and self.jugador1.is_dummy and self.jugador2 and self.jugador2.is_dummy:
             return f"{self.nombre} [Dummies]"
        elif (self.jugador1 and self.jugador1.is_dummy) or (self.jugador2 and self.jugador2.is_dummy):
             return f"{self.nombre} [Con Dummy]"
        return self.nombre

    # === ESTADÍSTICAS ===
    
    def get_partidos_jugados(self):
        """Retorna todos los partidos (grupos + eliminación) donde participó"""
        from torneos.models import Partido, PartidoGrupo
        
        partidos_elim = Partido.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        )
        
        partidos_grupo = PartidoGrupo.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        )
        
        return {
            'eliminacion': partidos_elim,
            'grupos': partidos_grupo,
            'total': partidos_elim.count() + partidos_grupo.count()
        }
    
    def get_victorias(self):
        """Cuenta victorias totales"""
        from torneos.models import Partido, PartidoGrupo
        
        victorias_elim = Partido.objects.filter(ganador=self).count()
        victorias_grupo = PartidoGrupo.objects.filter(ganador=self).count()
        
        return victorias_elim + victorias_grupo
    
    def get_derrotas(self):
        """Cuenta derrotas totales"""
        partidos = self.get_partidos_jugados()
        return partidos['total'] - self.get_victorias()
    
    def get_win_rate(self):
        """Calcula % de victorias"""
        partidos = self.get_partidos_jugados()
        if partidos['total'] == 0:
            return 0
        return round((self.get_victorias() / partidos['total']) * 100, 1)
    
    def get_torneos_ganados(self):
        """Cuenta torneos donde fue campeón"""
        from torneos.models import Torneo
        return Torneo.objects.filter(ganador_del_torneo=self).count()
    
    def get_racha_actual(self):
        """Calcula racha de victorias/derrotas consecutivas"""
        from torneos.models import Partido, PartidoGrupo
        
        partidos_elim = list(Partido.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        ).select_related('torneo').order_by('-torneo__fecha_inicio', '-ronda'))
        
        partidos_grupo = list(PartidoGrupo.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        ).select_related('grupo__torneo').order_by('-grupo__torneo__fecha_inicio'))
        
        todos = partidos_elim + partidos_grupo
        
        if not todos:
            return {'tipo': None, 'cantidad': 0, 'texto': ''}
        
        ultimo = todos[0]
        es_victoria = ultimo.ganador == self
        
        racha = 0
        for partido in todos:
            if partido.ganador == self:
                if es_victoria:
                    racha += 1
                else:
                    break
            else:
                if not es_victoria:
                    racha += 1
                else:
                    break
        
        tipo = 'victoria' if es_victoria else 'derrota'
        tipo_texto = tipo.title() + ('s' if racha != 1 else '')
       
        return {
            'tipo': tipo,
            'cantidad': racha,
            'texto': f'Racha de {racha} {tipo_texto}'
        }
    
    def get_ultimos_resultados(self, limit=5):
        """Obtiene últimos N resultados"""
        from torneos.models import Partido, PartidoGrupo
        
        partidos_elim = Partido.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        ).select_related('torneo', 'equipo1', 'equipo2').order_by('-torneo__fecha_inicio', '-ronda')
        
        partidos_grupo = PartidoGrupo.objects.filter(
            models.Q(equipo1=self) | models.Q(equipo2=self),
            ganador__isnull=False
        ).select_related('grupo__torneo', 'equipo1', 'equipo2').order_by('-grupo__torneo__fecha_inicio')
        
        resultados = []
        
        for p in partidos_elim:
            if len(resultados) >= limit:
                break
            resultados.append({
                'ganado': p.ganador == self,
                'rival': p.equipo2 if p.equipo1 == self else p.equipo1,
                'torneo': p.torneo.nombre,
                'tipo': 'eliminacion'
            })
        
        for p in partidos_grupo:
            if len(resultados) >= limit:
                break
            resultados.append({
                'ganado': p.ganador == self,
                'rival': p.equipo2 if p.equipo1 == self else p.equipo1,
                'torneo': p.grupo.torneo.nombre,
                'tipo': 'grupo'
            })
        
        return resultados[:limit]
    
    def get_puntos_ranking(self):
        """Devuelve los puntos totales sumados desde la tabla de rankings cacheada en BD"""
        # Evitamos import circular
        from equipos.models import RankingEquipo
        
        total = RankingEquipo.objects.filter(equipo=self).aggregate(models.Sum('puntos'))['puntos__sum']
        return total or 0


class Invitation(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pendiente'
        ACCEPTED = 'ACCEPTED', 'Aceptada'
        REJECTED = 'REJECTED', 'Rechazada'

    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='sent_invitations',
        on_delete=models.CASCADE
    )
    invited = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='received_invitations',
        on_delete=models.CASCADE
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('inviter', 'invited', 'status')
        ordering = ['-timestamp']

    def __str__(self):
        return f"Invitación de {self.inviter} a {self.invited} ({self.status})"


class RankingJugador(models.Model):
    jugador = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rankings_jugador')
    division = models.ForeignKey(Division, on_delete=models.CASCADE, related_name='rankings_jugadores_division')
    puntos = models.IntegerField(default=0)
    torneos_ganados = models.IntegerField(default=0)
    victorias = models.IntegerField(default=0)
    partidos_jugados = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['jugador', 'division'], name='unique_ranking_jugador_division')
        ]
        verbose_name = "Ranking de Jugador"
        verbose_name_plural = "Rankings de Jugadores"

    def __str__(self):
        return f"{self.jugador} - {self.division} ({self.puntos} pts)"


