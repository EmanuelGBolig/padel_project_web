from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm, AuthenticationForm
from .models import CustomUser
from equipos.models import Division


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


class CustomUserChangeForm(UserChangeForm):
    division = forms.ModelChoiceField(
        queryset=Division.objects.all(), required=True, label="División"
    )
    password = None # Ocultar campo de contraseña en perfil simple

    class Meta:
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
            if isinstance(field.widget, (forms.TextInput, forms.NumberInput, forms.EmailInput)):
                field.widget.attrs['class'] = estilo_input
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = estilo_select


class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        estilo_input = 'input input-bordered w-full bg-base-100 text-base-content'
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = estilo_input
