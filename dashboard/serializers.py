from rest_framework import serializers
from scheduling.models import Service, Professional, Category, Holiday, SpecialSchedule, Appointment

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