from django.urls import path
from . import views

urlpatterns = [
    # Tela Principal
    path('app', views.dashboard_view, name='dashboard'),

    # APIs (CRUD) - Usadas pelo Javascript do Dashboard
    path('servicos/', views.api_servicos, name='api_servicos_create'),
    path('servicos/<int:item_id>', views.api_servicos, name='api_servicos_edit'),
    
    path('categorias/', views.api_categorias, name='api_categorias_create'),     # Rota Adicionada
    path('categorias/<int:item_id>', views.api_categorias, name='api_categorias_edit'), # Rota Adicionada

    path('profissionais/', views.api_profissionais, name='api_profissionais_create'),
    path('profissionais/<int:item_id>', views.api_profissionais, name='api_profissionais_edit'),
    
    path('feriados/', views.api_feriados, name='api_feriados_create'), # Rota Adicionada
    path('feriados/<int:item_id>', views.api_feriados, name='api_feriados_edit'), # Rota Adicionada

    path('folgas-individuais/', views.api_folgas, name='api_folgas_create'), # Rota Adicionada
    path('folgas-individuais/<int:item_id>', views.api_folgas, name='api_folgas_edit'), # Rota Adicionada

    path('agendamentos/<int:item_id>', views.api_agendamentos, name='api_agendamentos_edit'), # Rota Adicionada

    path('saloes/<int:salon_id>', views.api_configuracoes, name='api_config'),

    # ROTA PARA O PARCIAL (HTML da tabela)
    path('partials/agendamentos', views.htmx_agendamentos, name='partial_agendamentos'),

    # ROTA PARA O "OUVIDO" (SSE) - NOVA
    path('events/stream', views.sse_updates, name='sse_stream'),
    
    # Rota genérica para deletar (Mantenha sempre por último)
    path('<str:tipo>/<int:item_id>', views.api_delete_item, name='api_delete'),
]