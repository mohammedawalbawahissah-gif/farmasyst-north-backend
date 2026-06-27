from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (RegisterView, LogoutView, MeView, ChangePasswordView,
                             FarmerProfileView, InvestorProfileView,
                             FarmerProfileListView, FarmerProfileDetailView,
                             InvestorProfileListView, UserViewSet,
                             VerifiedTokenObtainPairView,
                             VerifyOTPView, ResendOTPView)
from farms.views import FarmViewSet, FarmActivityLogViewSet, FarmAuditReportViewSet
from credit.views import (CreditApplicationViewSet, DocumentUploadView,
                           CreditAgreementViewSet, ProjectApplicationViewSet)
from marketplace.views import ProduceViewSet, OrderViewSet, ProduceReviewViewSet
from training.views import TrainingModuleViewSet, TrainingEnrolmentViewSet
from notifications.views import NotificationViewSet, notification_sse_stream
from payments.views import (RepaymentScheduleViewSet, InitiateRepaymentView,
                             PaystackWebhookView, MoMoWebhookView, HubtelWebhookView,
                             DisbursementViewSet, DisbursementRequestViewSet,
                             PayFullBalanceView)
from vet.views import VetProfileViewSet, VetServiceViewSet, VetBookingViewSet
from inputs.views import InputDealerProfileViewSet, FarmInputViewSet
from ai.views import CreditworthinessView, DiseaseDetectionView, AIChatView, FlockCountView

router = DefaultRouter()
router.register(r'users',                                   UserViewSet,                 basename='users')
router.register(r'farms',                                   FarmViewSet,                 basename='farms')
router.register(r'farms/(?P<farm_pk>[^/.]+)/activity-logs', FarmActivityLogViewSet,      basename='farm-activity')
router.register(r'farm-audit-reports',                      FarmAuditReportViewSet,      basename='audit-reports')
router.register(r'credit/applications',                     CreditApplicationViewSet,    basename='credit-applications')
router.register(r'credit/agreements',                       CreditAgreementViewSet,      basename='credit-agreements')
router.register(r'credit/projects',                         ProjectApplicationViewSet,   basename='project-applications')
router.register(r'marketplace/produce',                     ProduceViewSet,              basename='produce')
router.register(r'marketplace/produce/(?P<produce_pk>[^/.]+)/reviews', ProduceReviewViewSet, basename='produce-reviews')
router.register(r'marketplace/orders',                      OrderViewSet,                basename='orders')
router.register(r'training/modules',                        TrainingModuleViewSet,       basename='training-modules')
router.register(r'training/enrolments',                     TrainingEnrolmentViewSet,    basename='enrolments')
router.register(r'notifications',                           NotificationViewSet,         basename='notifications')
router.register(r'payments/schedules',                      RepaymentScheduleViewSet,    basename='repayment-schedules')
router.register(r'payments/disbursements',                  DisbursementViewSet,         basename='disbursements')
router.register(r'payments/disbursement-requests',          DisbursementRequestViewSet,  basename='disbursement-requests')
router.register(r'vet/profiles',                            VetProfileViewSet,           basename='vet-profiles')
router.register(r'vet/services',                            VetServiceViewSet,           basename='vet-services')
router.register(r'vet/bookings',                            VetBookingViewSet,           basename='vet-bookings')
router.register(r'inputs/dealers',                          InputDealerProfileViewSet,   basename='input-dealers')
router.register(r'inputs/listings',                         FarmInputViewSet,            basename='farm-inputs')

urlpatterns = [
    path('health/', lambda r: JsonResponse({'status': 'ok'})),
    path('admin/',  admin.site.urls),
    path('api/v1/', include(router.urls)),

    # Auth
    path('api/v1/auth/register/',      RegisterView.as_view()),
    path('api/v1/auth/login/',         VerifiedTokenObtainPairView.as_view()),
    path('api/v1/auth/refresh/',       TokenRefreshView.as_view()),
    path('api/v1/auth/logout/',        LogoutView.as_view()),
    path('api/v1/auth/me/',            MeView.as_view()),
    path('api/v1/auth/change-password/', ChangePasswordView.as_view()),

    # OTP verification
    path('api/v1/auth/verify-otp/',    VerifyOTPView.as_view()),
    path('api/v1/auth/resend-otp/',    ResendOTPView.as_view()),

    # Profiles
    path('api/v1/profiles/farmer/',             FarmerProfileView.as_view()),
    path('api/v1/profiles/farmers/',            FarmerProfileListView.as_view()),
    path('api/v1/profiles/farmers/<int:pk>/',   FarmerProfileDetailView.as_view()),
    path('api/v1/profiles/farmers/<uuid:user_id>/', FarmerProfileDetailView.as_view()),
    path('api/v1/profiles/investor/',           InvestorProfileView.as_view()),
    path('api/v1/profiles/investors/',          InvestorProfileListView.as_view()),

    # Credit documents
    path('api/v1/credit/applications/<uuid:application_id>/documents/',
         DocumentUploadView.as_view()),

    # Payments
    path('api/v1/payments/initiate-repayment/', InitiateRepaymentView.as_view()),
    path('api/v1/payments/pay-full-balance/',   PayFullBalanceView.as_view()),
    path('api/v1/webhooks/paystack/',           PaystackWebhookView.as_view()),
    path('api/v1/webhooks/momo/',               MoMoWebhookView.as_view()),
    path('api/v1/webhooks/hubtel/',             HubtelWebhookView.as_view()),

    # AI Engine
    path('api/v1/ai/creditworthiness/',  CreditworthinessView.as_view()),
    path('api/v1/ai/disease-detection/', DiseaseDetectionView.as_view()),
    path('api/v1/ai/chat/',              AIChatView.as_view()),
    path('api/v1/ai/flock-count/',       FlockCountView.as_view()),

    # Real-time notification stream (SSE)
    # Client connects with: GET /api/v1/notifications/stream/?token=<access_token>
    path('api/v1/notifications/stream/', notification_sse_stream),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
