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
