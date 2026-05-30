from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('para-organizadores/', views.ParaOrganizadoresView.as_view(), name='para_organizadores'),
    path('search/', views.GlobalSearchView.as_view(), name='search'),
    path('trigger-migration/', views.trigger_migration, name='trigger_migration'),
]
