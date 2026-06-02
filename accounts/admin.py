from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .forms import CustomUserCreationForm, CustomUserAdminForm
from .models import CustomUser


class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserAdminForm
    model = CustomUser
    list_display = (
        'email',
        'nombre',
        'apellido',
        'tipo_usuario',
        'division',
        'is_staff',
    )
    list_filter = ('tipo_usuario', 'division', 'is_staff', 'is_active')

    readonly_fields = ('raw_password_hash', 'last_login', 'date_joined')

    def raw_password_hash(self, obj):
        return obj.password
    raw_password_hash.short_description = 'Hash de Contraseña (Solo Lectura)'

    # Campos mostrados al editar
    fieldsets = (
        (None, {'fields': ('email', 'password', 'raw_password_hash', 'hash_password_manual')}),
        (
            'Información Personal',
            {'fields': ('nombre', 'apellido', 'imagen', 'numero_telefono', 'genero', 'division', 'organizacion')},
        ),
        (
            'Permisos',
            {
                'fields': (
                    'is_active',
                    'is_staff',
                    'is_superuser',
                    'tipo_usuario',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        ('Fechas Importantes', {'fields': ('last_login', 'date_joined')}),
    )

    # Campos mostrados al crear
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': (
                    'email',
                    'password1',
                    'password2',
                    'nombre',
                    'apellido',
                    'numero_telefono',
                    'genero',
                    'division',
                    'tipo_usuario',
                    'organizacion',
                ),
            },
        ),
    )
    search_fields = ('email', 'nombre', 'apellido')
    ordering = ('email',)


admin.site.register(CustomUser, CustomUserAdmin)

from .models import Division, Organizacion, Sponsor, MergeAuditLog

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden')
    ordering = ('orden',)


@admin.register(MergeAuditLog)
class MergeAuditLogAdmin(admin.ModelAdmin):
    """Auditoría de fusiones de cuentas (TP-21): solo lectura."""
    list_display = ('created_at', 'actor_email', 'source_email', 'source_was_dummy', 'target_email')
    list_filter = ('source_was_dummy', 'created_at')
    search_fields = ('actor_email', 'source_email', 'target_email', 'source_nombre', 'target_nombre')
    readonly_fields = [f.name for f in MergeAuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

class SponsorInline(admin.TabularInline):
    model = Sponsor
    extra = 1

@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'alias', 'direccion')
    inlines = [SponsorInline]
