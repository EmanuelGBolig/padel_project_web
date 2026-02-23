from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, DeleteView, ListView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages
from .models import Equipo, Invitation
from accounts.models import Division, CustomUser
from .forms import EquipoCreateForm
from django.db.models import Q
from django.db import models, transaction

# IMPORTANTE: Importar las vistas de autocompletado
from dal import autocomplete


# --- Mixins de Permisos ---
class PlayerRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Verifica que el usuario sea un 'PLAYER'"""

    def test_func(self):
        return self.request.user.tipo_usuario in ['PLAYER', 'ADMIN']

    def handle_no_permission(self):
        messages.error(
            self.request, "Debes ser un jugador o administrador para acceder a esta sección."
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
            import operator
            from functools import reduce
            keywords = self.q.split()
            if keywords:
                # Para cada palabra clave, debe coincidir en nombre O apellido
                q_list = [Q(nombre__icontains=kw) | Q(apellido__icontains=kw) for kw in keywords]
                query = reduce(operator.and_, q_list)
                qs = qs.filter(query)

        return qs

    def get_result_label(self, item):
        """
        Personalizar la etiqueta que se muestra en el dropdown.
        Mostrar: Nombre Apellido (email)
        """
        return f"{item.full_name} ({item.email})"


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
        
        # Si tiene equipo, mostrar detalle
        if self.object:
            context = self.get_context_data(object=self.object)
            return self.render_to_response(context)

        # Si NO tiene equipo, verificar si tiene invitaciones pendientes enviadas o recibidas
        invitaciones_enviadas = request.user.sent_invitations.filter(status=Invitation.Status.PENDING)
        invitaciones_recibidas = request.user.received_invitations.filter(status=Invitation.Status.PENDING)
        
        if invitaciones_enviadas.exists() or invitaciones_recibidas.exists():
            messages.info(request, "No tienes equipo, pero tienes invitaciones pendientes. Revisa tu perfil.")
            return redirect('accounts:perfil')

        messages.info(request, "Aún no tienes un equipo. ¡Crea uno!")
        return redirect('equipos:crear')
    
    def get_context_data(self, **kwargs):
        """Añade estadísticas del equipo al contexto"""
        context = super().get_context_data(**kwargs)
        equipo = self.get_object()
        
        if equipo:
            context['stats'] = {
                'partidos_jugados': equipo.get_partidos_jugados()['total'],
                'victorias': equipo.get_victorias(),
                'derrotas': equipo.get_derrotas(),
                'win_rate': equipo.get_win_rate(),
                'torneos_ganados': equipo.get_torneos_ganados(),
                'racha': equipo.get_racha_actual(),
                'ultimos_resultados': equipo.get_ultimos_resultados(),
            }
        
        return context


class EquipoCreateView(PlayerHasNoTeamMixin, CreateView):
    model = Equipo
    form_class = EquipoCreateForm
    template_name = 'equipos/equipo_form.html'
    success_url = reverse_lazy('accounts:perfil')  # Redirige a perfil para ver estado invitación

    def dispatch(self, request, *args, **kwargs):
        if not request.user.division:
            messages.error(request, "Debes tener una división asignada para crear un equipo. Edita tu perfil.")
            return redirect('accounts:perfil')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Nuevo Equipo"
        # ¡IMPORTANTE! Necesitamos el objeto usuario en el contexto
        context['user'] = self.request.user
        return context

    def get_initial(self):
        initial = super().get_initial()
        partner_id = self.request.GET.get('partner')
        if partner_id:
            try:
                # Add initial data for the ModelMultipleChoiceField
                initial['jugador2'] = [int(partner_id)]
            except ValueError:
                pass
        return initial

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Pasamos el usuario logueado al formulario para filtrar la división
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        # NO guardamos el equipo. Creamos una invitación.
        jugador2 = form.cleaned_data['jugador2']
        
        # Verificar si ya existe una invitación pendiente a este usuario
        existing_invitation = Invitation.objects.filter(
            inviter=self.request.user,
            invited=jugador2,
            status=Invitation.Status.PENDING
        ).exists()
        
        if existing_invitation:
            messages.warning(self.request, f"Ya tienes una invitación pendiente enviada a {jugador2.full_name}.")
            return redirect('accounts:perfil')

        # Crear invitación
        invitation = Invitation.objects.create(
            inviter=self.request.user,
            invited=jugador2,
            status=Invitation.Status.PENDING
        )
        
        # Enviar email de notificación
        from accounts.utils import send_email_async
        
        # Construir URL absoluta para el botón del email
        protocol = 'https' if self.request.is_secure() else 'http'
        domain = self.request.get_host()
        action_url = f"{protocol}://{domain}{reverse_lazy('accounts:perfil')}"

        send_email_async(
            subject=f'TodoPadel: {self.request.user.full_name} te invitó a un equipo',
            html_template='equipos/emails/invitation_email.html',
            context={
                'inviter': self.request.user,
                'invited': jugador2,
                'action_url': action_url
            },
            recipient_list=[jugador2.email]
        )

        messages.success(
            self.request,
            f"¡Invitación enviada a {jugador2.full_name}! El equipo se creará cuando acepte."
        )
        return redirect(self.success_url)


class AceptarInvitacionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        invitation = get_object_or_404(Invitation, pk=pk, invited=request.user, status=Invitation.Status.PENDING)
        
        # Validar que ninguno tenga equipo ya
        if invitation.inviter.equipo or invitation.invited.equipo:
            messages.error(request, "Uno de los jugadores ya tiene equipo. La invitación no puede aceptarse.")
            invitation.status = Invitation.Status.REJECTED
            invitation.save()
            return redirect('accounts:perfil')
            
        # Validar que el invitador tenga división asignada
        if not invitation.inviter.division:
            messages.error(request, "El jugador que te invitó no tiene una división asignada. No se puede crear el equipo.")
            return redirect('accounts:perfil')

        with transaction.atomic():
            # 1. Crear el equipo
            equipo = Equipo.objects.create(
                jugador1=invitation.inviter,
                jugador2=invitation.invited,
                division=invitation.inviter.division
            )
            
            # FIX: Borrar invitaciones previas ACEPTADAS entre estos mismos usuarios para evitar error de unicidad
            Invitation.objects.filter(
                inviter=invitation.inviter,
                invited=invitation.invited,
                status=Invitation.Status.ACCEPTED
            ).delete()

            # 2. Marcar invitación como aceptada
            invitation.status = Invitation.Status.ACCEPTED
            invitation.save()
            
            # 3. Cancelar todas las otras invitaciones pendientes que involucren a estos usuarios
            # (Ya sea como inviter o invited)
            users = [invitation.inviter, invitation.invited]
            Invitation.objects.filter(
                Q(inviter__in=users) | Q(invited__in=users),
                status=Invitation.Status.PENDING
            ).exclude(pk=invitation.pk).update(status=Invitation.Status.REJECTED)

        messages.success(request, f"¡Invitación aceptada! Equipo '{equipo.nombre}' creado exitosamente.")
        return redirect('equipos:mi_equipo')


class RechazarInvitacionView(LoginRequiredMixin, View):
    def post(self, request, pk):
        # Puede rechazar quien la recibe O cancelar quien la envió
        invitation = get_object_or_404(Invitation, pk=pk)
        
        if request.user != invitation.invited and request.user != invitation.inviter:
             messages.error(request, "No tienes permiso para realizar esta acción.")
             return redirect('accounts:perfil')
             
        if invitation.status != Invitation.Status.PENDING:
             messages.error(request, "Esta invitación ya no está pendiente.")
             return redirect('accounts:perfil')

        invitation.status = Invitation.Status.REJECTED
        invitation.save()
        
        if request.user == invitation.inviter:
            messages.success(request, "Invitación cancelada.")
        else:
            messages.info(request, "Invitación rechazada.")
            
        return redirect('accounts:perfil')


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


# --- Vista de Rankings ---


class RankingListView(ListView):
    model = Equipo
    template_name = 'equipos/ranking_list.html'
    context_object_name = 'rankings_por_division'
    
    def get_queryset(self):
        from django.db.models import Count, Q, F, Case, When, IntegerField, FloatField, Value
        from django.core.cache import cache
        
        # Obtener división seleccionada del parámetro GET
        # Obtener división seleccionada del parámetro GET
        division_id = self.request.GET.get('division')
        
        # Si no hay división seleccionada, usar la del usuario o la primera
        if not division_id:
            if self.request.user.is_authenticated and hasattr(self.request.user, 'equipo') and self.request.user.equipo:
                 division_id = self.request.user.equipo.division.id
            elif self.request.user.is_authenticated and self.request.user.division:
                 division_id = self.request.user.division.id
            else:
                first_div = Division.objects.first()
                if first_div:
                    division_id = first_div.id

        # Filtrar divisiones (Solo UNA a la vez)
        if division_id:
            divisiones = Division.objects.filter(id=division_id)
        else:
            divisiones = Division.objects.none()

        rankings_por_division = []
        
        for division in divisiones:
            # --- LÓGICA DE RANKING POR DIVISIÓN (OPTIMIZADA) ---
            # Filtrar equipos que PERTENECEN a esta división
            # Filtrar equipos que PERTENECEN a esta división O que hayan jugado en un torneo de esta división
            equipos_con_stats = Equipo.objects.filter(
                Q(division=division) |
                Q(partidos_bracket_e1__torneo__division=division) |
                Q(partidos_grupo_e1__grupo__torneo__division=division)
            ).distinct().select_related(
                'jugador1', 'jugador2', 'division'
            ).annotate(
                # 1. Victorias en Eliminación (Solo torneos de esta división)
                victorias_eliminacion=Count(
                    'partidos_bracket_ganados',
                    filter=Q(
                        partidos_bracket_ganados__isnull=False,
                        partidos_bracket_ganados__torneo__division=division
                    ),
                    distinct=True
                ),
                # 2. Victorias en Grupos (Solo torneos de esta división)
                victorias_grupo=Count(
                    'partidos_grupo_ganados',
                    filter=Q(
                        partidos_grupo_ganados__isnull=False,
                        partidos_grupo_ganados__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                # 3. Partidos jugados en Eliminación (Solo torneos de esta división)
                partidos_elim_1=Count(
                    'partidos_bracket_e1',
                    filter=Q(
                        partidos_bracket_e1__ganador__isnull=False,
                        partidos_bracket_e1__torneo__division=division
                    ),
                    distinct=True
                ),
                partidos_elim_2=Count(
                    'partidos_bracket_e2',
                    filter=Q(
                        partidos_bracket_e2__ganador__isnull=False,
                        partidos_bracket_e2__torneo__division=division
                    ),
                    distinct=True
                ),
                # 4. Partidos jugados en Grupos (Solo torneos de esta división)
                partidos_grupo_1=Count(
                    'partidos_grupo_e1',
                    filter=Q(
                        partidos_grupo_e1__ganador__isnull=False,
                        partidos_grupo_e1__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                partidos_grupo_2=Count(
                    'partidos_grupo_e2',
                    filter=Q(
                        partidos_grupo_e2__ganador__isnull=False,
                        partidos_grupo_e2__grupo__torneo__division=division
                    ),
                    distinct=True
                ),
                # 5. Torneos Ganados (Solo de esta división)
                torneos_ganados_count=Count(
                    'torneos_ganados',
                    filter=Q(torneos_ganados__division=division),
                    distinct=True
                )
            )
            
            # Procesar equipos y calcular métricas
            equipos_con_puntos = []
            for equipo in equipos_con_stats:
                # Calcular totales
                victorias_total = equipo.victorias_eliminacion + equipo.victorias_grupo
                partidos_total = (equipo.partidos_elim_1 + equipo.partidos_elim_2 + 
                                 equipo.partidos_grupo_1 + equipo.partidos_grupo_2)
                
                # Calcular win rate
                win_rate = 0
                if partidos_total > 0:
                    win_rate = round((victorias_total / partidos_total) * 100, 1)
                
                # Calcular puntos de ranking
                puntos = victorias_total * 3  # 3 puntos por victoria
                puntos += equipo.torneos_ganados_count * 50  # 50 puntos por torneo ganado
                
                # Bonus por win rate alto (Solo si jugó suficientes partidos en esta división)
                if win_rate >= 75 and partidos_total >= 5:
                    puntos += 20
                
                # Mostrar el equipo SIEMPRE que sea de esta división (ya filtrado por query)
                equipos_con_puntos.append({
                    'equipo': equipo,
                    'puntos': puntos,
                    'victorias': victorias_total,
                    'win_rate': win_rate,
                    'torneos_ganados': equipo.torneos_ganados_count,
                    'partidos_jugados': partidos_total
                })
            
            # Ordenar por puntos
            equipos_con_puntos.sort(key=lambda x: x['puntos'], reverse=True)
            
            # Agregar posición
            for i, item in enumerate(equipos_con_puntos, 1):
                item['posicion'] = i
            
            # Agregar a la lista final
            rankings_por_division.append({
                'division': division,
                'equipos': equipos_con_puntos
            })
        
        # Guardar en cache por 5 minutos (solo para esta vista específica)
        # Nota: La cache key debería cambiar si se usa paginación/filtros distintos, 
        # pero aquí estamos filtrando por división.
        # cache.set(cache_key, rankings_por_division, 300) 
        
        return rankings_por_division
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar todas las divisiones para el filtro (Dropdown)
        context['divisiones'] = Division.objects.all().order_by('nombre')
        
        # Determinar la división seleccionada para marcar en el select
        division_id = self.request.GET.get('division')
        if not division_id:
             if self.request.user.is_authenticated and hasattr(self.request.user, 'equipo') and self.request.user.equipo:
                 division_id = str(self.request.user.equipo.division.id)
             elif self.request.user.is_authenticated and self.request.user.division:
                 division_id = str(self.request.user.division.id)
             else:
                first = Division.objects.first()
                if first:
                    division_id = str(first.id)
        
        context['division_seleccionada'] = division_id
        
        # Agregar información del equipo del usuario si está autenticado
        if self.request.user.is_authenticated and hasattr(self.request.user, 'equipo') and self.request.user.equipo:
            context['mi_equipo'] = self.request.user.equipo
        
        return context

