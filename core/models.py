from django.db import models


class Testimonio(models.Model):
    """Testimonio de un jugador/organizador para la prueba social del home (TP-04)."""
    autor = models.CharField(max_length=100)
    rol = models.CharField(max_length=100, blank=True, help_text="Ej: Jugador 7ma · Organizador")
    texto = models.TextField()
    foto = models.ImageField(upload_to='testimonios/', blank=True, null=True)
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición")

    class Meta:
        ordering = ['orden']
        verbose_name = "Testimonio"
        verbose_name_plural = "Testimonios"

    def __str__(self):
        return f"{self.autor} ({self.rol})" if self.rol else self.autor
