from django.shortcuts import render

# Create your views here.
import json
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils.text import slugify
from django.http import JsonResponse
from .models import Salon, User

def login_view(request):
    if request.method == "POST":
        # CORREÇÃO: O HTML envia 'username' e 'password', não 'email' e 'senha'
        email = request.POST.get("username")
        senha = request.POST.get("password")
        
        # Boa prática: Forçar minúsculas no email para evitar erro de caixa alta/baixa
        if email:
            email = email.lower()

        # O Django espera o 'username', que no seu caso é o email
        user = authenticate(request, username=email, password=senha)
        
        if user:
            login(request, user)
            return redirect("dashboard")
        else:
            return render(request, "auth/login.html", {"erro": "E-mail ou senha incorretos."})
    
    return render(request, "auth/login.html")

def logout_view(request):
    logout(request)
    return redirect("login")

def signup_view(request):
    if request.method == "POST":
        nome_salao = request.POST.get("nome_salao")
        email = request.POST.get("email")
        senha = request.POST.get("senha")
        senha2 = request.POST.get("senha2")
        cor_tema = request.POST.get("cor_tema")

        if senha != senha2:
            return render(request, "auth/signup.html", {"erro": "Senhas não conferem"})
        
        if User.objects.filter(username=email).exists():
            return render(request, "auth/signup.html", {"erro": "E-mail já cadastrado"})

        # Lógica de Slug único
        base_slug = slugify(nome_salao)
        slug = base_slug
        counter = 1
        while Salon.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        # Criação Transacional (Salão + Dono)
        salao = Salon.objects.create(
            nome=nome_salao, 
            slug=slug, 
            cor_do_tema=cor_tema if cor_tema else "#8E44AD"
        )
        
        user = User.objects.create_user(username=email, email=email, password=senha)
        user.salon = salao
        user.is_salon_admin = True
        user.save()

        login(request, user)
        return redirect("dashboard")

    return render(request, "auth/signup.html")