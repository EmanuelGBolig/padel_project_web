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
        )

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


class OrganizacionForm(forms.ModelForm):

    class Meta:
        model = Organizacion
        fields = ('nombre', 'alias', 'descripcion', 'direccion', 'latitud', 'longitud', 'logo')
        widgets = {
            'logo': forms.FileInput(),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_textarea = 'textarea textarea-bordered w-full bg-base-100 text-base-content h-24'
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['class'] = estilo_textarea
            elif isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered w-full bg-base-100 text-base-content'
            else:
                field.widget.attrs['class'] = estilo_input


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
