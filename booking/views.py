import json
import random
import string
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Holiday, SpecialSchedule, WorkingHour, Category

# --- FUNÇÃO AUXILIAR (Mantida Igual) ---
def check_slot_availability(salao, prof, svc, date_obj, slot_time_obj):
    weekday = str(date_obj.weekday())
    duration = svc.duracao_minutos if svc else salao.intervalo_minutos
    slot_start = slot_time_obj
    dummy_date = datetime(2000, 1, 1, slot_start.hour, slot_start.minute)
    slot_end_dt = dummy_date + timedelta(minutes=duration)
    
    if slot_end_dt.date() > dummy_date.date(): return False
    if salao.dias_fechados and weekday in salao.dias_fechados.split(','): return False

    abertura = salao.hora_abertura_padrao
    fechamento = salao.hora_fechamento_padrao
    if salao.horarios_customizados:
        try:
            c = salao.horarios_customizados
            if isinstance(c, str): c = json.loads(c) if c.strip() else {}
            if isinstance(c, dict) and weekday in c:
                if c[weekday].get('inicio'): abertura = datetime.strptime(c[weekday]['inicio'], "%H:%M").time()
                if c[weekday].get('fim'): fechamento = datetime.strptime(c[weekday]['fim'], "%H:%M").time()
        except: pass

    if slot_start < abertura or slot_end_dt.time() > fechamento: return False

    feriados = Holiday.objects.filter(salon=salao, data=date_obj)
    for f in feriados:
        if not f.hora_inicio: return False
        if f.hora_inicio and f.hora_fim:
            if slot_start < f.hora_fim and slot_end_dt.time() > f.hora_inicio: return False

    wh = WorkingHour.objects.filter(professional=prof, day_of_week=int(weekday)).first()
    if not wh: return False
    if slot_start < wh.start_time or slot_end_dt.time() > wh.end_time: return False

    if hasattr(prof, 'intervalos') and prof.intervalos:
        try:
            intervals = prof.intervalos
            if isinstance(intervals, str): intervals = json.loads(intervals) if intervals.strip() else []
            if isinstance(intervals, list):
                for interval in intervals:
                    s_str = interval.get('start') or interval.get('inicio')
                    e_str = interval.get('end') or interval.get('fim')
                    if s_str and e_str:
                        i_start = datetime.strptime(str(s_str)[:5], '%H:%M').time()
                        i_end = datetime.strptime(str(e_str)[:5], '%H:%M').time()
                        if slot_start < i_end and slot_end_dt.time() > i_start: return False
        except: pass

    if SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=True).exists(): return False
    folgas = SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=False)
    for folga in folgas:
        if slot_start < folga.hora_fim and slot_end_dt.time() > folga.hora_inicio: return False

    apps = Appointment.objects.filter(professional=prof, data=date_obj).exclude(status='cancelado') if hasattr(Appointment, 'status') else Appointment.objects.filter(professional=prof, data=date_obj)
    for appt in apps:
        dur = appt.service.duracao_minutos if appt.service else 30
        a_dummy = datetime(2000, 1, 1, appt.hora_inicio.hour, appt.hora_inicio.minute)
        a_end = (a_dummy + timedelta(minutes=dur)).time()
        if slot_start < a_end and slot_end_dt.time() > appt.hora_inicio: return False
            
    return True

# --- VIEWS PRINCIPAIS ---

def pagina_agendamento(request, slug):
    salao = get_object_or_404(Salon, slug=slug)
    servicos = list(Service.objects.filter(salon=salao).values())
    categorias = list(Category.objects.filter(salon=salao).values())
    
    feriados = [{'data': f.data.strftime('%Y-%m-%d')} for f in Holiday.objects.filter(salon=salao, hora_inicio__isnull=True)]
    folgas_globais = [{'data': f.data.strftime('%Y-%m-%d')} for f in SpecialSchedule.objects.filter(salon=salao, hora_inicio__isnull=True)]
    
    dias_fechados = []
    if salao.dias_fechados:
        dias_fechados = [int(x) for x in salao.dias_fechados.split(',') if x.strip().isdigit()]

    endereco = {}
    try:
        if salao.endereco:
            endereco = salao.endereco if isinstance(salao.endereco, dict) else json.loads(salao.endereco)
    except: pass

    # --- AQUI ESTA A CORREÇÃO: ENVIAR DIAS DE TRABALHO ---
    profs_objs = Professional.objects.filter(salon=salao)
    all_wh = WorkingHour.objects.filter(professional__salon=salao)
    all_ss = SpecialSchedule.objects.filter(salon=salao, hora_inicio__isnull=True)

    profissionais_data = []
    for p in profs_objs:
        # Dias da semana que ele trabalha (0=Seg, 6=Dom)
        dias_trabalho = list(all_wh.filter(professional=p).values_list('day_of_week', flat=True))
        # Datas específicas de folga
        folgas_p = [f.data.strftime('%Y-%m-%d') for f in all_ss if f.professional_id == p.id]

        profissionais_data.append({
            "id": p.id,
            "nome": p.nome,
            "foto": p.foto.url if p.foto else None,
            "servicos": list(p.services.values_list('id', flat=True)),
            "dias_trabalho": dias_trabalho, 
            "folgas": folgas_p
        })
    # -----------------------------------------------------

    return render(request, "booking/agendar.html", {
        "salao": salao,
        "servicos": servicos,
        "categorias": categorias,
        "feriados": feriados,
        "folgas": folgas_globais,
        "dias_fechados": dias_fechados,
        "endereco": endereco,
        "profissionais": profissionais_data
    })

def api_profissionais_por_servico(request, slug, service_id):
    salao = get_object_or_404(Salon, slug=slug)
    profs = Professional.objects.filter(salon=salao, services__id=service_id)
    data = [{"id": p.id, "nome": p.nome, "foto_url": p.foto.url if p.foto else None} for p in profs]
    return JsonResponse(data, safe=False)

def api_disponibilidade(request, slug, data_iso):
    salao = get_object_or_404(Salon, slug=slug)
    try:
        service_id = int(request.GET.get('service_id', 0))
        prof_id = int(request.GET.get('professional_id', 0))
        date_obj = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except: return JsonResponse([], safe=False)

    svc = get_object_or_404(Service, id=service_id)
    profs = Professional.objects.filter(id=prof_id, salon=salao)
    resultado = []
    
    for prof in profs:
        if Holiday.objects.filter(salon=salao, data=date_obj, hora_inicio__isnull=True).exists(): continue
        if SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=True).exists(): continue

        weekday = date_obj.weekday()
        wh = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
        if not wh: continue

        slots = []
        current = datetime.combine(date_obj, wh.start_time)
        end_work = datetime.combine(date_obj, wh.end_time)
        step = salao.intervalo_minutos
        
        while current + timedelta(minutes=svc.duracao_minutos) <= end_work:
            t_obj = current.time()
            if check_slot_availability(salao, prof, svc, date_obj, t_obj):
                if date_obj > datetime.now().date() or (date_obj == datetime.now().date() and t_obj > datetime.now().time()):
                    slots.append(t_obj.strftime("%H:%M"))
            current += timedelta(minutes=step)
            
        if slots:
            resultado.append({"professional_id": prof.id, "nome": prof.nome, "horarios": slots})

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
    except Exception as e: return JsonResponse({"message": f"Dados inválidos: {str(e)}"}, status=400)

    if not check_slot_availability(salao, prof, svc, date_obj, time_obj):
        return JsonResponse({"message": "Ops! Esse horário acabou de ser reservado."}, status=409)

    codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    Appointment.objects.create(salon=salao, professional=prof, service=svc, cliente_nome=data['nome_cliente'], cliente_whatsapp=data['whatsapp'], data=date_obj, hora_inicio=time_obj, codigo_validacao=codigo)
    return JsonResponse({"ok": True, "codigo": codigo})