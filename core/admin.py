from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import Salon, User
from scheduling.models import Service, Professional, Appointment, WorkingHour

# Inline permite editar horários DENTRO da tela do Profissional
class WorkingHourInline(admin.TabularInline):
    model = WorkingHour
    extra = 1

@admin.register(Salon)
class SalonAdmin(admin.ModelAdmin):
    list_display = ('nome', 'slug', 'telefone', 'created_at')
    search_fields = ('nome', 'slug')

@admin.register(Professional)
class ProfessionalAdmin(admin.ModelAdmin):
    list_display = ('nome', 'salon', 'especialidade')
    list_filter = ('salon',) # Filtra por salão na lateral
    inlines = [WorkingHourInline] # Edita horários aqui mesmo!

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('data', 'hora_inicio', 'cliente_nome', 'professional', 'salon')
    list_filter = ('salon', 'data')
    date_hierarchy = 'data'