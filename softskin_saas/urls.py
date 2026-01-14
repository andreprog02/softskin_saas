from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Sistema de Login/Senha do Django
    path('accounts/', include('django.contrib.auth.urls')),
    
    # Suas views de autenticação personalizadas
    path('api/v1/login/', views.login_view, name='login'),
    path('api/v1/signup/', views.signup_view, name='signup'),
    
    # Inclusão dos outros arquivos de URL (CUIDADO AQUI)
    # Garanta que você está chamando os arquivos das PASTAS dos APPS
    path('api/v1/', include('core.urls')), 
    path('api/v1/', include('dashboard.urls')),
    
    # Rota de Agendamento Pública
    path('agendar/', include('booking.urls')), 
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)