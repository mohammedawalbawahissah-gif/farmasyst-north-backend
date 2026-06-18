from rest_framework import serializers
from .models import Farm, FarmActivityLog, FarmAuditReport


class FarmSerializer(serializers.ModelSerializer):
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    monitoring_officer_name = serializers.SerializerMethodField()

    class Meta:
        model = Farm
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_monitoring_officer_name(self, obj):
        if obj.monitoring_officer:
            return obj.monitoring_officer.get_full_name()
        return None

    def _abs(self, field, request):
        if not field:
            return None
        url = field.url
        if request:
            return request.build_absolute_uri(url)
        from django.conf import settings
        base = getattr(settings, 'BACKEND_URL', '').rstrip('/')
        return f'{base}{url}' if base else url

    def get_farm_photo(self, obj):
        return self._abs(obj.farm_photo, self.context.get('request'))

    def get_registration_cert(self, obj):
        return self._abs(obj.registration_cert, self.context.get('request'))


class FarmActivityLogSerializer(serializers.ModelSerializer):
    flock_count = serializers.ReadOnlyField()   # computed property: sum of all categories

    class Meta:
        model = FarmActivityLog
        fields = '__all__'
        read_only_fields = ['id', 'logged_by', 'created_at']


class FarmAuditReportSerializer(serializers.ModelSerializer):
    auditor_name = serializers.SerializerMethodField()
    farm_name    = serializers.CharField(source='farm.name', read_only=True)

    class Meta:
        model = FarmAuditReport
        fields = '__all__'
        read_only_fields = ['id', 'auditor', 'created_at']

    def get_auditor_name(self, obj):
        if obj.auditor:
            return obj.auditor.get_full_name()
        return None
