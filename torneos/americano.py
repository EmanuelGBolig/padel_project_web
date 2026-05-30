"""Vistas y scheduler del formato Americano/Mexicano (TP-09).

Se juega a nivel de jugador individual, en canchas/grupos de 4 (cada ronda = N/4
partidos). El puntaje de cada jugador es la suma de games ganados.
"""

from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages

from .models import Americano, JugadorAmericano, RondaAmericano, PartidoAmericano
from .forms import AmericanoForm, JugadorAmericanoForm


class AdminOrOrganizerMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Acceso para admins y organizadores."""

    def test_func(self):
        u = self.request.user
        return u.is_authenticated and (u.is_staff or u.tipo_usuario in ('ADMIN', 'ORGANIZER'))

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            messages.error(self.request, "Acceso denegado: solo administradores u organizadores.")
            return redirect('core:home')
        return super().handle_no_permission()


def generar_ronda_americano(americano, numero, jugadores):
    """Crea una ronda con N/4 partidos. `jugadores` ordenado, largo múltiplo de 4.

    Americano rota compañeros según 3 pairings; Mexicano arma fuerte+débil vs medios
    sobre el orden por ranking recibido.
    """
    ronda = RondaAmericano.objects.create(americano=americano, numero=numero)
    pairing = (numero - 1) % 3
    grupos = [jugadores[i:i + 4] for i in range(0, len(jugadores), 4)]
    for idx, grupo in enumerate(grupos, 1):
        a, b, c, d = grupo
        if americano.tipo == Americano.Tipo.MEXICANO:
            pa, pb = (a, d), (b, c)
        elif pairing == 0:
            pa, pb = (a, b), (c, d)
        elif pairing == 1:
            pa, pb = (a, c), (b, d)
        else:
            pa, pb = (a, d), (b, c)
        PartidoAmericano.objects.create(
            ronda=ronda, cancha=idx,
            a1=pa[0], a2=pa[1], b1=pb[0], b2=pb[1],
        )
    return ronda


class AmericanoListView(ListView):
    model = Americano
    template_name = 'torneos/americano_list.html'
    context_object_name = 'americanos'

    def get_queryset(self):
        return Americano.objects.all().prefetch_related('jugadores')


class AmericanoCreateView(AdminOrOrganizerMixin, CreateView):
    model = Americano
    form_class = AmericanoForm
    template_name = 'torneos/americano_form.html'

    def form_valid(self, form):
        user = self.request.user
        if not user.is_staff and getattr(user, 'organizacion_id', None):
            form.instance.organizacion = user.organizacion
        self.object = form.save()
        messages.success(self.request, "Americano creado. Compartí el link de inscripción.")
        return redirect('torneos:americano_manage', pk=self.object.pk)


class AmericanoDetailView(DetailView):
    model = Americano
    template_name = 'torneos/americano_detail.html'
    context_object_name = 'americano'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        am = self.object
        context['tabla'] = am.tabla()
        context['rondas'] = am.rondas.prefetch_related(
            'partidos__a1', 'partidos__a2', 'partidos__b1', 'partidos__b2'
        )
        context['join_url'] = self.request.build_absolute_uri(
            reverse_lazy('torneos:americano_join', kwargs={'codigo': am.codigo})
        )
        return context


class AmericanoJoinView(CreateView):
    """Inscripción pública por código, sin necesidad de cuenta."""
    model = JugadorAmericano
    form_class = JugadorAmericanoForm
    template_name = 'torneos/americano_join.html'

    def get_americano(self):
        return get_object_or_404(Americano, codigo=self.kwargs['codigo'])

    def dispatch(self, request, *args, **kwargs):
        self.americano = self.get_americano()
        if self.americano.estado != Americano.Estado.INSCRIPCION:
            messages.error(request, "La inscripción de este Americano está cerrada.")
            return redirect(self.americano.get_absolute_url())
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['americano'] = self.americano
        return context

    def form_valid(self, form):
        form.instance.americano = self.americano
        form.instance.orden = self.americano.jugadores.count()
        if self.request.user.is_authenticated:
            form.instance.user = self.request.user
        form.save()
        messages.success(self.request, "¡Inscripción confirmada! Ya estás anotado.")
        return redirect(self.americano.get_absolute_url())


class AmericanoManageView(AdminOrOrganizerMixin, DetailView):
    model = Americano
    template_name = 'torneos/americano_manage.html'
    context_object_name = 'americano'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        am = self.object
        context['jugadores'] = am.jugadores.all()
        context['num_jugadores'] = am.jugadores.count()
        context['rondas'] = am.rondas.prefetch_related(
            'partidos__a1', 'partidos__a2', 'partidos__b1', 'partidos__b2'
        )
        context['join_url'] = self.request.build_absolute_uri(
            reverse_lazy('torneos:americano_join', kwargs={'codigo': am.codigo})
        )
        return context

    def post(self, request, *args, **kwargs):
        am = self.get_object()
        action = request.POST.get('action')

        if action == 'iniciar':
            jugadores = list(am.jugadores.order_by('orden', 'id'))
            n = len(jugadores)
            if n < 4 or n % 4 != 0:
                messages.error(request, f"Se necesitan múltiplos de 4 jugadores (hay {n}).")
                return redirect('torneos:americano_manage', pk=am.pk)
            if am.estado != Americano.Estado.INSCRIPCION:
                messages.warning(request, "El Americano ya fue iniciado.")
                return redirect('torneos:americano_manage', pk=am.pk)
            am.rondas.all().delete()
            if am.tipo == Americano.Tipo.AMERICANO:
                # Rotación fija: 3 rondas (cada quien juega con los otros 3 de su cancha).
                for numero in range(1, 4):
                    generar_ronda_americano(am, numero, jugadores)
            else:
                # Mexicano: solo la 1ra ronda; las siguientes se arman por ranking.
                generar_ronda_americano(am, 1, jugadores)
            am.estado = Americano.Estado.EN_JUEGO
            am.save(update_fields=['estado'])
            messages.success(request, "¡Americano iniciado!")

        elif action == 'siguiente_ronda':
            if am.estado != Americano.Estado.EN_JUEGO:
                return redirect('torneos:americano_manage', pk=am.pk)
            am.recalcular_puntos()
            jugadores = list(am.tabla())
            numero = am.rondas.count() + 1
            generar_ronda_americano(am, numero, jugadores)
            messages.success(request, f"Ronda {numero} generada según el ranking.")

        elif action == 'cargar_resultado':
            try:
                partido = PartidoAmericano.objects.get(
                    pk=request.POST.get('partido_id'), ronda__americano=am
                )
                partido.games_a = int(request.POST.get('games_a') or 0)
                partido.games_b = int(request.POST.get('games_b') or 0)
                partido.cargado = True
                partido.save()
                am.recalcular_puntos()
                messages.success(request, "Resultado guardado.")
            except (PartidoAmericano.DoesNotExist, ValueError):
                messages.error(request, "No se pudo guardar el resultado.")

        elif action == 'finalizar':
            am.recalcular_puntos()
            am.estado = Americano.Estado.FINALIZADO
            am.save(update_fields=['estado'])
            messages.success(request, "Americano finalizado.")

        return redirect('torneos:americano_manage', pk=am.pk)
