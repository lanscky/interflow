# views.py
from rest_framework import viewsets, authentication,status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import (
    User, Student, School, SchoolUser,
    Company, CompanyUser, OffreStage,
    Candidature, AffectationStage, Evaluation, Formation, Competence, CompanySubscription, SubscriptionPlan, Payment
)
from .serializers import (
    UserSerializer, StudentSerializer, SchoolSerializer, SchoolUserSerializer,
    CompanySerializer, CompanyUserSerializer, OffreStageSerializer,
    CandidatureSerializer, AffectationStageSerializer, EvaluationSerializer, 
    CustomTokenObtainPairSerializer, FormationSerializer, CompetenceSerializer, CompanySubscriptionSerializer, PaymentSerializer
)
from rest_framework.pagination import PageNumberPagination
# Surcharge de la methode d'authentification JWT pour inclure des informations utilisateur
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.response import Response                                                      
from rest_framework.decorators import action   
from .permissions import IsStaffPermission  
                                               
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from django.utils import timezone
from datetime import timedelta


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# Fin de la surcharge de la methode d'authentification JWT


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    #authentication_classes = [JWTAuthentication]
    #permission_classes = [IsAuthenticated]

class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    #authentication_classes = [JWTAuthentication]
    permission_classes = [IsStaffPermission]

class SchoolUserViewSet(viewsets.ModelViewSet):
    queryset = SchoolUser.objects.all()
    serializer_class = SchoolUserSerializer
    #permission_classes = [IsAuthenticated]

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsStaffPermission]

class CompanyUserViewSet(viewsets.ModelViewSet):
    queryset = CompanyUser.objects.all()
    serializer_class = CompanyUserSerializer
    #permission_classes = [IsStaffPermission]

class OffreStageViewSet(viewsets.ModelViewSet):
    queryset = OffreStage.objects.all().order_by('-id')
    serializer_class = OffreStageSerializer
    permission_classes = [IsStaffPermission]

    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_id=None):
        offres = self.queryset.filter(company_id=company_id)
        serializer = self.get_serializer(offres, many=True)
        return Response(serializer.data)
    
    def perform_create(self, serializer):
        company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()

        if company_user:
            company = company_user.company
            print("DEBUG - Company liée à l'utilisateur :", company)
        else:
            # Aucun lien avec une entreprise
            raise APIException(detail={"error": "Utilisateur non lié à une entreprise."}, code=status.HTTP_403_FORBIDDEN)

        try:
            subscription = CompanySubscription.objects.get(company=company)
        except CompanySubscription.DoesNotExist:
            raise APIException(detail={"error": "Aucun abonnement actif trouvé."}, code=status.HTTP_403_FORBIDDEN)

        if not subscription.is_active():
            raise APIException(detail={"error": "Votre abonnement a expiré."}, code=status.HTTP_403_FORBIDDEN)

        remaining = subscription.remaining_offres()
        if remaining is not None and remaining <= 0:
            raise APIException(detail={"error": "Vous avez atteint la limite d'offres pour votre abonnement."}, code=status.HTTP_403_FORBIDDEN)

        serializer.save(company=company)
        #return Response(serializer.data)


class CandidatureViewSet(viewsets.ModelViewSet):
    #queryset = Candidature.objects.all()
    queryset = Candidature.objects.select_related('student', 'offre_stage', 'offre_stage__company')

    serializer_class = CandidatureSerializer
    permission_classes = [IsStaffPermission]

    @action(detail=False, methods=['get'], url_path='by-student/(?P<student_id>[^/.]+)')
    def by_student(self, request, student_id=None):
        candidatures = self.queryset.filter(student_id=student_id)
        serializer = self.get_serializer(candidatures, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_id=None):
        candidatures = self.queryset.filter(offre_stage__company_id=company_id)
        serializer = self.get_serializer(candidatures, many=True)
        return Response(serializer.data)

class AffectationStageViewSet(viewsets.ModelViewSet):
    queryset = AffectationStage.objects.all()
    serializer_class = AffectationStageSerializer
    permission_classes = [IsStaffPermission]

class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsStaffPermission]
    @action(detail=False, methods=['get'], url_path='by-candidature/(?P<candidature_id>[^/.]+)')
    def by_candidature(self, request, candidature_id=None):
        evaluations = self.queryset.filter(candidature_id=candidature_id)
        serializer = self.get_serializer(evaluations, many=True)
        return Response(serializer.data)

class FormationViewSet(viewsets.ModelViewSet):
    queryset = Formation.objects.all()
    serializer_class = FormationSerializer
    permission_classes = [IsStaffPermission]

class CompetenceViewSet(viewsets.ModelViewSet):
    queryset = Competence.objects.all()
    serializer_class = CompetenceSerializer
    permission_classes = [IsStaffPermission]

class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):  # uniquement GET (list, retrieve)
    serializer_class = CompanySubscriptionSerializer
    permission_classes = [IsAuthenticated]
  
    def get_queryset(self):
        company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()
        if company_user:
            company = company_user.company
        # On filtre les abonnements de la compagnie de l'utilisateur connecté
        return CompanySubscription.objects.filter(company=company)

class CompanySubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()
        if user.role != 'company':
            return CompanySubscription.objects.none()
        print("DEBUG - CompanyUser:", company_user.company)
        return CompanySubscription.objects.filter(company=company_user.company)

    def perform_create(self, serializer):
        user = self.request.user
        company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()
        if user.role != 'company':
            raise APIException(detail={"error": "Seules les entreprises peuvent souscrire à un abonnement."}, code=status.HTTP_403_FORBIDDEN)

        # Récupère la company liée au user
        try:
            company = company_user.company
        except AttributeError:
            raise APIException(detail={"error": "Seules les entreprises peuvent souscrire à un abonnement."}, code=status.HTTP_403_FORBIDDEN)   

        # Vérifie si la company a déjà un abonnement actif
        if CompanySubscription.objects.filter(company=company, end_date__gte=timezone.now()).exists():
            raise APIException(detail={"error": "Vous avez déjà un abonnement actif. Veuillez le renouveler."}, code=status.HTTP_400_BAD_REQUEST)
        if CompanySubscription.objects.filter(company=company).exists():
            raise APIException(detail={"error": "Veuillez le renouveler au lieu d'en créer un nouveau."}, code=status.HTTP_400_BAD_REQUEST)
        plan_id = self.request.data.get("plan_id")
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            raise APIException(detail={"error": "Plan d'abonnement invalide."}, code=status.HTTP_400_BAD_REQUEST)

        # Calcul de la date de fin (exemple : 30 jours)
        end_date = timezone.now() + timedelta(days=30)

        serializer.save(company=company, plan=plan, end_date=end_date)

    def update(self, request, *args, **kwargs):
        """Renouveler ou changer le plan"""
        instance = self.get_object()
        plan_id = request.data.get("plan_id")

        if plan_id:
            try:
                new_plan = SubscriptionPlan.objects.get(id=plan_id)
                instance.plan = new_plan
            except SubscriptionPlan.DoesNotExist:
                raise APIException(detail={"error": "Plan invalide."}, code=status.HTTP_400_BAD_REQUEST)

        # Prolonger la date de fin (exemple : +30 jours)
        instance.end_date += timedelta(days=30)
        instance.save()

        return Response(self.get_serializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Suppression non autorisée."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class  PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role != 'company':
            return Payment.objects.none()
        company_user = CompanyUser.objects.filter(user=user, is_active=True).first()
        if not company_user:
            return Payment.objects.none()
        return Payment.objects.filter(company=company_user.company)

    def perform_create(self, serializer):
        user = self.request.user
        company_user = CompanyUser.objects.filter(user=user, is_active=True).first()
        if not company_user:
            raise ValidationError("Aucune entreprise associée à ce compte.")
        
        serializer.save(company=company_user.company)