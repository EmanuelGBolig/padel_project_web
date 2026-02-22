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
        (None, {'fields': ('email', 'password', 'raw_password_hash')}),
        (
            'Información Personal',
            {'fields': ('nombre', 'apellido', 'numero_telefono', 'genero', 'division', 'organizacion')},
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

from .models import Division, Organizacion, Sponsor

@admin.register(Division)
class DivisionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden')
    ordering = ('orden',)

class SponsorInline(admin.TabularInline):
    model = Sponsor
    extra = 1

@admin.register(Organizacion)
class OrganizacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'alias', 'direccion')
    inlines = [SponsorInline]
