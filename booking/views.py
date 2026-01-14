import json
import random # Added missing import
import string # Added missing import
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Holiday, SpecialSchedule, WorkingHour, ProfessionalBreak, Category

# --- FUNÇÃO AUXILIAR DE DISPONIBILIDADE ---
def check_slot_availability(salao, prof, svc, date_obj, slot_time_obj):
    # 1. Checa dia fechado do salão
    weekday = date_obj.weekday()
    if salao.dias_fechados and str(weekday) in salao.dias_fechados.split(','):
        return False
        
    # 2. Checa Feriado
    if Holiday.objects.filter(salon=salao, data=date_obj).exists():
        return False

    # 3. Checa Folga Individual (Dia todo)
    # Se houver qualquer registro de folga para esse dia SEM hora de início, bloqueia tudo.
    if SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=True).exists():
        return False

    # --- DEFINIÇÃO DO SLOT (INÍCIO E FIM) ---
    duration = svc.duracao_minutos if svc else salao.intervalo_minutos
    slot_start = slot_time_obj
    dummy_date = datetime(2000, 1, 1, slot_start.hour, slot_start.minute)
    slot_end_dt = dummy_date + timedelta(minutes=duration)
    slot_end = slot_end_dt.time()

    if slot_end_dt.date() > dummy_date.date():
        return False

    # 4. Checa Escala de Trabalho
    work_hour = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
    if not work_hour:
        return False
    
    if slot_start < work_hour.start_time or slot_end > work_hour.end_time:
        return False

    # 5. Checa Folga Parcial
    folgas_parciais = SpecialSchedule.objects.filter(
        salon=salao, 
        professional=prof, 
        data=date_obj, 
        hora_inicio__isnull=False
    )
    for folga in folgas_parciais:
        if (slot_start < folga.hora_fim and slot_end > folga.hora_inicio):
            return False

    # 6. Checa Intervalos de Pausa
    breaks = ProfessionalBreak.objects.filter(professional=prof, day_of_week=weekday)
    for b in breaks:
        if (slot_start < b.end_time and slot_end > b.start_time):
            return False

    # 7. Checa Agendamentos Existentes
    appointments = Appointment.objects.filter(professional=prof, data=date_obj)
    for appt in appointments:
        appt_duration = appt.service.duracao_minutos if appt.service else salao.intervalo_minutos
        appt_start = appt.hora_inicio
        appt_dummy = datetime(2000, 1, 1, appt_start.hour, appt_start.minute)
        appt_end = (appt_dummy + timedelta(minutes=appt_duration)).time()
        
        if (slot_start < appt_end and slot_end > appt_start):
            return False
            
    return True

# --- VIEWS ---

def pagina_agendamento(request, slug):
    salao = get_object_or_404(Salon, slug=slug)
    
    servicos = list(Service.objects.filter(salon=salao).values())
    categorias = list(Category.objects.filter(salon=salao).values())
    
    feriados_objs = Holiday.objects.filter(salon=salao)
    feriados = [{'data': f.data.strftime('%Y-%m-%d'), 'descricao': f.descricao} for f in feriados_objs]
    
    folgas_objs = SpecialSchedule.objects.filter(salon=salao, hora_inicio__isnull=True)
    folgas = [{'data': f.data.strftime('%Y-%m-%d')} for f in folgas_objs]

    dias_fechados_lista = []
    if salao.dias_fechados:
        dias_fechados_lista = [int(x.strip()) for x in salao.dias_fechados.split(',') if x.strip().isdigit()]

    # --- Processar Endereço ---
    endereco_dict = {}
    if salao.endereco:
        try:
            endereco_dict = json.loads(salao.endereco)
        except:
            endereco_dict = {}

    context = {
        "salao": salao,
        "servicos": servicos,
        "categorias": categorias,
        "feriados": feriados,
        "folgas": folgas,
        "dias_fechados": dias_fechados_lista,
        "turnstile_site_key": "",
        "endereco": endereco_dict 
    }
    return render(request, "booking/agendar.html", context)

def api_profissionais_por_servico(request, slug, service_id):
    salao = get_object_or_404(Salon, slug=slug)
    profs = Professional.objects.filter(salon=salao, services__id=service_id)
    
    data = []
    for p in profs:
        data.append({
            "id": p.id, 
            "nome": p.nome,
            "foto_url": p.foto.url if p.foto else None
        })
        
    return JsonResponse(data, safe=False)

def api_disponibilidade(request, slug, data_iso):
    salao = get_object_or_404(Salon, slug=slug)
    service_id = request.GET.get('service_id')
    svc = get_object_or_404(Service, id=service_id) if service_id else None
    
    try:
        date_obj = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse([], safe=False)

    if svc:
        profs = Professional.objects.filter(salon=salao, services=svc)
    else:
        profs = Professional.objects.filter(salon=salao)

    resultado = []
    
    for prof in profs:
        weekday = date_obj.weekday()
        wh = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
        if not wh: continue

        slots_disponiveis = []
        
        current_time = datetime.combine(date_obj, wh.start_time)
        end_time = datetime.combine(date_obj, wh.end_time)
        intervalo = salao.intervalo_minutos
        
        duracao = svc.duracao_minutos if svc else 30
        
        while current_time + timedelta(minutes=duracao) <= end_time:
            time_obj = current_time.time()
            if check_slot_availability(salao, prof, svc, date_obj, time_obj):
                if date_obj == datetime.now().date() and time_obj < datetime.now().time():
                    pass
                else:
                    slots_disponiveis.append(time_obj.strftime("%H:%M"))
            
            current_time += timedelta(minutes=intervalo)
            
        if slots_disponiveis:
            resultado.append({
                "professional_id": prof.id,
                "nome": prof.nome,
                "horarios": slots_disponiveis
            })

    return JsonResponse(resultado, safe=False)

@csrf_exempt
def api_confirmar_agendamento(request, slug):
    if request.method != "POST": return JsonResponse({"error": "Method not allowed"}, status=405)
    
    salao = get_object_or_404(Salon, slug=slug)
    try:
        data = json.loads(request.body)
        svc = Service.objects.get(id=data['servico_id'])
        prof = Professional.objects.get(id=data['profissional_id'])
        date_obj = datetime.strptime(data['data'], "%Y-%m-%d").date()
        
        hora_str = data['horario']
        if len(hora_str) == 5: hora_str += ":00"
        time_obj = datetime.strptime(hora_str, "%H:%M:%S").time()
        
    except Exception as e:
        return JsonResponse({"message": f"Dados inválidos: {str(e)}"}, status=400)

    if not check_slot_availability(salao, prof, svc, date_obj, time_obj):
        return JsonResponse({"message": "Horário não está mais disponível."}, status=409)

    # 1. GERAR CÓDIGO AQUI
    codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    Appointment.objects.create(
        salon=salao,
        professional=prof,
        service=svc,
        cliente_nome=data['nome_cliente'],
        cliente_whatsapp=data['whatsapp'],
        data=date_obj,
        hora_inicio=time_obj,
        codigo_validacao=codigo # 2. SALVAR NO BANCO
    )
    
    # 3. RETORNAR PARA O FRONTEND
    return JsonResponse({"ok": True, "codigo": codigo})