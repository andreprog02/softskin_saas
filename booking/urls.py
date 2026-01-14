from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from core import views # Certifique-se de que o import está correto para suas views

# Função de redirecionamento
def redirect_to_login(request):
    return redirect('/api/v1/login/')

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 1. Rotas de Autenticação (Recuperação de senha, etc)
    path('accounts/', include('django.contrib.auth.urls')),
    
    # 2. Rotas do seu App/API
    path('api/v1/login/', views.login_view, name='login'),
    path('api/v1/signup/', views.signup_view, name='signup'), # Exemplo
    path('api/v1/', include('core.urls')),
    path('api/v1/', include('dashboard.urls')),
    
    # 3. Rotas de Agendamento (Públicas)
    # Se o booking.urls tiver path('agendar/<slug:slug>', ...), 
    # aqui você deve decidir se quer um prefixo ou não.
    path('', include('booking.urls')), 
    
    # 4. Redirecionamento da Raiz (Apenas se a rota acima não capturar tudo)
    # Se você quer que a raiz vá para o login:
    # path('', redirect_to_login, name='root_redirect'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)