from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from .models import CustomUser, Division, Organizacion, Sponsor


class CustomUserCreationForm(UserCreationForm):
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(), required=True, label="División"
    )

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = (
            'email',
            'nombre',
            'apellido',
            'numero_telefono',
            'genero',
            'division',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered input-sm md:input-md w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered select-sm md:select-md w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            field.help_text = None # Eliminar textos de ayuda (requisitos de contraseña)
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput, forms.PasswordInput)):
                field.widget.attrs['class'] = estilo_input
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select

    def save(self, commit=True):
        user = super().save(commit=False)
        user.tipo_usuario = 'PLAYER'
        if commit:
            user.save()
        return user


class CustomUserAdminForm(UserChangeForm):
    """Formulario para el Admin de Django (Mantiene el campo password seguro)"""
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(), required=True, label="División"
    )
    hash_password_manual = forms.CharField(
        label="Pegar Hash de Contraseña",
        required=False,
        widget=forms.TextInput(attrs={'style': 'width: 100%; font-family: monospace;'}),
        help_text="Pegue aquí el hash exacto de otro usuario (ej. pbkdf2_sha256$720000$...) para clonar su contraseña. Si lo deja en blanco, la contraseña no se modificará."
    )

    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if self.instance.tipo_usuario in ['ADMIN', 'ORGANIZER'] or self.instance.is_staff:
                self.fields['division'].required = False

    def save(self, commit=True):
        user = super().save(commit=False)
        hash_manual = self.cleaned_data.get('hash_password_manual')
        if hash_manual:
            user.password = hash_manual
        if commit:
            user.save()
        return user


class CustomUserProfileForm(UserChangeForm):
    """Formulario para editar perfil en el frontend (Oculta password)"""
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(), required=True, label="División"
    )
    password = None 

    class Meta:
        model = CustomUser
        fields = (
            'imagen',
            'email',
            'nombre',
            'apellido',
            'numero_telefono',
            'genero',
            'division',
            # Ficha de jugador (TP-19.3)
            'posicion_cancha',
            'mano_habil',
            'club',
            'ciudad',
            'juega_desde',
            'instagram',
            'bio',
        )
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3, 'maxlength': 280,
                                         'placeholder': 'Contá algo sobre tu juego (máx. 280)'}),
            'instagram': forms.TextInput(attrs={'placeholder': 'tu_usuario (sin @)'}),
            'club': forms.TextInput(attrs={'placeholder': 'Ej: AprendePadel'}),
            'ciudad': forms.TextInput(attrs={'placeholder': 'Ej: Mar del Plata'}),
            'juega_desde': forms.NumberInput(attrs={'placeholder': 'Año, ej: 2019'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'

        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput)):
                field.widget.attrs['class'] = estilo_input
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered w-full bg-base-100 text-base-content'
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = 'textarea textarea-bordered w-full bg-base-100 text-base-content'

        # Labels claros para la ficha
        self.fields['posicion_cancha'].label = "Posición en la cancha"
        self.fields['mano_habil'].label = "Mano hábil"
        self.fields['juega_desde'].label = "Juega desde (año)"
        self.fields['bio'].label = "Sobre mí"

        if self.instance and self.instance.pk:
            if self.instance.tipo_usuario in ['ADMIN', 'ORGANIZER'] or self.instance.is_staff:
                self.fields['division'].required = False

    def clean_instagram(self):
        """Normaliza el handle de Instagram: sin @, sin URL, solo el usuario."""
        ig = (self.cleaned_data.get('instagram') or '').strip()
        if not ig:
            return ig
        ig = ig.rsplit('/', 1)[-1]          # saca https://instagram.com/usuario
        ig = ig.split('?')[0].lstrip('@')   # saca query y @
        import re
        if not re.fullmatch(r'[A-Za-z0-9._]{1,30}', ig):
            raise forms.ValidationError("Poné solo tu usuario de Instagram (letras, números, punto o guion bajo).")
        return ig

    def clean_juega_desde(self):
        anio = self.cleaned_data.get('juega_desde')
        if anio is None:
            return anio
        from django.utils import timezone
        actual = timezone.now().year
        if anio < 1950 or anio > actual:
            raise forms.ValidationError(f"Ingresá un año entre 1950 y {actual}.")
        return anio


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = estilo_input

    def clean(self):
        from django.contrib.auth import authenticate, get_user_model
        from django.core.exceptions import ValidationError
        
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username is not None and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                # Revisar si el usuario existe, tiene password correcta pero está inactivo (o error de mayúsculas)
                User = get_user_model()
                try:
                    user = User.objects.get(email__iexact=username)
                    # Cuenta fusionada (TP-20): el mail es válido pero la contraseña
                    # de esta cuenta vieja ya no sirve; hay que usar la de la principal.
                    if user.merged_into_id:
                        raise ValidationError(
                            "Esta cuenta se unificó con otra. Entrá con este mismo mail "
                            "pero usando la contraseña de tu cuenta principal.",
                            code='merged',
                        )
                    if user.check_password(password):
                        if not user.is_active:
                            if self.request:
                                self.request.session['verification_user_id'] = user.id
                            raise ValidationError("Debes verificar tu cuenta primero.", code='unverified')
                        else:
                            # Autenticación exitosa (el problema eran las mayúsculas en el email)
                            self.user_cache = user
                            self.confirm_login_allowed(self.user_cache)
                            return self.cleaned_data
                except (User.DoesNotExist, User.MultipleObjectsReturned):
                    pass
                
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class GoogleProfileCompletionForm(forms.ModelForm):
    """
    Formulario para que los usuarios que se registran con Google completen
    los campos que Google no provee: teléfono, división y género.
    """
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(),
        required=True,
        label='División',
        empty_label='Seleccioná tu división',
    )

    class Meta:
        model = CustomUser
        fields = ('numero_telefono', 'genero', 'division')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'

        self.fields['numero_telefono'].required = True
        self.fields['numero_telefono'].label = 'Número de teléfono'
        self.fields['genero'].label = 'Género'

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            else:
                field.widget.attrs['class'] = estilo_input

        if self.instance and self.instance.pk:
            if self.instance.tipo_usuario in ['ADMIN', 'ORGANIZER'] or self.instance.is_staff:
                self.fields['division'].required = False


class OrganizacionForm(forms.ModelForm):

    class Meta:
        model = Organizacion
        fields = ('nombre', 'alias', 'descripcion', 'whatsapp', 'direccion', 'latitud', 'longitud', 'logo', 'receptor_notificaciones')
        widgets = {
            'logo': forms.FileInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_textarea = 'textarea textarea-bordered w-full bg-base-100 text-base-content h-24'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = estilo_textarea
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered w-full bg-base-100 text-base-content'
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            else:
                field.widget.attrs['class'] = estilo_input

        # Filtrar para que solo muestre organizadores de ESTA organización
        if self.instance and self.instance.pk:
            from accounts.models import CustomUser
            self.fields['receptor_notificaciones'].queryset = CustomUser.objects.filter(
                organizacion=self.instance, tipo_usuario='ORGANIZER'
            )


class SponsorForm(forms.ModelForm):
    class Meta:
        model = Sponsor
        fields = ('nombre', 'imagen', 'link', 'orden')
        widgets = {
            'imagen': forms.FileInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered w-full bg-base-100 text-base-content'
            else:
                field.widget.attrs['class'] = estilo_input


class DummyUserCreationForm(forms.ModelForm):
    """
    Formulario para que los organizadores creen jugadores 'dummy' sin cuenta real
    pero que se pueden usar para formar parejas y que computen puntos en el ranking.
    """
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(), required=True, label="División"
    )

    class Meta:
        model = CustomUser
        fields = ('nombre', 'apellido', 'genero', 'division')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'

        self.fields['genero'].label = 'Género'
        self.fields['genero'].required = True
        # Agregar opción vacía al inicio para forzar que el organizador elija explícitamente
        genero_choices = [('', 'Seleccioná el género')] + list(self.fields['genero'].choices)
        self.fields['genero'].choices = genero_choices

        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select
            else:
                field.widget.attrs['class'] = estilo_input

    def save(self, commit=True, organizacion=None):
        import uuid
        user = super().save(commit=False)
        user.is_dummy = True
        user.tipo_usuario = 'PLAYER'
        user.is_active = False # No pueden loguear
        
        if organizacion:
            user.organizacion = organizacion

        # Autogenerar email único ficticio usando uuid para evadir el constraint
        unique_id = str(uuid.uuid4())[:8]
        user.email = f"dummy_{unique_id}@padel.local"

        if commit:
            user.save()
        return user


class MergeUserForm(forms.Form):
    """
    Formulario para elegir un usuario dummy y un usuario real para fusionar sus historiales.
    """
    dummy_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_dummy=True),
        label="Jugador Dummy (Origen)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )
    real_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_dummy=False, tipo_usuario='PLAYER'),
        label="Usuario Real (Destino)",
        widget=forms.Select(attrs={'class': 'select select-bordered w-full bg-base-100 text-base-content'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtros opcionales pueden añadirse aquí si se pasan desde la vista
