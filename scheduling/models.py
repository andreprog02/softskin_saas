from django.db import models
from core.models import Salon

class Category(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    def __str__(self): return self.nome

class Service(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='services')
    nome = models.CharField(max_length=100)
    preco = models.DecimalField(max_digits=10, decimal_places=2)
    duracao_minutos = models.IntegerField()
    category = models.ForeignKey('Category', on_delete=models.SET_NULL, null=True, blank=True, related_name='services')

    def __str__(self):
        return f"{self.nome} ({self.salon.nome})"

class Professional(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE, related_name='professionals')
    nome = models.CharField(max_length=100)
    especialidade = models.CharField(max_length=100, blank=True, null=True)
    services = models.ManyToManyField(Service, related_name='professionals', blank=True)
    # NOVO CAMPO
    foto = models.ImageField(upload_to='profissionais/', blank=True, null=True)
    
    def __str__(self):
        return self.nome

class WorkingHour(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="working_hours")
    day_of_week = models.IntegerField() # 0=Segunda, 6=Domingo
    start_time = models.TimeField()
    end_time = models.TimeField()

class ProfessionalBreak(models.Model):
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE, related_name="breaks")
    day_of_week = models.IntegerField()
    start_time = models.TimeField()
    end_time = models.TimeField()

class SpecialSchedule(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE)
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    data = models.DateField()
    hora_inicio = models.TimeField(null=True, blank=True)
    hora_fim = models.TimeField(null=True, blank=True)

# A CLASSE QUE ESTAVA FALTANDO ESTÁ AQUI ABAIXO:
class Holiday(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE)
    data = models.DateField()
    descricao = models.CharField(max_length=255)

class Appointment(models.Model):
    salon = models.ForeignKey(Salon, on_delete=models.CASCADE)
    professional = models.ForeignKey(Professional, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.SET_NULL, null=True)
    
    cliente_nome = models.CharField(max_length=255)
    cliente_whatsapp = models.CharField(max_length=20)

    codigo_validacao = models.CharField(max_length=10, blank=True, null=True)
    
    data = models.DateField()
    hora_inicio = models.TimeField()
    
    class Meta:
        unique_together = ('professional', 'data', 'hora_inicio')

    def __str__(self):
        return f"{self.cliente_nome} - {self.data} {self.hora_inicio}"