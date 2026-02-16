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
    )
    jugador2 = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="equipos_como_jugador2",
        on_delete=models.CASCADE,
    )
    division = models.ForeignKey(Division, on_delete=models.PROTECT)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Evita que los mismos dos jugadores formen otro equipo
        unique_together = ('jugador1', 'jugador2')

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

    def save(self, *args, **kwargs):
        # Lógica adaptada de tu proyecto anterior:
        if self.jugador1 and self.jugador2:
            # 1. Usamos 'apellido' (nuestro campo) en lugar de 'last_name'
            # Si no tienen apellido, usamos el email como fallback
            j1_nombre = self.jugador1.apellido or self.jugador1.email.split('@')[0]
            j2_nombre = self.jugador2.apellido or self.jugador2.email.split('@')[0]

            # 2. Ordenamos alfabéticamente para consistencia
            nombres_ordenados = sorted([j1_nombre, j2_nombre])
            self.nombre = f"{nombres_ordenados[0]}/{nombres_ordenados[1]}"

            # 3. Asignar división automáticamente basada en el jugador 1 (si no se pasó)
            # Esto mantiene la integridad de datos
            if not self.division_id:
                self.division = self.jugador1.division

        super().save(*args, **kwargs)

    def __str__(self):
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
        """Calcula puntos para el ranking global"""
        puntos = 0
        
        # Victorias: 3 puntos cada una
        puntos += self.get_victorias() * 3
        
        # Torneos ganados: 50 puntos extra cada uno
        puntos += self.get_torneos_ganados() * 50
        
        # Bonus por win rate alto (>=75%) con al menos 5 partidos
        partidos_jugados = self.get_partidos_jugados()['total']
        if self.get_win_rate() >= 75 and partidos_jugados >= 5:
            puntos += 20
        
        return puntos


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

