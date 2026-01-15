from rest_framework import serializers
from scheduling.models import Service, Professional, Category, Holiday, SpecialSchedule, Appointment
from datetime import datetime, timedelta  # <--- ADICIONE ESTA LINHA

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

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ['salon']

class SpecialScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialSchedule
        fields = '__all__'
        read_only_fields = ['salon']

class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = '__all__'
        read_only_fields = ['salon', 'codigo_validacao']

class ProfessionalSerializer(serializers.ModelSerializer):
    # Foto é opcional
    foto = serializers.ImageField(required=False, allow_null=True)
    
    # Estes campos são tratados manualmente na View por virem como string JSON do FormData
    # Definimos como read_only aqui para o serializer padrão não tentar validar e falhar
    services = serializers.PrimaryKeyRelatedField(many=True, read_only=True) 
    
    class Meta:
        model = Professional
        fields = '__all__'
        read_only_fields = ['salon', 'working_hours', 'breaks']

class SpecialScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = SpecialSchedule
        fields = '__all__'
        read_only_fields = ['salon']

    # --- ADICIONE ESTE MÉTODO VALIDATE ---
    def validate(self, data):
        prof = data.get('professional')
        dia = data.get('data')
        inicio = data.get('hora_inicio')
        fim = data.get('hora_fim')

        # Busca todos os agendamentos desse profissional para o dia da folga
        agendamentos = Appointment.objects.filter(professional=prof, data=dia)

        for ag in agendamentos:
            # Calcula o horário de término do agendamento existente
            # Se não tiver duração definida, assume 30 min por segurança
            duracao = ag.service.duracao_minutos if ag.service else 30 
            
            ag_inicio_dt = datetime.combine(dia, ag.hora_inicio)
            ag_fim_dt = ag_inicio_dt + timedelta(minutes=duracao)

            # CASO 1: Folga de dia inteiro
            if not inicio: 
                raise serializers.ValidationError(
                    "Não é possível cadastrar folga de dia inteiro pois existem agendamentos nesta data."
                )

            # CASO 2: Folga parcial (verifica sobreposição de horários)
            folga_inicio_dt = datetime.combine(dia, inicio)
            folga_fim_dt = datetime.combine(dia, fim)

            # Lógica de Colisão: (InicioFolga < FimAgenda) E (FimFolga > InicioAgenda)
            if folga_inicio_dt < ag_fim_dt and folga_fim_dt > ag_inicio_dt:
                raise serializers.ValidationError(
                    f"Conflito: Existe um agendamento para {ag.cliente_nome} às {ag.hora_inicio.strftime('%H:%M')} neste intervalo."
                )

        return data
    

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ['salon']

    # --- ADICIONE ESTE MÉTODO ---
    def validate(self, data):
        dia = data.get('data')
        
        # Precisamos pegar o salão do usuário logado através do contexto da requisição
        # para garantir que estamos validando apenas agendamentos DESTE salão.
        salao = self.context['request'].user.salon

        # Se houver qualquer agendamento neste dia, bloqueia
        if Appointment.objects.filter(salon=salao, data=dia).exists():
            raise serializers.ValidationError(
                f"Bloqueado: Existem agendamentos marcados para o dia {dia.strftime('%d/%m/%Y')}. Cancele-os antes de criar o feriado."
            )

        return data
    
    

class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = '__all__'
        read_only_fields = ['salon']

    def validate(self, data):
        # ... (lógica de validação existente) ...
        
        # NOVA VALIDAÇÃO
        inicio = data.get('hora_inicio')
        fim = data.get('hora_fim')
        if inicio and fim and inicio >= fim:
            raise serializers.ValidationError("A hora de início deve ser anterior ao fim.")
            
        return data