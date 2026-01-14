import json
from datetime import datetime, timedelta, time
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Holiday, SpecialSchedule, WorkingHour, ProfessionalBreak

# --- FUNÇÃO AUXILIAR DE DISPONIBILIDADE ---
def check_slot_availability(salao, prof, svc, date_obj, slot_time_obj):
    # 1. Checa se o dia da semana está configurado como fechado no salão
    weekday = date_obj.weekday() # 0=Segunda, 6=Domingo
    if salao.dias_fechados and str(weekday) in salao.dias_fechados.split(','):
        return False
        
    # 2. Verifica se a data é um feriado cadastrado para o salão
    if Holiday.objects.filter(salon=salao, data=date_obj).exists():
        return False

    # 3. Verifica folgas ou agendas especiais do profissional
    folgas = SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj)
    for folga in folgas:
        if not folga.hora_inicio: # Se não houver hora, é folga o dia todo
            return False

    # 4. Verifica a Escala de Trabalho (WorkingHour) do profissional para este dia
    work_hour = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
    if not work_hour:
        return False
    
    # Define os limites de início e fim do atendimento (slot)
    duration = svc.duracao_minutos if svc else salao.intervalo_minutos
    slot_start = slot_time_obj
    
    # Cálculo da hora final do serviço
    dummy_date = datetime(2000, 1, 1, slot_start.hour, slot_start.minute)
    slot_end = (dummy_date + timedelta(minutes=duration)).time()

    # Verifica se o serviço termina antes do fim do expediente do profissional
    if slot_start < work_hour.start_time or slot_end > work_hour.end_time:
        return False

    # 5. Verifica intervalos (como horário de almoço)
    breaks = ProfessionalBreak.objects.filter(professional=prof, day_of_week=weekday)
    for b in breaks:
        if (slot_start < b.end_time and slot_end > b.start_time):
            return False

    # 6. Verifica sobreposição com agendamentos já existentes
    appointments = Appointment.objects.filter(professional=prof, data=date_obj)
    for appt in appointments:
        appt_duration = appt.service.duracao_minutos if appt.service else salao.intervalo_minutos
        appt_start = appt.hora_inicio
        appt_dummy = datetime(2000, 1, 1, appt_start.hour, appt_start.minute)
        appt_end = (appt_dummy + timedelta(minutes=appt_duration)).time()
        
        if (slot_start < appt_end and slot_end > appt_start):
            return False
            
    return True

# --- VIEWS PRINCIPAIS ---

def pagina_agendamento(request, slug):
    salao = get_object_or_404(Salon, slug=slug)
    # Coleta serviços e categorias vinculados ao salão
    servicos = list(salao.service_set.all().values())
    categorias = list(salao.category_set.all().values())
    
    context = {
        "salao": salao,
        "servicos": servicos,
        "categorias": categorias,
        "turnstile_site_key": "" # Insira sua site key do Cloudflare Turnstile aqui
    }
    return render(request, "booking/agendar.html", context)

def api_profissionais_por_servico(request, slug, service_id):
    salao = get_object_or_404(Salon, slug=slug)
    # Filtra apenas profissionais habilitados para o serviço selecionado
    profs = Professional.objects.filter(salon=salao, services__id=service_id)
    data = [{"id": p.id, "nome": p.nome} for p in profs]
    return JsonResponse(data, safe=False)

def api_disponibilidade(request, slug, data_iso):
    salao = get_object_or_404(Salon, slug=slug)
    service_id = request.GET.get('service_id')
    svc = get_object_or_404(Service, id=service_id) if service_id else None
    
    try:
        date_obj = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse([], safe=False)

    profs = Professional.objects.filter(salon=salao, services=svc) if svc else Professional.objects.filter(salon=salao)
    resultado = []
    
    for prof in profs:
        weekday = date_obj.weekday()
        wh = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
        if not wh: continue

        slots_disponiveis = []
        current_time = datetime.combine(date_obj, wh.start_time)
        end_time = datetime.combine(date_obj, wh.end_time)
        intervalo = salao.intervalo_minutos
        
        while current_time + timedelta(minutes=svc.duracao_minutos if svc else 30) <= end_time:
            time_obj = current_time.time()
            if check_slot_availability(salao, prof, svc, date_obj, time_obj):
                # Esconde horários passados se a data for hoje
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
    if request.method != "POST": 
        return JsonResponse({"error": "Método não permitido"}, status=405)
    
    salao = get_object_or_404(Salon, slug=slug)
    try:
        data = json.loads(request.body)
        
        # Extração e validação dos dados enviados pelo agendar.html
        svc = Service.objects.get(id=data['service_id'])
        prof = Professional.objects.get(id=data['professional_id'])
        date_obj = datetime.strptime(data['data'], "%Y-%m-%d").date()
        time_obj = datetime.strptime(data['hora_inicio'], "%H:%M").time()
        
        # Validação final de segurança para evitar agendamentos duplicados no mesmo microssegundo
        if not check_slot_availability(salao, prof, svc, date_obj, time_obj):
            return JsonResponse({"message": "Este horário acabou de ser preenchido por outra pessoa."}, status=409)

        # Criação do agendamento
        Appointment.objects.create(
            salon=salao,
            professional=prof,
            service=svc,
            cliente_nome=data['cliente_nome'],
            cliente_whatsapp=data['cliente_whatsapp'],
            data=date_obj,
            hora_inicio=time_obj
        )
        return JsonResponse({"ok": True})
    except Exception as e:
        return JsonResponse({"message": f"Erro nos dados enviados: {str(e)}"}, status=400)