from django.contrib import admin

from .models import Testimonio


@admin.register(Testimonio)
class TestimonioAdmin(admin.ModelAdmin):
    list_display = ('autor', 'rol', 'activo', 'orden')
    list_editable = ('activo', 'orden')
    list_filter = ('activo',)
    search_fields = ('autor', 'texto')
