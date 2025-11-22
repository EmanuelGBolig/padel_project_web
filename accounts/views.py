from django.urls import reverse_lazy
from django.views.generic import CreateView, UpdateView
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import CustomUser
from .forms import CustomUserCreationForm, CustomUserChangeForm, CustomLoginForm


class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = CustomLoginForm
    redirect_authenticated_user = True


class CustomLogoutView(LogoutView):
    next_page = reverse_lazy('core:home')


class RegistroView(CreateView):
    model = CustomUser
    form_class = CustomUserCreationForm
    template_name = 'accounts/registro.html'
    success_url = reverse_lazy('accounts:login')


class PerfilView(LoginRequiredMixin, UpdateView):
    model = CustomUser
    form_class = CustomUserChangeForm
    template_name = 'accounts/perfil.html'
    success_url = reverse_lazy('accounts:perfil')

    def get_object(self, queryset=None):
        # Devuelve el usuario actualmente logueado
        return self.request.user
