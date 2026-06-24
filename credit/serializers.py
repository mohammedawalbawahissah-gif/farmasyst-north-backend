from rest_framework import serializers
from .models import CreditApplication, ApplicationDocument, CreditAgreement
from accounts.serializers import UserSerializer
from farms.models import Farm


class ApplicationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationDocument
        fields = ['id', 'doc_type', 'file', 'original_name', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class CreditApplicationSerializer(serializers.ModelSerializer):
    farmer_name = serializers.CharField(source='farmer.get_full_name', read_only=True)
    documents   = ApplicationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = CreditApplication
        fields = ['id', 'reference', 'farmer', 'farmer_name', 'farm', 'credit_type',
                  'amount_requested', 'repayment_period_months', 'purpose', 'input_details',
                  'status', 'credit_score_at_submission', 'reviewer', 'reviewer_notes',
                  'rejection_reason', 'submitted_at', 'reviewed_at', 'approved_at',
                  'matched_investor', 'created_at', 'updated_at', 'documents']
        read_only_fields = ['id', 'reference', 'farmer', 'status', 'credit_score_at_submission',
                            'reviewer', 'reviewer_notes', 'rejection_reason',
                            'submitted_at', 'reviewed_at', 'approved_at', 'created_at', 'updated_at']


class CreditApplicationAdminSerializer(CreditApplicationSerializer):
    farmer = UserSerializer(read_only=True)

    class Meta(CreditApplicationSerializer.Meta):
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']


class CreditAgreementSerializer(serializers.ModelSerializer):
    farmer_name   = serializers.CharField(source='farmer.get_full_name', read_only=True)
    investor_name = serializers.CharField(source='investor.get_full_name', read_only=True)

    class Meta:
        model = CreditAgreement
        fields = '__all__'
        read_only_fields = ['id', 'reference', 'farmer_signed_at', 'investor_signed_at',
                            'created_at', 'updated_at']


# ── Project Applications ──────────────────────────────────────────────────────

from .models import ProjectApplication, ProjectFarmerEntry


class ProjectFarmerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFarmerEntry
        fields = '__all__'
        read_only_fields = ['id', 'project', 'created_at']


class ProjectApplicationSerializer(serializers.ModelSerializer):
    farmer_entries       = ProjectFarmerEntrySerializer(many=True, read_only=True)
    farmer_count         = serializers.SerializerMethodField()
    submitted_by_name    = serializers.SerializerMethodField()
    reviewer_name        = serializers.SerializerMethodField()

    class Meta:
        model = ProjectApplication
        fields = [
            'id', 'reference', 'project_name', 'organisation',
            'submitted_by', 'submitted_by_name',
            'credit_type', 'total_amount_requested', 'repayment_period_months',
            'purpose', 'status', 'reviewer', 'reviewer_name',
            'reviewer_notes', 'rejection_reason',
            'submitted_at', 'reviewed_at', 'created_at', 'updated_at',
            'farmer_entries', 'farmer_count',
        ]
        read_only_fields = ['id', 'reference', 'status', 'reviewer',
                            'reviewer_notes', 'rejection_reason',
                            'submitted_at', 'reviewed_at', 'created_at', 'updated_at']

    def get_farmer_count(self, obj):
        return obj.farmer_entries.count()

    def get_submitted_by_name(self, obj):
        return obj.submitted_by.get_full_name() if obj.submitted_by else None

    def get_reviewer_name(self, obj):
        return obj.reviewer.get_full_name() if obj.reviewer else None


class ProjectApplicationAdminSerializer(ProjectApplicationSerializer):
    class Meta(ProjectApplicationSerializer.Meta):
        read_only_fields = ['id', 'reference', 'created_at', 'updated_at']
