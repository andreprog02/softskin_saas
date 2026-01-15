import json
import random
import string
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Holiday, SpecialSchedule, WorkingHour, Category

# --- FUNÇÃO AUXILIAR DE DISPONIBILIDADE ---
def check_slot_availability(salao, prof, svc, date_obj, slot_time_obj):
    """
    Verifica se um horário específico (slot) está livre.
    Retorna True (Livre) ou False (Ocupado).
    """
    weekday = str(date_obj.weekday()) # 0=Segunda, 6=Domingo

    # 1. DEFINIÇÃO DO SLOT
    duration = svc.duracao_minutos if svc else salao.intervalo_minutos
    slot_start = slot_time_obj
    dummy_date = datetime(2000, 1, 1, slot_start.hour, slot_start.minute)
    slot_end_dt = dummy_date + timedelta(minutes=duration)
    slot_end = slot_end_dt.time()
    
    # Bloqueia virada de dia (ex: serviço começando 23:50)
    if slot_end_dt.date() > dummy_date.date():
        return False
    

    # --- TRAVA DE SEGURANÇA: O profissional faz esse serviço? ---
    if not prof.services.filter(id=svc.id).exists():
        return False


    # 2. DIA FECHADO GLOBAL
    if salao.dias_fechados and weekday in salao.dias_fechados.split(','):
        return False

    # 3. HORÁRIO DE FUNCIONAMENTO (PADRÃO OU CUSTOMIZADO)
    abertura = salao.hora_abertura_padrao
    fechamento = salao.hora_fechamento_padrao
    
    # Tenta ler configuração específica do dia (ex: Sábado reduzido)
    if salao.horarios_customizados:
        try:
            custom = salao.horarios_customizados
            if isinstance(custom, str):
                custom = json.loads(custom) if custom.strip() else {}
            
            if isinstance(custom, dict) and weekday in custom:
                day_cfg = custom[weekday]
                if day_cfg.get('inicio'):
                    abertura = datetime.strptime(day_cfg['inicio'], "%H:%M").time()
                if day_cfg.get('fim'):
                    fechamento = datetime.strptime(day_cfg['fim'], "%H:%M").time()
        except:
            pass # Usa padrão se falhar

    if slot_start < abertura or slot_end > fechamento:
        return False

    # 4. FERIADOS GLOBAIS (TOTAL OU PARCIAL)
    feriados = Holiday.objects.filter(salon=salao, data=date_obj)
    for f in feriados:
        # Se não tem hora de início definida, é feriado o dia todo
        if not f.hora_inicio:
            return False
        
        # Se for parcial, precisa ter início e fim. Se faltar fim, ignora para não quebrar.
        if f.hora_inicio and f.hora_fim:
            # Lógica de Colisão: Slot começa ANTES do bloqueio terminar E termina DEPOIS do bloqueio começar
            if slot_start < f.hora_fim and slot_end > f.hora_inicio:
                return False

    # 5. ESCALA DO PROFISSIONAL
    wh = WorkingHour.objects.filter(professional=prof, day_of_week=int(weekday)).first()
    if not wh:
        return False # Não trabalha neste dia
    
    if slot_start < wh.start_time or slot_end > wh.end_time:
        return False

    # 6. INTERVALOS DE PAUSA (ALMOÇO)
    # Verifica se o campo existe e tem dados
    if hasattr(prof, 'intervalos') and prof.intervalos:
        try:
            intervals = prof.intervalos
            # Se for string, converte para lista
            if isinstance(intervals, str):
                intervals = json.loads(intervals) if intervals.strip() else []
            
            # Garante que é lista
            if isinstance(intervals, list):
                for interval in intervals:
                    # Tenta ler chaves variadas (start/end ou inicio/fim)
                    start_str = interval.get('start') or interval.get('inicio')
                    end_str = interval.get('end') or interval.get('fim')
                    
                    if start_str and end_str:
                        # Limpa os segundos se houver (pega só os 5 primeiros caracteres: "12:00")
                        s_clean = str(start_str)[:5]
                        e_clean = str(end_str)[:5]
                        
                        try:
                            i_start = datetime.strptime(s_clean, '%H:%M').time()
                            i_end = datetime.strptime(e_clean, '%H:%M').time()
                            
                            # Lógica de colisão
                            if slot_start < i_end and slot_end > i_start:
                                return False
                        except ValueError:
                            continue # Pula se o formato for inválido
        except Exception as e:
            print(f"Erro ao ler intervalos: {e}") # Loga o erro no terminal
            pass

    # 7. FOLGAS INDIVIDUAIS (TOTAL OU PARCIAL)
    # Folga Total
    if SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=True).exists():
        return False
    
    # Folga Parcial
    folgas = SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=False)
    for folga in folgas:
        if folga.hora_inicio and folga.hora_fim:
            if slot_start < folga.hora_fim and slot_end > folga.hora_inicio:
                return False

    # 8. AGENDAMENTOS EXISTENTES
    appointments = Appointment.objects.filter(professional=prof, data=date_obj).exclude(status='cancelado') if hasattr(Appointment, 'status') else Appointment.objects.filter(professional=prof, data=date_obj)
    
    for appt in appointments:
        appt_duration = appt.service.duracao_minutos if appt.service else salao.intervalo_minutos
        a_start = appt.hora_inicio
        a_dummy = datetime(2000, 1, 1, a_start.hour, a_start.minute)
        a_end = (a_dummy + timedelta(minutes=appt_duration)).time()
        
        if slot_start < a_end and slot_end > a_start:
            return False
            
    return True

# --- VIEWS PÚBLICAS ---

def pagina_agendamento(request, slug):
    salao = get_object_or_404(Salon, slug=slug)
    servicos = list(Service.objects.filter(salon=salao).values())
    categorias = list(Category.objects.filter(salon=salao).values())
    
    # Prepara feriados e folgas para o calendário bloquear dias inteiros visualmente
    feriados = [{'data': f.data.strftime('%Y-%m-%d')} for f in Holiday.objects.filter(salon=salao, hora_inicio__isnull=True)]
    folgas = [{'data': f.data.strftime('%Y-%m-%d')} for f in SpecialSchedule.objects.filter(salon=salao, hora_inicio__isnull=True)]
    
    dias_fechados = []
    if salao.dias_fechados:
        dias_fechados = [int(x) for x in salao.dias_fechados.split(',') if x.strip().isdigit()]

    endereco = {}
    try:
        if salao.endereco:
            endereco = salao.endereco if isinstance(salao.endereco, dict) else json.loads(salao.endereco)
    except: pass

    # --- NOVO: Carregar profissionais e seus serviços para filtro imediato ---
    profs_objs = Professional.objects.filter(salon=salao)
    profissionais_data = []
    for p in profs_objs:
        profissionais_data.append({
            "id": p.id,
            "nome": p.nome,
            "foto": p.foto.url if p.foto else None,
            "servicos": list(p.services.values_list('id', flat=True)) # Lista de IDs de serviços que ele faz
        })

    return render(request, "booking/agendar.html", {
        "salao": salao,
        "servicos": servicos,
        "categorias": categorias,
        "feriados": feriados,
        "folgas": folgas,
        "dias_fechados": dias_fechados,
        "endereco": endereco,
        "profissionais": profissionais_data # Passando para o template
    })


def api_profissionais_por_servico(request, slug, service_id):
    salao = get_object_or_404(Salon, slug=slug)
    profs = Professional.objects.filter(salon=salao, services__id=service_id)
    data = [{"id": p.id, "nome": p.nome, "foto_url": p.foto.url if p.foto else None} for p in profs]
    return JsonResponse(data, safe=False)

def api_disponibilidade(request, slug, data_iso):
    """
    Gera os slots de tempo disponíveis.
    """
    salao = get_object_or_404(Salon, slug=slug)
    
    try:
        service_id = int(request.GET.get('service_id', 0))
        prof_id = int(request.GET.get('professional_id', 0))
        date_obj = datetime.strptime(data_iso, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return JsonResponse([], safe=False)

    svc = get_object_or_404(Service, id=service_id)
    # Filtra apenas o profissional selecionado para otimizar
    profs = Professional.objects.filter(id=prof_id, salon=salao)

    resultado = []
    
    for prof in profs:
        # Se houver feriado de DIA INTEIRO, pula o profissional
        if Holiday.objects.filter(salon=salao, data=date_obj, hora_inicio__isnull=True).exists():
            continue
            
        # Se houver folga de DIA INTEIRO, pula
        if SpecialSchedule.objects.filter(salon=salao, professional=prof, data=date_obj, hora_inicio__isnull=True).exists():
            continue

        weekday = date_obj.weekday()
        wh = WorkingHour.objects.filter(professional=prof, day_of_week=weekday).first()
        if not wh: continue

        slots = []
        # Define horário de início e fim baseados na escala
        current = datetime.combine(date_obj, wh.start_time)
        end_work = datetime.combine(date_obj, wh.end_time)
        
        # Incremento do loop
        step = salao.intervalo_minutos
        
        while current + timedelta(minutes=svc.duracao_minutos) <= end_work:
            t_obj = current.time()
            
            # Verifica disponibilidade atômica
            if check_slot_availability(salao, prof, svc, date_obj, t_obj):
                # Não mostra horários passados se for hoje
                if date_obj > datetime.now().date() or (date_obj == datetime.now().date() and t_obj > datetime.now().time()):
                    slots.append(t_obj.strftime("%H:%M"))
            
            current += timedelta(minutes=step)
            
        if slots:
            resultado.append({
                "professional_id": prof.id,
                "nome": prof.nome,
                "horarios": slots
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
        return JsonResponse({"message": "Ops! Esse horário acabou de ser reservado."}, status=409)

    codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    Appointment.objects.create(
        salon=salao,
        professional=prof,
        service=svc,
        cliente_nome=data['nome_cliente'],
        cliente_whatsapp=data['whatsapp'],
        data=date_obj,
        hora_inicio=time_obj,
        codigo_validacao=codigo
    )
    
    return JsonResponse({"ok": True, "codigo": codigo})