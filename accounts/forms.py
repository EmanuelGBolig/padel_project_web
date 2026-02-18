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
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        estilo_select = 'select select-bordered w-full bg-base-100 text-base-content'
        
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

    class Meta:
        model = CustomUser
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No aplicamos estilos personalizados agresivos aquí para no romper el admin,
        # o solo aplicamos a campos específicos si es necesario.
        # UserChangeForm ya trae widgets adecuados para el admin.


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
class OrganizacionForm(forms.ModelForm):
    class Meta:
        model = Organizacion
        fields = ('nombre', 'alias', 'descripcion', 'direccion', 'latitud', 'longitud', 'logo')
    
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.FileInput):
                field.widget.attrs['class'] = 'file-input file-input-bordered w-full bg-base-100 text-base-content'
            else:
                field.widget.attrs['class'] = estilo_input
