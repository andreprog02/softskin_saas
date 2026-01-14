from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from core import views  # Certifique-se de que o app 'core' tem as views de login e signup

# Função para redirecionar a página inicial para o login caso não haja uma home pública
def redirect_to_login(request):
    return redirect('/api/v1/login/')

urlpatterns = [
    # Painel Administrativo do Django
    path('admin/', admin.site.urls),
    
    # Sistema padrão de autenticação (necessário para o 'password_reset')
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Rotas de Autenticação do seu SaaS
    path('api/v1/login/', views.login_view, name='login'),
    path('api/v1/signup/', views.signup_view, name='signup'),
    
    # Inclusão das URLs dos seus Apps
    path('api/v1/', include('core.urls')), 
    path('api/v1/', include('dashboard.urls')),
    path('api/v1/', include('scheduling.urls')), # Incluindo o app de agendamentos internos
    
    # Rota de Agendamento Pública (Acesso do Cliente Final)
    # O arquivo booking/urls.py deve conter apenas as rotas de agendar
    path('agendar/', include('booking.urls')), 
    
    # Redirecionamento da raiz (opcional)
    path('', redirect_to_login, name='root_redirect'),
]

# Configuração para arquivos de mídia e estáticos em ambiente de desenvolvimento
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)