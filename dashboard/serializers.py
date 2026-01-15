from rest_framework import serializers
from scheduling.models import Service, Professional, Category, Holiday, SpecialSchedule, Appointment
from datetime import datetime, timedelta

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = '__all__'
        read_only_fields = ['salon']

class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = '__all__'
        read_only_fields = ['salon']

class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['salon', 'codigo_validacao']

class ProfessionalSerializer(serializers.ModelSerializer):
    foto = serializers.ImageField(required=False, allow_null=True)
    services = serializers.PrimaryKeyRelatedField(many=True, read_only=True) 
    
    class Meta:
        model = Professional
        fields = '__all__'
        read_only_fields = ['salon', 'working_hours', 'breaks']

# --- SERIALIZER DE FOLGA INDIVIDUAL (CORRIGIDO) ---
class SpecialScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialSchedule
        fields = '__all__'
        read_only_fields = ['salon']

    def validate(self, data):
        prof = data.get('professional')
        dia = data.get('data')
        inicio = data.get('hora_inicio')
        fim = data.get('hora_fim')

        # Busca todos os agendamentos ATIVOS desse profissional para o dia
        agendamentos = Appointment.objects.filter(professional=prof, data=dia).exclude(codigo_validacao__isnull=True) # Exemplo de filtro extra se necessario

        for ag in agendamentos:
            duracao = ag.service.duracao_minutos if ag.service else 30 
            ag_inicio_dt = datetime.combine(dia, ag.hora_inicio)
            ag_fim_dt = ag_inicio_dt + timedelta(minutes=duracao)

            # CASO 1: Folga de dia inteiro
            if not inicio: 
                raise serializers.ValidationError(
                    f"Conflito: Já existe agendamento para {ag.cliente_nome} às {ag.hora_inicio}."
                )

            # CASO 2: Folga parcial (verifica colisão)
            folga_inicio_dt = datetime.combine(dia, inicio)
            folga_fim_dt = datetime.combine(dia, fim)

            if folga_inicio_dt < ag_fim_dt and folga_fim_dt > ag_inicio_dt:
                raise serializers.ValidationError(
                    f"Conflito de horário com cliente {ag.cliente_nome} ({ag.hora_inicio})."
                )

        return data

# --- SERIALIZER DE FERIADO GLOBAL (CORRIGIDO) ---
class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ['salon']

    def validate(self, data):
        inicio = data.get('hora_inicio')
        fim = data.get('hora_fim')
        if inicio and fim and inicio >= fim:
            raise serializers.ValidationError("A hora de início deve ser anterior ao fim.")
        
        # Tenta recuperar o salão do usuário logado de forma segura
        user = self.context['request'].user
        salon = None
        if hasattr(user, 'salon'): 
            salon = user.salon
        elif hasattr(user, 'employees') and user.employees.exists():
            salon = user.employees.first().salon
        
        # Se achou o salão, verifica agendamentos
        if salon:
            data_feriado = data.get('data')
            
            # Se for feriado DIA TODO, não pode ter nenhum agendamento
            if not inicio:
                if Appointment.objects.filter(salon=salon, data=data_feriado).exists():
                    raise serializers.ValidationError("Impossível bloquear o dia: Existem agendamentos marcados.")
            
            # Se for PARCIAL, verificamos colisão
            else:
                agendamentos = Appointment.objects.filter(salon=salon, data=data_feriado)
                f_ini = datetime.combine(data_feriado, inicio)
                f_fim = datetime.combine(data_feriado, fim)
                
                for ag in agendamentos:
                    dur = ag.service.duracao_minutos if ag.service else 30
                    a_ini = datetime.combine(data_feriado, ag.hora_inicio)
                    a_fim = a_ini + timedelta(minutes=dur)
                    
                    if f_ini < a_fim and f_fim > a_ini:
                        raise serializers.ValidationError(f"O bloqueio conflita com o agendamento de {ag.cliente_nome}.")
        
        return data