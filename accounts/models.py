from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
    Permission,
)
from django.db import models
from django.utils import timezone


# --- ¡NUEVO MODELO AÑADIDO AQUÍ! ---
# Modelo de referencia para las divisiones
# Movido desde 'equipos' para romper la dependencia circular
class Division(models.Model):
    nombre = models.CharField(max_length=50, unique=True)  # Ej: "3ra", "4ta", "5ta"
    orden = models.PositiveSmallIntegerField(unique=True, help_text="Octava=8, Séptima=7, ..., Primera=1")

    class Meta:
        ordering = ['orden']  # Ordena de menor a mayor (Primera=1 primero)
        verbose_name_plural = "Divisiones"

    def __str__(self):
        return self.nombre


# --- FIN DEL MODELO AÑADIDO ---


class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('tipo_usuario', 'ADMIN')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractBaseUser, PermissionsMixin):

    class TipoUsuario(models.TextChoices):
        PLAYER = 'PLAYER', 'Jugador'
        ADMIN = 'ADMIN', 'Admin'

    class Genero(models.TextChoices):
        MASCULINO = 'MASCULINO', 'Masculino'
        FEMENINO = 'FEMENINO', 'Femenino'
        OTRO = 'OTRO', 'Otro'

    # Campos de Registro
    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    numero_telefono = models.CharField(max_length=20, blank=True)
    imagen = models.ImageField(upload_to='perfiles/', blank=True, null=True)

    division = models.ForeignKey(
        'accounts.Division',  # <-- CAMBIO AQUÍ (apunta a sí mismo)
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    genero = models.CharField(
        max_length=10, choices=Genero.choices, default=Genero.MASCULINO
    )

    # Campos de Rol
    tipo_usuario = models.CharField(
        max_length=10, choices=TipoUsuario.choices, default=TipoUsuario.PLAYER
    )

    # Campos de Django
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)

    # --- Solución al Error E304 ---
    # Debemos sobreescribir los campos 'groups' y 'user_permissions'
    # para añadir un related_name único y evitar conflictos con auth.User

    groups = models.ManyToManyField(
        Group,
        verbose_name='grupos',
        blank=True,
        help_text=(
            'Los grupos a los que pertenece este usuario. Un usuario obtendrá todos los permisos '
            'concedidos a cada uno de sus grupos.'
        ),
        # Nombre de relación inverso único
        related_name="custom_user_groups",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='permisos de usuario',
        blank=True,
        help_text='Permisos específicos para este usuario.',
        # Nombre de relación inverso único
        related_name="custom_user_permissions",
        related_query_name="user",
    )
    # --- Fin de la Solución ---

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre', 'apellido']

    class Meta:
        verbose_name = "un usuario"
        verbose_name_plural = "usuarios"

    def __str__(self):
        return self.email

    @property
    def full_name(self):
        return f"{self.nombre} {self.apellido}"

    def save(self, *args, **kwargs):
        # Si hay imagen y es nueva (o ha cambiado)
        if self.imagen:
            try:
                # Verificar si es una imagen nueva comparando con la base de datos
                if self.pk:
                    old_user = CustomUser.objects.get(pk=self.pk)
                    if old_user.imagen == self.imagen:
                        super().save(*args, **kwargs)
                        return
            except CustomUser.DoesNotExist:
                pass  # Es un usuario nuevo

            # Procesar la imagen
            from PIL import Image
            from io import BytesIO
            from django.core.files.uploadedfile import InMemoryUploadedFile
            import sys
            import os

            # Abrir la imagen subida
            try:
                img = Image.open(self.imagen)
                
                # Convertir a RGB si es necesario (ej. PNG con transparencia)
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                
                # Preparar buffer
                output = BytesIO()
                
                # Guardar como WebP
                img.save(output, format='WEBP', quality=80)
                output.seek(0)
                
                # Crear nuevo nombre de archivo
                nombre_base = os.path.splitext(self.imagen.name)[0]
                nuevo_nombre = f"{nombre_base}.webp"
                
                # Crear el archivo en memoria de Django
                self.imagen = InMemoryUploadedFile(
                    output,
                    'ImageField',
                    nuevo_nombre,
                    'image/webp',
                    sys.getsizeof(output),
                    None
                )
            except Exception:
                # Si falla, guardar como estaba originalmente (silenciosamente en prod)
                pass

        super().save(*args, **kwargs)

    @property
    def get_avatar_url(self):
        if self.imagen:
            return self.imagen.url
        return None  # El template manejará el fallback

    @property
    def equipo(self):
        """
        Propiedad para encontrar fácilmente el equipo de un jugador,
        ya sea como jugador1 o jugador2.
        """
        # Importación local para evitar importación circular
        from equipos.models import Equipo

        equipo = self.equipos_como_jugador1.first()
        if not equipo:
            equipo = self.equipos_como_jugador2.first()
        return equipo
