import json
import time
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

# DRF Imports
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

# Models & Serializers
from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Category, Holiday, SpecialSchedule, WorkingHour, ProfessionalBreak
from .serializers import ServiceSerializer, ProfessionalSerializer, CategorySerializer, HolidaySerializer, SpecialScheduleSerializer, AppointmentSerializer

# --- VIEWS DE RENDERIZAÇÃO (HTML) ---

@login_required
def dashboard_view(request):
    salao = request.user.salon
    
    # Buscas otimizadas para o template
    agendamentos = Appointment.objects.filter(salon=salao).order_by('-data', 'hora_inicio')
    categorias = Category.objects.filter(salon=salao)
    servicos = Service.objects.filter(salon=salao)
    feriados = Holiday.objects.filter(salon=salao)
    folgas = SpecialSchedule.objects.filter(salon=salao)

    # Montagem da estrutura complexa de profissionais para o template
    profs_db = Professional.objects.filter(salon=salao)
    profissionais_list = []
    for p in profs_db:
        whs = p.working_hours.all()
        escala = [{"day": h.day_of_week, "start": h.start_time.strftime("%H:%M"), "end": h.end_time.strftime("%H:%M")} for h in whs]
        
        breaks = p.breaks.all()
        unique_breaks = {(b.start_time.strftime("%H:%M"), b.end_time.strftime("%H:%M")) for b in breaks}
        intervalos = [{"start": s, "end": e} for s, e in unique_breaks]
        
        profissionais_list.append({
            "id": p.id,
            "nome": p.nome,
            "especialidade": p.especialidade,
            "servicos_ids": [s.id for s in p.services.all()],
            "escala": escala,
            "intervalos": intervalos,
            "foto_url": p.foto.url if p.foto else None
        })

    context = {
        "salao": salao,
        "agendamentos": agendamentos,
        "categorias": list(categorias.values()),
        "servicos": list(servicos.values()),
        "profissionais": profissionais_list,
        "feriados": list(feriados.values()),
        "folgas": list(folgas.values('id', 'data', 'hora_inicio', 'hora_fim', 'professional_id')),
        "tab": request.GET.get("tab", "agenda")
    }
    return render(request, "dashboard/index.html", context)

@login_required
def htmx_agendamentos(request):
    """Retorna o HTML parcial da tabela para atualização automática"""
    salao = request.user.salon
    agendamentos = Appointment.objects.filter(salon=salao).order_by('-data', 'hora_inicio')
    return render(request, "dashboard/partials/lista_agendamentos.html", {"agendamentos": agendamentos})

@login_required
def sse_updates(request):
    """Canal de SSE para notificar o frontend sobre mudanças"""
    def event_stream():
        last_count = Appointment.objects.count()
        while True:
            current_count = Appointment.objects.count()
            if current_count != last_count:
                last_count = current_count
                yield f"data: update\n\n"
            time.sleep(1)

    response = StreamingHttpResponse(event_stream(), content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response

# --- VIEWSETS (CRUD PADRONIZADO E SEGURO) ---

class BaseSalonViewSet(viewsets.ModelViewSet):
    """Base para garantir que o usuário só acesse dados do seu próprio salão"""
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return self.queryset.filter(salon=self.request.user.salon)

    def perform_create(self, serializer):
        serializer.save(salon=self.request.user.salon)

class CategoryViewSet(BaseSalonViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ServiceViewSet(BaseSalonViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

class HolidayViewSet(BaseSalonViewSet):
    queryset = Holiday.objects.all()
    serializer_class = HolidaySerializer

class SpecialScheduleViewSet(BaseSalonViewSet):
    queryset = SpecialSchedule.objects.all()
    serializer_class = SpecialScheduleSerializer

class AppointmentViewSet(BaseSalonViewSet):
    queryset = Appointment.objects.all()
    serializer_class = AppointmentSerializer

class ProfessionalViewSet(BaseSalonViewSet):
    queryset = Professional.objects.all()
    serializer_class = ProfessionalSerializer
    # Suporta JSON e Upload de Arquivos (Multipart)
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def create(self, request, *args, **kwargs):
        # CORREÇÃO: Garante que 'data' seja um dicionário, não importa a origem
        data = request.data.dict() if hasattr(request.data, 'dict') else request.data
        
        servicos_raw = data.get('servicos_ids')
        escala_raw = data.get('escala')
        intervalos_raw = data.get('intervalos')

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        professional = serializer.instance

        self._process_nested_data(professional, servicos_raw, escala_raw, intervalos_raw)
        
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # CORREÇÃO: Garante que 'data' seja um dicionário
        data = request.data.dict() if hasattr(request.data, 'dict') else request.data
        
        servicos_raw = data.get('servicos_ids')
        escala_raw = data.get('escala')
        intervalos_raw = data.get('intervalos')
        remover_foto = data.get('remover_foto')

        if str(remover_foto).lower() == 'true':
            instance.foto.delete(save=False)
            data['foto'] = None

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        self._process_nested_data(instance, servicos_raw, escala_raw, intervalos_raw)

        return Response(serializer.data)

    def _process_nested_data(self, professional, servicos_raw, escala_raw, intervalos_raw):
        """Processa os dados complexos (escalas, serviços) enviados pelo frontend"""
        # 1. Serviços (ManyToMany)
        if servicos_raw:
            try:
                ids = json.loads(servicos_raw) if isinstance(servicos_raw, str) else servicos_raw
                professional.services.set(ids)
            except Exception as e:
                print(f"Erro ao processar serviços: {e}")

        # 2. Escala (WorkingHour)
        if escala_raw:
            try:
                escala_data = json.loads(escala_raw) if isinstance(escala_raw, str) else escala_raw
                
                # Limpa e recria
                professional.working_hours.all().delete()
                professional.breaks.all().delete()
                
                dias = escala_data.get("dias", [])
                inicio = escala_data.get("inicio")
                fim = escala_data.get("fim")
                
                for dia in dias:
                    if inicio and fim:
                        WorkingHour.objects.create(
                            professional=professional, 
                            day_of_week=dia, 
                            start_time=inicio, 
                            end_time=fim
                        )
                
                # 3. Intervalos (ProfessionalBreak) - depende da escala ser processada
                if intervalos_raw:
                    intervalos_list = json.loads(intervalos_raw) if isinstance(intervalos_raw, str) else intervalos_raw
                    for i in intervalos_list:
                        for dia in dias: # Aplica intervalos nos dias de trabalho
                            ProfessionalBreak.objects.create(
                                professional=professional, 
                                day_of_week=dia, 
                                start_time=i["start"], 
                                end_time=i["end"]
                            )
            except Exception as e:
                print(f"Erro ao processar escala: {e}")

# --- API MANUAL (Configurações Específicas) ---
# Mantida separada pois lida com atualização parcial de campos específicos do Salon

@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def api_configuracoes(request, salon_id):
    salao = request.user.salon
    if salao.id != int(salon_id):
        return Response({"error": "Forbidden"}, status=403)
    
    data = request.data
    allowed = ["nome", "cnpj_cpf", "telefone", "hora_abertura_padrao", "hora_fechamento_padrao", "intervalo_minutos", "dias_fechados", "cor_do_tema", "ocultar_precos", "endereco", "horarios_customizados"]
    
    for k, v in data.items():
        if k in allowed:
            # Se for endereço e vier como dicionário, converte pra JSON string se seu model espera string
            # Se seu model espera JSONField, pode passar direto. Assumindo TextField/CharField com JSON:
            if k == 'endereco' and isinstance(v, dict):
                setattr(salao, k, json.dumps(v))
            else:
                setattr(salao, k, v)
    
    salao.save()
    return Response({"ok": True})