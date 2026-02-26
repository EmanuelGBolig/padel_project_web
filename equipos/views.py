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
    
    def get_queryset(self, force_recalc=False):
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
            # Cache para esta división
            cache_key = f'rankings_equipos_div_{division.id}'
            from django.core.cache import cache as dj_cache
            
            if not force_recalc:
                cached = dj_cache.get(cache_key)
                if cached is not None:
                    rankings_por_division.append({'division': division, 'equipos': cached})
                    continue

                from equipos.models import RankingEquipo
                rankings_db = RankingEquipo.objects.filter(division=division).select_related('equipo', 'equipo__jugador1', 'equipo__jugador2').order_by('-puntos', '-torneos_ganados', '-victorias')

                equipos_con_puntos = []
                for i, r in enumerate(rankings_db, 1):
                    win_rate = round((r.victorias / r.partidos_jugados) * 100, 1) if r.partidos_jugados > 0 else 0
                    equipos_con_puntos.append({
                        'equipo': r.equipo,
                        'puntos': r.puntos,
                        'victorias': r.victorias,
                        'win_rate': win_rate,
                        'torneos_ganados': r.torneos_ganados,
                        'partidos_jugados': r.partidos_jugados,
                        'posicion': i
                    })
                
                dj_cache.set(cache_key, equipos_con_puntos, 300)
                rankings_por_division.append({'division': division, 'equipos': equipos_con_puntos})
                continue

            # --- LÓGICA OPTIMIZADA: consultas simples en vez de mega-JOINs ---
            from torneos.models import Partido, PartidoGrupo, Torneo as TorneoModel

            torneo_ids = list(TorneoModel.objects.filter(division=division).values_list('id', flat=True))

            if not torneo_ids:
                # Sin torneos: listar solo equipos de la división con 0 puntos
                equipos_vacios = Equipo.objects.filter(division=division).select_related('jugador1', 'jugador2', 'division')
                equipos_con_puntos = [{'equipo': e, 'puntos': 0, 'victorias': 0, 'win_rate': 0, 'torneos_ganados': 0, 'partidos_jugados': 0} for e in equipos_vacios]
                for i, item in enumerate(equipos_con_puntos, 1):
                    item['posicion'] = i
                dj_cache.set(cache_key, equipos_con_puntos, 300)
                rankings_por_division.append({'division': division, 'equipos': equipos_con_puntos})
                continue

            # 1. Victorias en partidos de grupo (15 puntos por victoria)
            vict_grupo = (
                PartidoGrupo.objects.filter(grupo__torneo_id__in=torneo_ids, ganador__isnull=False)
                .values('ganador_id')
                .annotate(wins=Count('id'))
            )

            # 2. Partidos jugados bracket
            part_bracket = (
                Partido.objects.filter(torneo_id__in=torneo_ids, ganador__isnull=False)
                .values('equipo1_id', 'equipo2_id', 'ganador_id')
            )
            # 3. Partidos jugados grupo
            part_grupo = (
                PartidoGrupo.objects.filter(grupo__torneo_id__in=torneo_ids, ganador__isnull=False)
                .values('equipo1_id', 'equipo2_id')
            )

            # 4. Puntos por Bracket (Ronda máxima alcanzada)
            bracket_matches = Partido.objects.filter(
                torneo_id__in=torneo_ids, equipo1__isnull=False, equipo2__isnull=False, ganador__isnull=False
            ).values(
                'torneo_id', 'ronda', 'equipo1_id', 'equipo2_id'
            )
            
            # Campeones de torneos
            t_ganados = TorneoModel.objects.filter(id__in=torneo_ids, ganador_del_torneo__isnull=False).values(
                'id', 'ganador_del_torneo_id'
            )

            # Agregar en Python
            victorias_por_equipo = {}
            partidos_por_equipo = {}
            puntos_por_equipo = {}
            torneos_ganados_por_equipo = {}

            # Helpers para acumular
            def add_victorias(eid, count):
                if eid: victorias_por_equipo[eid] = victorias_por_equipo.get(eid, 0) + count

            def add_partidos(eid, count):
                if eid: partidos_por_equipo[eid] = partidos_por_equipo.get(eid, 0) + count

            def add_puntos(eid, pts):
                if eid: puntos_por_equipo[eid] = puntos_por_equipo.get(eid, 0) + pts

            def add_torneo(eid):
                if eid: torneos_ganados_por_equipo[eid] = torneos_ganados_por_equipo.get(eid, 0) + 1

            for v in vict_grupo:
                add_victorias(v['ganador_id'], v['wins'])
                add_puntos(v['ganador_id'], v['wins'] * 15)

            for p in part_bracket:
                add_partidos(p['equipo1_id'], 1)
                add_partidos(p['equipo2_id'], 1)
                add_victorias(p['ganador_id'], 1)

            for p in part_grupo:
                add_partidos(p['equipo1_id'], 1)
                add_partidos(p['equipo2_id'], 1)

            # Campeones por Torneo
            campeones = {}
            for t in t_ganados:
                tid = t['id']
                ganador = t['ganador_del_torneo_id']
                campeones[tid] = ganador
                add_torneo(ganador)

            # Max ronda por equipo y torneo
            max_ronda_equipo_torneo = {} # {torneo_id: {equipo_id: max_ronda}}
            for bm in bracket_matches:
                tid = bm['torneo_id']
                ronda = bm['ronda']
                if tid not in max_ronda_equipo_torneo:
                    max_ronda_equipo_torneo[tid] = {}
                
                for el in ['equipo1_id', 'equipo2_id']:
                    eid = bm[el]
                    if eid:
                        curr = max_ronda_equipo_torneo[tid].get(eid, 0)
                        if ronda > curr:
                            max_ronda_equipo_torneo[tid][eid] = ronda

            # Asignar Puntos de Bracket
            for tid, equipos_rondas in max_ronda_equipo_torneo.items():
                campeon_torneo = campeones.get(tid)
                for eid, max_ronda in equipos_rondas.items():
                    if eid == campeon_torneo:
                        add_puntos(eid, 600)
                    else:
                        if max_ronda == 4:
                            add_puntos(eid, 360) # Finalista
                        elif max_ronda == 3:
                            add_puntos(eid, 180) # Semifinal
                        elif max_ronda == 2:
                            add_puntos(eid, 90)  # Cuartos
                        elif max_ronda == 1:
                            add_puntos(eid, 45)  # Octavos

            # Obtener todos los equipos relevantes
            equipo_ids_con_datos = (
                set(victorias_por_equipo.keys()) |
                set(partidos_por_equipo.keys()) |
                set(torneos_ganados_por_equipo.keys()) |
                set(puntos_por_equipo.keys())
            )
            
            equipos_qs = Equipo.objects.filter(
                Q(division=division) | Q(id__in=equipo_ids_con_datos)
            ).distinct().select_related('jugador1', 'jugador2', 'division')

            equipos_con_puntos = []
            for equipo in equipos_qs:
                victorias = victorias_por_equipo.get(equipo.id, 0)
                partidos = partidos_por_equipo.get(equipo.id, 0)
                t_gan = torneos_ganados_por_equipo.get(equipo.id, 0)
                puntos = puntos_por_equipo.get(equipo.id, 0)
                
                win_rate = round((victorias / partidos) * 100, 1) if partidos > 0 else 0
                
                equipos_con_puntos.append({
                    'equipo': equipo,
                    'puntos': puntos,
                    'victorias': victorias,
                    'win_rate': win_rate,
                    'torneos_ganados': t_gan,
                    'partidos_jugados': partidos,
                })

            # Ordenar por el mismo criterio que jugadores
            equipos_con_puntos.sort(
                key=lambda x: (
                    x['puntos'],
                    x['torneos_ganados'],
                    x['win_rate'],
                    x['victorias']
                ),
                reverse=True
            )
            
            for i, item in enumerate(equipos_con_puntos, 1):
                item['posicion'] = i

            dj_cache.set(cache_key, equipos_con_puntos, 300)
            rankings_por_division.append({'division': division, 'equipos': equipos_con_puntos})
        
        return rankings_por_division

    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Agregar todas las divisiones para el filtro (Dropdown)
        context['divisiones'] = Division.objects.all().order_by('orden')
        
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


class OrganizadorJugadorAutocomplete(autocomplete.Select2QuerySetView):
    """
    Vista AJAX para que los organizadores busquen jugadores sin equipo.
    """
    def get_queryset(self):
        if not self.request.user.is_authenticated or self.request.user.tipo_usuario not in ['ADMIN', 'ORGANIZER']:
            return CustomUser.objects.none()

        qs = CustomUser.objects.filter(tipo_usuario='PLAYER')

        # Excluir a los que ya tienen equipo
        usuarios_con_equipo_ids = set(
            Equipo.objects.values_list('jugador1_id', flat=True)
        ).union(set(Equipo.objects.values_list('jugador2_id', flat=True)))
        
        qs = qs.exclude(id__in=usuarios_con_equipo_ids)

        if self.q:
            import operator
            from functools import reduce
            keywords = self.q.split()
            if keywords:
                q_list = [Q(nombre__icontains=kw) | Q(apellido__icontains=kw) for kw in keywords]
                query = reduce(operator.and_, q_list)
                qs = qs.filter(query)

        return qs

    def get_result_label(self, item):
        etiq_dummy = " [Dummy]" if item.is_dummy else ""
        return f"{item.full_name} ({item.division}){etiq_dummy}"


class OrganizadorEquipoCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Equipo
    from .forms import PairCreationForm
    form_class = PairCreationForm
    template_name = 'equipos/organizador_equipo_form.html'
    success_url = reverse_lazy('accounts:organizacion_settings')

    def test_func(self):
        return self.request.user.tipo_usuario in ['ADMIN', 'ORGANIZER']

    def handle_no_permission(self):
        messages.error(self.request, "Solo organizadores pueden acceder.")
        return redirect('core:home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = "Crear Pareja Manualmente"
        return context

    def form_valid(self, form):
        # Crear la pareja directamente sin usar invitación
        equipo = form.save(commit=False)
        equipo.save()
        messages.success(self.request, f"¡Pareja '{equipo.nombre}' creada con éxito!")
        return redirect(self.success_url)


