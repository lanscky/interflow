# views.py
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from .models import (
    User, Student, School, SchoolUser,
    Company, CompanyUser, OffreStage,
    Candidature, AffectationStage, Evaluation, Formation, Competence
)
from .serializers import (
    UserSerializer, StudentSerializer, SchoolSerializer, SchoolUserSerializer,
    CompanySerializer, CompanyUserSerializer, OffreStageSerializer,
    CandidatureSerializer, AffectationStageSerializer, EvaluationSerializer, CustomTokenObtainPairSerializer, FormationSerializer, CompetenceSerializer
)
from rest_framework.pagination import PageNumberPagination
# Surcharge de la methode d'authentification JWT pour inclure des informations utilisateur
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.response import Response                                                      
from rest_framework.decorators import action                                                    

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
    permission_classes = [IsAuthenticated]

class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all()
    serializer_class = SchoolSerializer
    permission_classes = [IsAuthenticated]

class SchoolUserViewSet(viewsets.ModelViewSet):
    queryset = SchoolUser.objects.all()
    serializer_class = SchoolUserSerializer
    permission_classes = [IsAuthenticated]

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated]

class CompanyUserViewSet(viewsets.ModelViewSet):
    queryset = CompanyUser.objects.all()
    serializer_class = CompanyUserSerializer
    permission_classes = [IsAuthenticated]

class OffreStageViewSet(viewsets.ModelViewSet):
    queryset = OffreStage.objects.all()
    serializer_class = OffreStageSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_id=None):
        offres = self.queryset.filter(company_id=company_id)
        serializer = self.get_serializer(offres, many=True)
        return Response(serializer.data)

class CandidatureViewSet(viewsets.ModelViewSet):
    #queryset = Candidature.objects.all()
    queryset = Candidature.objects.select_related('student', 'offre_stage', 'offre_stage__company')

    serializer_class = CandidatureSerializer
    permission_classes = [IsAuthenticated]

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
    permission_classes = [IsAuthenticated]

class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated]
    @action(detail=False, methods=['get'], url_path='by-candidature/(?P<candidature_id>[^/.]+)')
    def by_candidature(self, request, candidature_id=None):
        evaluations = self.queryset.filter(candidature_id=candidature_id)
        serializer = self.get_serializer(evaluations, many=True)
        return Response(serializer.data)

class FormationViewSet(viewsets.ModelViewSet):
    queryset = Formation.objects.all()
    serializer_class = FormationSerializer
    permission_classes = [IsAuthenticated]

class CompetenceViewSet(viewsets.ModelViewSet):
    queryset = Competence.objects.all()
    serializer_class = CompetenceSerializer
    permission_classes = [IsAuthenticated]