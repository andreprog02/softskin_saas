from django.db import models
from django.contrib.auth.models import AbstractUser, Group, Permission

class Salon(models.Model):
    nome = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    logo_url = models.URLField(blank=True, null=True)
    cnpj_cpf = models.CharField(max_length=20, blank=True, null=True)
    endereco = models.JSONField(default=dict, blank=True)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    
    # Configurações
    cor_do_tema = models.CharField(max_length=7, default="#8E44AD")
    hora_abertura_padrao = models.TimeField(default="09:00")
    hora_fechamento_padrao = models.TimeField(default="18:00")
    intervalo_minutos = models.IntegerField(default=30)
    dias_fechados = models.CharField(max_length=50, default="0")
    ocultar_precos = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.nome

class User(AbstractUser):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name="users", null=True, blank=True)
    is_salon_admin = models.BooleanField(default=False)

    # --- CORREÇÃO DO CONFLITO ABAIXO ---
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to.',
        related_name="core_user_groups",  # Nome exclusivo para evitar conflito
        related_query_name="core_user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="core_user_permissions",  # Nome exclusivo para evitar conflito
        related_query_name="core_user",
    )