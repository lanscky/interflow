from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, StudentViewSet, SchoolViewSet, SchoolUserViewSet,
    CompanyViewSet, CompanyUserViewSet, OffreStageViewSet,
    CandidatureViewSet, AffectationStageViewSet, StageWeeklyReportViewSet, StageCertificateViewSet, NotificationViewSet, PushDeviceViewSet, EvaluationViewSet,
    FormationViewSet, CompetenceViewSet,SubscriptionViewSet,CompanySubscriptionViewSet,PaymentViewSet,ConfigViewSet,
    GoogleLoginView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'students', StudentViewSet)
router.register(r'schools', SchoolViewSet)
router.register(r'school-users', SchoolUserViewSet)
router.register(r'companies', CompanyViewSet)
router.register(r'company-users', CompanyUserViewSet)
router.register(r'offres-stage', OffreStageViewSet)
router.register(r'candidatures', CandidatureViewSet)
router.register(r'affectations-stage', AffectationStageViewSet)
router.register(r'rapports-stage', StageWeeklyReportViewSet)
router.register(r'attestations', StageCertificateViewSet, basename='attestations')
router.register(r'notifications', NotificationViewSet, basename='notifications')
router.register(r'push-devices', PushDeviceViewSet, basename='push-devices')
router.register(r'evaluations', EvaluationViewSet)
router.register(r'formations', FormationViewSet)
router.register(r'competences', CompetenceViewSet)
router.register(r'subscription', SubscriptionViewSet, basename='subscription')
router.register(r'company-subscriptions', CompanySubscriptionViewSet, basename='company-subscription')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'config', ConfigViewSet, basename='config')

urlpatterns = [
    path('auth/google/', GoogleLoginView.as_view(), name='google-login'),
    path('', include(router.urls)),
]
