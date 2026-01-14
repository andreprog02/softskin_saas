import json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt 

from core.models import Salon
from scheduling.models import Service, Professional, Appointment, Category, Holiday, SpecialSchedule, WorkingHour, ProfessionalBreak

@login_required
def dashboard_view(request):
    salao = request.user.salon
    
    agendamentos = Appointment.objects.filter(salon=salao).order_by('-data', 'hora_inicio')
    categorias = Category.objects.filter(salon=salao)
    servicos = Service.objects.filter(salon=salao)
    feriados = Holiday.objects.filter(salon=salao)
    folgas = SpecialSchedule.objects.filter(salon=salao)

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
            "intervalos": intervalos
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

# --- APIs ---

@csrf_exempt
@login_required
def api_servicos(request, item_id=None):
    salao = request.user.salon
    
    if request.method == "DELETE":
        s = get_object_or_404(Service, id=item_id, salon=salao)
        s.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    cat_id = data.get("category_id")
    if cat_id == "" or cat_id == "sem-categoria":
        cat_id = None

    if request.method == "POST":
        s = Service.objects.create(
            salon=salao,
            nome=data['nome'],
            preco=data['preco'],
            duracao_minutos=data['duracao_minutos'],
            category_id=cat_id
        )
        return JsonResponse({"id": s.id, "ok": True})
    
    elif request.method == "PUT":
        s = get_object_or_404(Service, id=item_id, salon=salao)
        s.nome = data.get('nome', s.nome)
        s.preco = data.get('preco', s.preco)
        s.duracao_minutos = data.get('duracao_minutos', s.duracao_minutos)
        s.category_id = cat_id
        s.save()
        return JsonResponse({"ok": True})

@csrf_exempt
@login_required
def api_profissionais(request, item_id=None):
    salao = request.user.salon
    
    if request.method == "DELETE":
        p = get_object_or_404(Professional, id=item_id, salon=salao)
        p.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    
    if request.method == "POST":
        p = Professional.objects.create(salon=salao, nome=data['nome'], especialidade=data.get('especialidade'))
    else:
        p = get_object_or_404(Professional, id=item_id, salon=salao)
        p.nome = data.get('nome', p.nome)
        p.especialidade = data.get('especialidade', p.especialidade)
        p.save()

    if "servicos_ids" in data:
        p.services.set(data['servicos_ids'])
    
    if "escala" in data:
        p.working_hours.all().delete()
        p.breaks.all().delete()
        
        escala = data["escala"]
        dias = escala.get("dias", [])
        inicio = escala.get("inicio")
        fim = escala.get("fim")
        
        for dia in dias:
            if inicio and fim:
                WorkingHour.objects.create(professional=p, day_of_week=dia, start_time=inicio, end_time=fim)
            
            for i in data.get("intervalos", []):
                ProfessionalBreak.objects.create(professional=p, day_of_week=dia, start_time=i["start"], end_time=i["end"])

    return JsonResponse({"ok": True})

@csrf_exempt
@login_required
def api_categorias(request, item_id=None):
    salao = request.user.salon
    
    if request.method == "DELETE":
        c = get_object_or_404(Category, id=item_id, salon=salao)
        c.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    
    if request.method == "POST":
        c = Category.objects.create(salon=salao, nome=data['nome'])
        return JsonResponse({"id": c.id, "ok": True})
    elif request.method == "PUT":
        c = get_object_or_404(Category, id=item_id, salon=salao)
        c.nome = data.get('nome', c.nome)
        c.save()
        return JsonResponse({"ok": True})

@csrf_exempt
@login_required
def api_feriados(request, item_id=None):
    salao = request.user.salon
    
    if request.method == "DELETE":
        h = get_object_or_404(Holiday, id=item_id, salon=salao)
        h.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    
    if request.method == "POST":
        Holiday.objects.create(salon=salao, data=data['data'], descricao=data['descricao'])
        return JsonResponse({"ok": True})
    elif request.method == "PUT":
        h = get_object_or_404(Holiday, id=item_id, salon=salao)
        h.data = data.get('data', h.data)
        h.descricao = data.get('descricao', h.descricao)
        h.save()
        return JsonResponse({"ok": True})

@csrf_exempt
@login_required
def api_folgas(request, item_id=None):
    salao = request.user.salon
    
    if request.method == "DELETE":
        f = get_object_or_404(SpecialSchedule, id=item_id, salon=salao)
        f.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    prof_id = data.get('professional_id')
    if not Professional.objects.filter(id=prof_id, salon=salao).exists():
        return JsonResponse({"error": "Profissional inválido"}, status=400)

    if request.method == "POST":
        SpecialSchedule.objects.create(
            salon=salao, 
            professional_id=prof_id,
            data=data['data'],
            hora_inicio=data.get('hora_inicio'),
            hora_fim=data.get('hora_fim')
        )
        return JsonResponse({"ok": True})
    elif request.method == "PUT":
        folga = get_object_or_404(SpecialSchedule, id=item_id, salon=salao)
        folga.data = data.get('data', folga.data)
        folga.hora_inicio = data.get('hora_inicio')
        folga.hora_fim = data.get('hora_fim')
        folga.save()
        return JsonResponse({"ok": True})

@csrf_exempt
@login_required
def api_agendamentos(request, item_id):
    salao = request.user.salon
    
    if request.method == "DELETE":
        a = get_object_or_404(Appointment, id=item_id, salon=salao)
        a.delete()
        return JsonResponse({"ok": True})

    data = json.loads(request.body)
    appt = get_object_or_404(Appointment, id=item_id, salon=salao)
    
    if request.method == "PUT":
        if 'data' in data: appt.data = data['data']
        if 'hora_inicio' in data: appt.hora_inicio = data['hora_inicio']
        if 'service_id' in data: appt.service_id = data['service_id']
        if 'professional_id' in data: appt.professional_id = data['professional_id']
        appt.save()
        return JsonResponse({"ok": True})

# Mantido caso ainda seja usado por algum endpoint antigo
@csrf_exempt
@login_required
def api_delete_item(request, tipo, item_id):
    # Redirecionando a lógica para garantir consistência ou manter compatibilidade
    return JsonResponse({"error": "Use endpoint específico"}, status=400)

@csrf_exempt
@login_required
def api_configuracoes(request, salon_id):
    salao = request.user.salon
    if salao.id != int(salon_id): return JsonResponse({"error": "Forbidden"}, status=403)
    data = json.loads(request.body)
    allowed = ["nome", "cnpj_cpf", "telefone", "hora_abertura_padrao", "hora_fechamento_padrao", "intervalo_minutos", "dias_fechados", "cor_do_tema", "ocultar_precos", "endereco"]
    for k, v in data.items():
        if k in allowed: setattr(salao, k, v)
    salao.save()
    return JsonResponse({"ok": True})