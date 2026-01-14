from django.urls import path
from . import views

urlpatterns = [
    # Note as barras '/' no final de cada rota
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
]