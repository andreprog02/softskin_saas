from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# --- ROTEADOR AUTOMÁTICO (DRF) ---
# Substitui todas as rotas manuais de CRUD (GET, POST, PUT, DELETE)
router = DefaultRouter()
router.register(r'categorias', views.CategoryViewSet)
router.register(r'servicos', views.ServiceViewSet)
router.register(r'profissionais', views.ProfessionalViewSet)
router.register(r'feriados', views.HolidayViewSet)
router.register(r'folgas-individuais', views.SpecialScheduleViewSet)
router.register(r'agendamentos', views.AppointmentViewSet)

urlpatterns = [
    # 1. Tela Principal (HTML)
    path('app', views.dashboard_view, name='dashboard'),

    # 2. Rotas de Tempo Real (Mantidas do código antigo)
    path('partials/agendamentos', views.htmx_agendamentos, name='partial_agendamentos'),
    path('events/stream', views.sse_updates, name='sse_stream'),

    # 3. API de Configuração (Mantida manual pois é específica)
    # Adicionamos a barra '/' logo após <int:salon_id>
    path('saloes/<int:salon_id>/', views.api_configuracoes, name='api_config'),

    # 4. Inclui todas as rotas mágicas do Router
    # Isso cobre URLs como: /servicos/, /profissionais/1/, etc.
    path('', include(router.urls)),
]