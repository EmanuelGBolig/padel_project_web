from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, DeleteView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .models import Equipo
from accounts.models import Division, CustomUser
from .forms import EquipoCreateForm
from django.db.models import Q  # Importamos Q de forma limpia
from django.db import models  # <--- ¡CORRECCIÓN! Importamos models desde django.db

# IMPORTANTE: Importar las vistas de autocompletado
from dal import autocomplete


# --- Mixins de Permisos ---
class PlayerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verifica que el usuario sea un 'PLAYER'"""

    def test_func(self):
        return self.request.user.tipo_usuario == 'PLAYER'

    def handle_no_permission(self):
        messages.error(
            self.request, "Debes ser un jugador para acceder a esta sección."
        )
        return redirect(reverse_lazy('core:home'))


class PlayerHasNoTeamMixin(PlayerRequiredMixin):
    """Verifica que el jugador NO tenga equipo. Para CreateView."""

    def test_func(self):
        if not super().test_func():
            return False
        # FIX: Usamos el método equipo del modelo CustomUser
        return self.request.user.equipo is None

    def handle_no_permission(self):
        messages.warning(self.request, "Ya tienes un equipo.")
        return redirect('equipos:mi_equipo')


class PlayerOwnsTeamMixin(PlayerRequiredMixin):
    """Verifica que el jugador sea dueño del equipo que intenta ver/borrar."""

    def get_object(self, queryset=None):
        # Devuelve el equipo del usuario logueado para usar en test_func
        return self.request.user.equipo

    def test_func(self):
        if not super().test_func():
            return False

        equipo = self.request.user.equipo
        # El mixin base de DetailView/DeleteView necesita un objeto para test_func
        return equipo is not None

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado o no tienes equipo.")
        return redirect(reverse_lazy('equipos:mi_equipo'))


class AdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verifica que el usuario sea un 'ADMIN'"""

    def test_func(self):
        return self.request.user.tipo_usuario == 'ADMIN'

    def handle_no_permission(self):
        messages.error(self.request, "Acceso denegado: solo administradores.")
        return redirect(reverse_lazy('core:home'))


# --- Vistas de Autocompletado (NUEVAS) ---


class JugadorAutocomplete(autocomplete.Select2QuerySetView):
    """
    Vista AJAX que devuelve jugadores de la misma división para el autocompletado.
    """

    def get_queryset(self):
        # Aseguramos que solo los usuarios logueados puedan buscar
        if (
            not self.request.user.is_authenticated
            or self.request.user.tipo_usuario != 'PLAYER'
        ):
            return CustomUser.objects.none()

        user = self.request.user

        # 1. Base Query: Mismos filtros que en EquipoCreateForm (División y tipo)
        qs = CustomUser.objects.filter(
            division=user.division, tipo_usuario='PLAYER'
        ).exclude(
            id=user.id  # Excluirse a sí mismo
        )

        # 2. FILTRO CLAVE: Excluir a los jugadores que ya aparecen como jugador1 O jugador2 en CUALQUIER equipo
        # Usamos las relaciones inversas explícitas (related_name)
        qs = qs.exclude(
            Q(equipos_como_jugador1__isnull=False)
            | Q(equipos_como_jugador2__isnull=False)
        )

        # 3. Aplicamos el filtro de búsqueda del usuario (q)
        if self.q:
            # Búsqueda por nombre O apellido (Case insensitive: icontains)
            qs = qs.filter(Q(nombre__icontains=self.q) | Q(apellido__icontains=self.q))

        return qs


# --- Vistas de Jugador ---


class MiEquipoDetailView(LoginRequiredMixin, DetailView):
    model = Equipo
    template_name = 'equipos/mi_equipo_detail.html'
    context_object_name = 'equipo'

    def get_object(self, queryset=None):
        """Devuelve el equipo del usuario logueado con relaciones precargadas."""
        equipo = self.request.user.equipo
        if equipo:
            # Precarga jugador1, jugador2 y division para evitar queries extras
            return Equipo.objects.select_related(
                'jugador1', 'jugador2', 'division'
            ).get(pk=equipo.pk)
        return None

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object is None:
            messages.info(request, "Aún no tienes un equipo. ¡Crea uno!")
            return redirect('equipos:crear')

        # Redirigir a crear si no tiene equipo
        if not self.object:
            return redirect('equipos:crear')

        context = self.get_context_data(object=self.object)
        return self.render_to_response(context)


class EquipoCreateView(PlayerHasNoTeamMixin, CreateView):
    model = Equipo
    form_class = EquipoCreateForm
    template_name = 'equipos/equipo_form.html'
    success_url = reverse_lazy('equipos:mi_equipo')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Equipo"
        # ¡IMPORTANTE! Necesitamos el objeto usuario en el contexto
        context['user'] = self.request.user
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasamos el usuario logueado al formulario para filtrar la división
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # Asignamos al usuario logueado como jugador1
        form.instance.jugador1 = self.request.user
        messages.success(
            self.request,
            f"¡El equipo '{form.instance.nombre}' fue creado exitosamente!",
        )
        return super().form_valid(form)


class EquipoDeleteView(PlayerOwnsTeamMixin, DeleteView):
    model = Equipo
    template_name = 'equipos/equipo_confirm_delete.html'
    success_url = reverse_lazy('core:home')
    context_object_name = 'equipo'

    def get_object(self, queryset=None):
        # Obtenemos el equipo del usuario (validado por PlayerOwnsTeamMixin)
        return self.request.user.equipo

    def form_valid(self, form):
        messages.success(
            self.request, f"El equipo '{self.object.nombre}' ha sido disuelto."
        )
        return super().form_valid(form)


# --- Vistas de Admin ---


class AdminEquipoListView(AdminRequiredMixin, ListView):
    model = Equipo
    template_name = 'equipos/admin_equipo_list.html'
    context_object_name = 'equipos'
    paginate_by = 20

    def get_queryset(self):
        queryset = Equipo.objects.all().select_related(
            'jugador1', 'jugador2', 'division'
        )

        # Filtro por división
        division_id = self.request.GET.get('division')
        if division_id:
            queryset = queryset.filter(division_id=division_id)

        # Búsqueda por nombre de equipo
        search_query = self.request.GET.get('search')
        if search_query:
            queryset = queryset.filter(nombre__icontains=search_query)

        return queryset.order_by('nombre')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['divisiones'] = Division.objects.all()
        context['current_division'] = self.request.GET.get('division')
        context['search_query'] = self.request.GET.get('search', '')
        return context
