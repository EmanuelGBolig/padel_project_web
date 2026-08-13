from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
    Group,
    Permission,
)
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
from core.validators import validar_imagen


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
        ORGANIZER = 'ORGANIZER', 'Organizador'

    class Genero(models.TextChoices):
        MASCULINO = 'MASCULINO', 'Masculino'
        FEMENINO = 'FEMENINO', 'Femenino'
        OTRO = 'OTRO', 'Otro'

    # Ficha de jugador (TP-19.3)
    class Posicion(models.TextChoices):
        DRIVE = 'D', 'Drive'
        REVES = 'R', 'Revés'
        AMBAS = 'A', 'Ambas'

    class Mano(models.TextChoices):
        DIESTRA = 'D', 'Diestra'
        ZURDA = 'Z', 'Zurda'

    # Campos de Registro
    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    numero_telefono = models.CharField(max_length=20, blank=True)
    imagen = models.ImageField(
        upload_to='perfiles/', blank=True, null=True, validators=[validar_imagen]
    )

    # --- Ficha de jugador (TP-19.3) ---
    posicion_cancha = models.CharField(max_length=1, choices=Posicion.choices, blank=True)
    mano_habil = models.CharField(max_length=1, choices=Mano.choices, blank=True)
    club = models.CharField(max_length=120, blank=True)
    ciudad = models.CharField(max_length=100, blank=True)
    juega_desde = models.PositiveSmallIntegerField(null=True, blank=True, help_text="Año en que empezó a jugar")
    instagram = models.CharField(max_length=50, blank=True, help_text="Usuario de Instagram, sin @")
    bio = models.TextField(blank=True, max_length=280)

    # Campos de Verificación
    verification_code = models.CharField(max_length=6, blank=True, null=True)
    is_verified = models.BooleanField(default=False)


    division = models.ForeignKey(
        'accounts.Division',  # <-- CAMBIO AQUÍ (apunta a sí mismo)
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    genero = models.CharField(
        max_length=10, choices=Genero.choices
    )

    # Campos de Rol
    tipo_usuario = models.CharField(
        max_length=10, choices=TipoUsuario.choices, default=TipoUsuario.PLAYER
    )
    
    # Campos de Organización y Dummy
    organizacion = models.ForeignKey(
        'accounts.Organizacion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='miembros'
    )
    is_dummy = models.BooleanField(
        default=False,
        verbose_name="Es Jugador Creado por Organizador",
        help_text="Indica si el usuario fue creado por un organizador para usar de relleno y no tiene cuenta real."
    )

    # Cuentas creadas automáticamente al anotarse sin cuenta: la contraseña se le
    # dicta por WhatsApp, así que tiene que cambiarla la primera vez que entra.
    debe_cambiar_password = models.BooleanField(
        default=False,
        verbose_name="Tiene que cambiar la contraseña al entrar",
        help_text="Se activa en las cuentas creadas con contraseña automática.",
    )

    # Deduplicación de cuentas (TP-20): si está seteado, esta cuenta fue
    # fusionada dentro de otra. No aparece en rankings; en etapa 2 su email
    # podrá usarse para entrar a la cuenta canónica.
    merged_into = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cuentas_fusionadas',
        help_text="Cuenta canónica en la que se fusionó esta cuenta."
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

    @property
    def telefono_numero(self):
        """Solo dígitos del teléfono, para enlaces https://wa.me/<numero>."""
        import re
        return re.sub(r'\D', '', self.numero_telefono or '')

    class Meta:
        indexes = [
            # Rankings y listados de jugadores filtran por división + tipo, y las
            # herramientas de organizador por dummy/organización.
            models.Index(fields=['tipo_usuario', 'is_dummy'], name='user_tipo_dummy_idx'),
            models.Index(fields=['division', 'tipo_usuario'], name='user_division_tipo_idx'),
            models.Index(fields=['organizacion'], name='user_organizacion_idx'),
        ]

    def save(self, *args, **kwargs):
        # Simplemente guardar - Cloudinary se encarga de la optimización
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

        equipo = self.equipos_como_jugador1.filter(esta_activo=True).first()
        if not equipo:
            equipo = self.equipos_como_jugador2.filter(esta_activo=True).first()
        return equipo

class Organizacion(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
    alias = models.SlugField(max_length=150, unique=True, help_text="URL amigable (ej: club-padel-mdq)")
    descripcion = models.TextField(blank=True, help_text="Descripción del organizador o sede.")
    ciudad = models.CharField(max_length=100, blank=True, help_text="Ciudad/localidad de la sede.")
    direccion = models.CharField(max_length=255, blank=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    logo = models.ImageField(
        upload_to='organizadores/logos/', blank=True, null=True, validators=[validar_imagen]
    )
    receptor_notificaciones = models.ForeignKey(
        'accounts.CustomUser',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organizacion_notificaciones',
        limit_choices_to={'tipo_usuario': 'ORGANIZER'},
        help_text="Organizador que recibirá los emails de nuevas inscripciones."
    )
    whatsapp = models.CharField(
        max_length=20,
        blank=True,
        validators=[RegexValidator(
            r'^\+?\d{8,15}$',
            'Ingresá el número en formato internacional, solo dígitos (ej: +5491123456789).'
        )],
        help_text="WhatsApp de contacto en formato internacional (ej: +54911...). Habilita el botón de contacto.",
    )

    # --- Cobro de inscripciones ---
    # Los datos bancarios son de la organización, no de cada torneo: se cargan una
    # vez y valen para todos. Los importes sí van por torneo.
    alias_cobro = models.CharField(
        max_length=100, blank=True,
        verbose_name="Alias o CBU para transferencias",
        help_text="Ej: miclub.padel. Se muestra a los jugadores al inscribirse.",
    )
    titular_cobro = models.CharField(
        max_length=150, blank=True,
        verbose_name="Titular de la cuenta",
        help_text="Nombre que figura en la cuenta, para que el jugador verifique antes de transferir.",
    )
    whatsapps_comprobante = models.CharField(
        max_length=200, blank=True,
        verbose_name="WhatsApp(s) para enviar el comprobante",
        help_text="Uno o varios separados por coma. Ej: +5492235937115, +5492236337881",
    )

    @property
    def whatsapps_comprobante_lista(self):
        """Los números de comprobante como lista de (visible, solo_digitos)."""
        import re
        salida = []
        for crudo in (self.whatsapps_comprobante or '').split(','):
            crudo = crudo.strip()
            if not crudo:
                continue
            salida.append((crudo, re.sub(r'\D', '', crudo)))
        return salida

    @property
    def tiene_datos_de_cobro(self):
        return bool(self.alias_cobro)

    class Meta:
        verbose_name = "Organización"
        verbose_name_plural = "Organizaciones"

    def __str__(self):
        return self.nombre

    @property
    def whatsapp_numero(self):
        """Solo dígitos, para construir enlaces https://wa.me/<numero>."""
        import re
        return re.sub(r'\D', '', self.whatsapp or '')


class Sponsor(models.Model):
    organizacion = models.ForeignKey(
        Organizacion,
        on_delete=models.CASCADE,
        related_name='sponsors',
        null=True,
        blank=True
    )
    nombre = models.CharField(max_length=100)
    imagen = models.ImageField(upload_to='sponsors/', validators=[validar_imagen])
    link = models.URLField(blank=True)
    orden = models.PositiveIntegerField(default=0, help_text="Orden de aparición en el carrusel")

    class Meta:
        ordering = ['orden']

    def __str__(self):
        return f"{self.nombre} (Sponsor de {self.organizacion.nombre})"


class PushSubscription(models.Model):
    """Suscripción Web Push de un dispositivo del usuario (TP-11).

    Un usuario puede tener varias (celu + compu). Si el endpoint devuelve
    404/410 al enviar, la suscripción está vencida y se borra.
    """
    user = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.CASCADE, related_name='push_subscriptions'
    )
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suscripción push"
        verbose_name_plural = "Suscripciones push"

    def __str__(self):
        return f"Push de {self.user} ({self.endpoint[:40]}…)"


class Notificacion(models.Model):
    """Una notificación guardada, para el panel de la campanita.

    Hasta ahora todo aviso era Web Push y nada más: si el celular estaba en
    silencio, si el usuario descartaba el globito o si nunca dio permiso de
    notificaciones, el aviso se perdía y no había dónde ir a buscarlo. Acá queda
    guardado y el usuario lo puede abrir cuando quiera.

    Se crea sola: `accounts.push.send_push_to_users` graba una por destinatario
    antes de intentar el envío, así que **todo aviso de la app cae en el panel**
    aunque las claves VAPID no estén configuradas o el push falle.
    """
    usuario = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.CASCADE, related_name='notificaciones'
    )
    titulo = models.CharField(max_length=120)
    cuerpo = models.TextField(blank=True)
    # A dónde lleva al tocarla. Siempre una ruta interna (arranca con "/").
    url = models.CharField(max_length=300, default='/')
    leida = models.BooleanField(default=False)
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada']
        indexes = [
            # El contador del navbar filtra siempre por estos dos campos.
            models.Index(fields=['usuario', 'leida'], name='notif_usuario_leida_idx'),
        ]
        verbose_name = "Notificación"
        verbose_name_plural = "Notificaciones"

    def __str__(self):
        return f"{self.titulo} → {self.usuario}"

    @property
    def destino_seguro(self):
        """La URL a la que redirigir, validada.

        Las notificaciones las arma el código de la app, no el usuario, pero el
        redirect igual se limita a rutas internas: si mañana algún dato de un
        formulario termina acá, no queremos un open redirect.
        """
        destino = (self.url or '/').strip()
        if not destino.startswith('/') or destino.startswith('//'):
            return '/'
        return destino


class MergeAuditLog(models.Model):
    """Registro de fusiones de cuentas (TP-21 seguridad). Quién fusionó qué y cuándo."""
    actor = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fusiones_realizadas'
    )
    actor_email = models.CharField(max_length=254, blank=True)
    source_id = models.IntegerField()
    source_email = models.CharField(max_length=254, blank=True)
    source_nombre = models.CharField(max_length=210, blank=True)
    source_was_dummy = models.BooleanField(default=False)
    target = models.ForeignKey(
        'accounts.CustomUser', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='fusiones_recibidas'
    )
    target_email = models.CharField(max_length=254, blank=True)
    target_nombre = models.CharField(max_length=210, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Registro de fusión"
        verbose_name_plural = "Registros de fusión"

    def __str__(self):
        return f"{self.source_email} → {self.target_email} ({self.created_at:%d/%m/%Y})"
