# views.py
from rest_framework import viewsets, authentication
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import (
    User, Student, School, SchoolUser,
    Company, CompanyUser, OffreStage,
    Candidature, AffectationStage, Evaluation, Formation, Competence, CompanySubscription, SubscriptionPlan
)
from .serializers import (
    UserSerializer, StudentSerializer, SchoolSerializer, SchoolUserSerializer,
    CompanySerializer, CompanyUserSerializer, OffreStageSerializer,
    CandidatureSerializer, AffectationStageSerializer, EvaluationSerializer, 
    CustomTokenObtainPairSerializer, FormationSerializer, CompetenceSerializer, CompanySubscriptionSerializer
)
from rest_framework.pagination import PageNumberPagination
# Surcharge de la methode d'authentification JWT pour inclure des informations utilisateur
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.response import Response                                                      
from rest_framework.decorators import action   
from .permissions import IsStaffPermission  
                                               
from rest_framework.exceptions import PermissionDenied


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
    queryset = OffreStage.objects.all()
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
            raise PermissionDenied("Utilisateur non lié à une entreprise.") # ou autre logique selon ton auth
        
        try:
            subscription = CompanySubscription.objects.get(company=company)
        except CompanySubscription.DoesNotExist:
            raise PermissionDenied("Aucun abonnement actif trouvé.")

        if not subscription.is_active():
            raise PermissionDenied("Votre abonnement a expiré.")

        remaining = subscription.remaining_offres()
        if remaining is not None and remaining <= 0:
            raise PermissionDenied("Vous avez atteint la limite d'offres pour votre abonnement.")

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
