from django.urls import path
from . import views

urlpatterns = [
    # Esta rota capturará /agendar/nome-da-barbearia
    path('<slug:slug>', views.pagina_agendamento, name='agendar_publico'),
    
    # APIs Públicas para o calendário
    path('saloes/<slug:slug>/profissionais-por-servico/<int:service_id>', views.api_profissionais_por_servico),
    path('saloes/<slug:slug>/disponibilidade/<str:data_iso>', views.api_disponibilidade),
    path('saloes/<slug:slug>/agendar', views.api_confirmar_agendamento),
]