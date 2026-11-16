# views.py
from rest_framework import viewsets, authentication, status, filters
from rest_framework.permissions import AllowAny, IsAuthenticated, SAFE_METHODS
from .models import Partner
from .serializers import PartnerSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import (
    User, Student, SocialIdentity, School, SchoolUser,
    Company, CompanyUser, OffreStage,
    Candidature, AffectationStage, StageWeeklyReport, StageCertificate, Notification, PushDevice, Evaluation, Formation, Competence, CompanySubscription, SubscriptionPlan, Payment, Config
)
from .serializers import (
    UserSerializer, StudentSerializer, SchoolSerializer, SchoolUserSerializer,
    CompanySerializer, CompanyUserSerializer, OffreStageSerializer,
    CandidatureSerializer, AffectationStageSerializer, StageWeeklyReportSerializer, NotificationSerializer, PushDeviceSerializer, EvaluationSerializer,
    CustomTokenObtainPairSerializer, StudentProfileUpdateSerializer,
    GoogleAuthSerializer, serialize_user_for_session, FormationSerializer, CompetenceSerializer,
    CompanySubscriptionSerializer, PaymentSerializer, SubscriptionPlanSerializer, ConfigSerializer
)
from rest_framework.pagination import PageNumberPagination, LimitOffsetPagination
# Surcharge de la methode d'authentification JWT pour inclure des informations utilisateur
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import CustomTokenObtainPairSerializer
from rest_framework.response import Response                                                      
from rest_framework.decorators import action   
from rest_framework.views import APIView
from .permissions import IsStaffPermission, IsRelatedObjectOwnerOrStaff, company_for_user
                                               
from rest_framework.exceptions import PermissionDenied, ValidationError, APIException
from django.utils import timezone
from datetime import timedelta
#envoie m'email
from appstage.tasks import send_welcome_email
# verification de l'activation du compte
from .utils import decode_activation_token
from .utils import generate_activation_token
from .tasks import send_activation_email
from django.contrib.auth.password_validation import validate_password
from django.db.models import Count, F, Max
from django.core.exceptions import ObjectDoesNotExist
from .documents import build_stage_certificate, certificate_data_hash
from .notifications import notify_company, notify_user
from django.db import transaction
from decimal import Decimal, InvalidOperation
import base64
import logging
import requests
from django.conf import settings
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from .profiles import student_profile_completion


logger = logging.getLogger(__name__)


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

# Fin de la surcharge de la methode d'authentification JWT


class GoogleConfigurationError(APIException):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "La connexion Google n'est pas configurée sur le serveur."


class PlatformStatsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        today = timezone.localdate()
        return Response({
            "companies": Company.objects.count(),
            "students": Student.objects.count(),
            "active_offers": OffreStage.objects.filter(
                is_active=True,
                end_date__gte=today,
            ).count(),
            "placements": Candidature.objects.filter(status="accepted").count(),
        })


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @staticmethod
    def _verify_google_token(token):
        allowed_client_ids = settings.GOOGLE_OAUTH_CLIENT_IDS
        if not allowed_client_ids:
            raise GoogleConfigurationError()
        try:
            claims = google_id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
            )
        except ValueError as exc:
            raise ValidationError({"detail": "Jeton Google invalide ou expiré."}) from exc

        if claims.get('aud') not in allowed_client_ids:
            raise ValidationError({"detail": "Ce jeton Google n'est pas destiné à Totinda."})
        if not claims.get('email_verified'):
            raise ValidationError({"detail": "L'adresse e-mail Google n'est pas vérifiée."})
        if not claims.get('sub') or not claims.get('email'):
            raise ValidationError({"detail": "Le compte Google ne fournit pas les informations requises."})
        return claims

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        claims = self._verify_google_token(serializer.validated_data['id_token'])
        provider_user_id = claims['sub']
        email = claims['email'].strip().lower()
        password = serializer.validated_data.get('password')

        with transaction.atomic():
            identity = SocialIdentity.objects.select_related('user').filter(
                provider=SocialIdentity.PROVIDER_GOOGLE,
                provider_user_id=provider_user_id,
            ).first()

            if identity:
                user = identity.user
                if user.email.lower() != email:
                    identity.email_at_link = email
                    identity.save(update_fields=['email_at_link', 'updated_at'])
            else:
                user = User.objects.select_for_update().filter(email__iexact=email).first()
                if user:
                    if user.role != 'student':
                        return Response(
                            {"detail": "Cette adresse appartient à un compte non étudiant."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    if not user.is_active:
                        return Response(
                            {"detail": "Activez d'abord votre compte existant par e-mail."},
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    if not password:
                        return Response(
                            {
                                "code": "account_link_required",
                                "detail": "Saisissez le mot de passe du compte Totinda existant pour le lier à Google.",
                            },
                            status=status.HTTP_409_CONFLICT,
                        )
                    if not user.has_usable_password() or not user.check_password(password):
                        return Response(
                            {
                                "code": "account_link_required",
                                "detail": "Mot de passe Totinda incorrect.",
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    if user.social_identities.filter(
                        provider=SocialIdentity.PROVIDER_GOOGLE,
                    ).exists():
                        return Response(
                            {"detail": "Ce compte Totinda est déjà lié à un autre compte Google."},
                            status=status.HTTP_409_CONFLICT,
                        )
                else:
                    username = (
                        claims.get('family_name')
                        or claims.get('name')
                        or email.split('@', 1)[0]
                    ).strip()[:150]
                    user = User(
                        email=email,
                        username=username,
                        prenom=str(claims.get('given_name') or '').strip()[:150],
                        postnom='',
                        role='student',
                        is_active=True,
                        is_staff=False,
                        is_superuser=False,
                    )
                    user.set_unusable_password()
                    user.save()
                    Student.objects.create(user=user)

                SocialIdentity.objects.create(
                    user=user,
                    provider=SocialIdentity.PROVIDER_GOOGLE,
                    provider_user_id=provider_user_id,
                    email_at_link=email,
                )

        if user.role != 'student' or not user.is_active:
            return Response(
                {"detail": "Accès réservé aux comptes étudiants actifs."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': serialize_user_for_session(user, request),
        })


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 1000

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination

    def get_permissions(self):
        if self.action in {'activate_account', 'resend_activation'}:
            return [AllowAny()]
        return [IsAuthenticated(), IsRelatedObjectOwnerOrStaff()]

    def get_queryset(self):
        if self.request.user.is_staff:
            return User.objects.all()
        return User.objects.filter(pk=self.request.user.pk)

    def perform_update(self, serializer):
        previous_picture = serializer.instance.profile_picture
        user = serializer.save()
        if previous_picture and previous_picture.name != getattr(user.profile_picture, 'name', None):
            storage = previous_picture.storage
            name = previous_picture.name

            def delete_previous_picture():
                try:
                    storage.delete(name)
                except Exception:
                    logger.exception("Échec de suppression de l'ancienne photo de profil: %s", name)

            transaction.on_commit(delete_previous_picture)

    @action(detail=False, methods=['get'], url_path='me')
    def me(self, request):
        return Response(serialize_user_for_session(request.user, request))

    @action(detail=False, methods=['patch'], url_path='complete-student-profile')
    def complete_student_profile(self, request):
        if request.user.role != 'student':
            raise PermissionDenied("Accès réservé aux étudiants.")

        serializer = StudentProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        with transaction.atomic():
            user = User.objects.select_for_update().get(pk=request.user.pk)
            user.username = data['username']
            user.postnom = data['postnom']
            user.prenom = data['prenom']
            user.telephone = data['telephone']
            user.save(update_fields=['username', 'postnom', 'prenom', 'telephone'])
            student, _created = Student.objects.select_for_update().get_or_create(user=user)
            student.filiere = data['filiere']
            student.niveau = data['niveau']
            student.school = data.get('school')
            student.custom_school_name = data.get('custom_school_name', '')
            student.save(update_fields=['filiere', 'niveau', 'school', 'custom_school_name'])

        return Response(serialize_user_for_session(user, request))

    @staticmethod
    def _account_files(user):
        """Capture les fichiers personnels avant que la suppression en cascade ne les masque."""
        files = []

        def add(file_field):
            if file_field and file_field.name:
                files.append((file_field.storage, file_field.name))

        add(user.profile_picture)
        try:
            student = user.student
        except Student.DoesNotExist:
            student = None

        if student:
            add(student.cv)
            for candidature in student.candidature_set.all():
                add(candidature.letter_of_support)
            for affectation in student.affectationstage_set.all():
                add(affectation.convention_pdf)

        return files

    @action(detail=False, methods=['delete'], url_path='delete-account')
    def delete_account(self, request):
        """Supprime définitivement le compte connecté et ses données associées."""
        password = request.data.get('password')
        if not password:
            return Response(
                {'detail': 'Le mot de passe actuel est requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not request.user.check_password(password):
            return Response(
                {'detail': 'Mot de passe incorrect.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        files = self._account_files(request.user)
        with transaction.atomic():
            request.user.delete()

            def delete_personal_files():
                for storage, name in files:
                    try:
                        storage.delete(name)
                    except Exception:
                        # La suppression du compte ne doit pas être annulée si le stockage
                        # distant est momentanément indisponible, mais l'incident doit être
                        # visible afin que l'exploitation puisse purger le fichier restant.
                        logger.exception("Échec de suppression d'un fichier de compte: %s", name)

            transaction.on_commit(delete_personal_files)

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['post'], url_path='activate')
    def activate_account(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'Token manquant'}, status=status.HTTP_400_BAD_REQUEST)

        payload = decode_activation_token(token)
        if not payload:
            return Response({'error': 'Token invalide ou expiré'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=payload['user_id'], email=payload['email'])
        except User.DoesNotExist:
            return Response({'error': 'Utilisateur introuvable !!'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_active:
            return Response({'message': 'Compte déjà activé'}, status=status.HTTP_200_OK)

        user.is_active = True
        user.save()
        return Response({'message': 'Compte activé avec succès'}, status=status.HTTP_200_OK)
    
    # ✅ Nouveau endpoint pour renvoyer le mail d'activation
    @action(detail=False, methods=['post'], url_path='resend-activation')
    def resend_activation(self, request):
        email = request.data.get('email')
        if not email:
            return Response({'error': 'Email manquant'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': "Aucun utilisateur trouvé avec cet email"}, status=status.HTTP_404_NOT_FOUND)

        if user.is_active:
            return Response({'message': 'Ce compte est déjà activé'}, status=status.HTTP_200_OK)

        # Générer un nouveau token et lien
        token = generate_activation_token(user)
        activation_link = f"https://totinda.com/activate?token={token}"

        # Envoyer via Celery
        send_activation_email.delay(user.email, user.username, activation_link)

        return Response({'message': 'Email de vérification renvoyé avec succès'}, status=status.HTTP_200_OK)
        
    @action(detail=False, methods=['post'], url_path='change-password')
    def change_password(self, request):
        user = request.user
        data = request.data

        old_password = data.get('old_password')
        new_password = data.get('new_password')

        if not user.check_password(old_password):
            return Response({"detail": "Ancien mot de passe incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            validate_password(new_password, user=user)
        except Exception as e:
            return Response({"detail": e.messages}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()

        return Response({"detail": "Mot de passe mis à jour avec succès."})

class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Student.objects.all()
        if user.role == 'student':
            return Student.objects.filter(user=user)
        company = company_for_user(user)
        if company:
            return Student.objects.filter(
                candidature__offre_stage__company=company
            ).distinct()
        if user.role == 'school':
            return Student.objects.filter(school__schooluser__user=user).distinct()
        return Student.objects.none()

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez modifier que votre profil étudiant.")
        serializer.save(user=serializer.instance.user)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff and instance.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez supprimer que votre profil étudiant.")
        instance.delete()

class SchoolPagination(LimitOffsetPagination):
    default_limit = 20
    max_limit = 50


class SchoolViewSet(viewsets.ModelViewSet):
    queryset = School.objects.all().order_by('name', 'province', 'territory')
    serializer_class = SchoolSerializer
    pagination_class = SchoolPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'sigle', 'province', 'territory']
    ordering_fields = ['name', 'province', 'territory']
    ordering = ['name', 'province', 'territory']

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsStaffPermission()]

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.is_authenticated and self.request.user.is_staff:
            return queryset
        return queryset.filter(is_active=True)

class SchoolUserViewSet(viewsets.ModelViewSet):
    queryset = SchoolUser.objects.all()
    serializer_class = SchoolUserSerializer
    permission_classes = [IsStaffPermission]

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return super().get_permissions()

    def perform_update(self, serializer):
        previous_logo = serializer.instance.logo
        company = serializer.save()
        if previous_logo and previous_logo.name != getattr(company.logo, 'name', None):
            storage = previous_logo.storage
            name = previous_logo.name
            transaction.on_commit(lambda: storage.delete(name))

    def perform_destroy(self, instance):
        logo = instance.logo
        storage = logo.storage if logo else None
        name = logo.name if logo else None
        instance.delete()
        if storage and name:
            transaction.on_commit(lambda: storage.delete(name))

class CompanyUserViewSet(viewsets.ModelViewSet):
    queryset = CompanyUser.objects.all()
    serializer_class = CompanyUserSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_staff:
            return CompanyUser.objects.all()
        return CompanyUser.objects.filter(user=self.request.user)

class OffreStageViewSet(viewsets.ModelViewSet):
    queryset = OffreStage.objects.all().order_by('-id')
    serializer_class = OffreStageSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsAuthenticated()]
        return super().get_permissions()

    def get_queryset(self):
        return OffreStage.objects.annotate(
            nombre_candidats=Count('candidature')
        )

    def perform_update(self, serializer):
        company = company_for_user(self.request.user)
        if not self.request.user.is_staff and serializer.instance.company != company:
            raise PermissionDenied("Cette offre appartient à une autre entreprise.")
        serializer.save(company=serializer.instance.company)

    def perform_destroy(self, instance):
        company = company_for_user(self.request.user)
        if not self.request.user.is_staff and instance.company != company:
            raise PermissionDenied("Cette offre appartient à une autre entreprise.")
        instance.delete()

    @action(detail=False, methods=['get'], url_path='offresactives')
    def offres_actives(self, request):
        user = request.user
        if not user.is_authenticated:
            return Response({"error": "Utilisateur non authentifié."}, status=status.HTTP_401_UNAUTHORIZED)

        student = Student.objects.filter(user=user).first()
        if not student:
            return Response({"error": "Profil étudiant introuvable."}, status=status.HTTP_404_NOT_FOUND)

        offres = OffreStage.objects.filter(
            is_active=True,
            end_date__gte=timezone.localdate(),
        ).annotate(
            nombre_candidats=Count("candidature")
        ).select_related(
            "company__companysubscription__plan"
        ).order_by('-published_at')
        serializer = self.get_serializer(offres, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
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
    MAX_CANDIDATURES_GRATUIT = 5
    queryset = Candidature.objects.select_related(
        'student', 'offre_stage', 'offre_stage__company', 'reviewed_by', 'affectation'
    )

    serializer_class = CandidatureSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset.order_by('-created_at')
        if user.is_staff:
            return queryset
        if user.role == 'student':
            return queryset.filter(student__user=user)
        company = company_for_user(user)
        if company:
            return queryset.filter(offre_stage__company=company)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        offre_id = request.data.get("offre_stage")
        if not offre_id:
            raise PermissionDenied("L'ID de l'offre est requis.")

        try:
            offre = OffreStage.objects.select_related(
                "company__companysubscription__plan"
            ).get(id=offre_id)
        except OffreStage.DoesNotExist:
            raise PermissionDenied("Offre introuvable.")

        if not offre.is_active or offre.end_date < timezone.localdate():
            raise ValidationError({
                'code': 'offer_expired',
                'detail': "Cette offre a expiré et n'accepte plus de candidatures.",
            })

        subscription = getattr(offre.company, "companysubscription", None)
        plan = subscription.plan if subscription else None

        if plan is not None:
            if plan.price <= 0:
                nb_candidatures = Candidature.objects.filter(offre_stage=offre).count()
                if nb_candidatures >= self.MAX_CANDIDATURES_GRATUIT:
                    raise PermissionDenied(
                        "Limite de candidatures atteinte pour cette offre gratuite."
                    )
        # Si plan is None, illimité, donc pas de limite

        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Seuls les étudiants peuvent candidater.")
        completion = student_profile_completion(request.user, student)
        if not completion['can_apply']:
            raise ValidationError({
                'code': 'incomplete_profile',
                'detail': "Complétez les informations obligatoires de votre profil avant de postuler.",
                'missing_fields': completion['missing_fields'],
                'profile_completion': completion,
            })
        if Candidature.objects.filter(student=student, offre_stage=offre).exists():
            raise ValidationError("Vous avez déjà candidaté à cette offre.")

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            student=student,
            status='pending',
            company_message='',
            reviewed_at=None,
            reviewed_by=None,
        )
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        user = self.request.user
        previous_status = serializer.instance.status
        changed_fields = set(serializer.validated_data)
        if user.role == 'student' and changed_fields - {'motivation', 'letter_of_support'}:
            raise PermissionDenied("Un étudiant ne peut modifier que sa motivation et sa lettre.")
        if user.role == 'company' and changed_fields - {'status', 'company_message'}:
            raise PermissionDenied("Une entreprise ne peut modifier que la décision et son message.")

        save_kwargs = {
            'student': serializer.instance.student,
            'offre_stage': serializer.instance.offre_stage,
        }
        if user.is_staff or user.role == 'company':
            decision_status = serializer.validated_data.get('status', serializer.instance.status)
            if decision_status in {'accepted', 'rejected'}:
                message = serializer.validated_data.get(
                    'company_message', serializer.instance.company_message
                ).strip()
                if not message:
                    raise ValidationError({
                        'company_message': "Un message est requis pour accepter ou rejeter une candidature."
                    })
                save_kwargs.update(
                    company_message=message,
                    reviewed_at=timezone.now(),
                    reviewed_by=user,
                )
            elif decision_status == 'pending':
                save_kwargs.update(
                    company_message='',
                    reviewed_at=None,
                    reviewed_by=None,
                )

        with transaction.atomic():
            candidature = serializer.save(**save_kwargs)
            self._sync_affectation(candidature)
            if (
                candidature.status in {'accepted', 'rejected'}
                and candidature.status != previous_status
            ):
                accepted = candidature.status == 'accepted'
                affectation_id = (
                    getattr(getattr(candidature, 'affectation', None), 'id', None)
                    if accepted else None
                )
                notify_user(
                    candidature.student.user,
                    'application_decision',
                    'Candidature acceptée' if accepted else 'Candidature non retenue',
                    (
                        f"{candidature.offre_stage.company.name} a accepté votre candidature pour « {candidature.offre_stage.title} »."
                        if accepted else
                        f"{candidature.offre_stage.company.name} a répondu à votre candidature pour « {candidature.offre_stage.title} »."
                    ),
                    {
                        'application_id': candidature.id,
                        'offer_id': candidature.offre_stage_id,
                        'stage_id': affectation_id,
                        'status': candidature.status,
                    },
                    f"application-decision:{candidature.id}:{candidature.status}",
                )

    @staticmethod
    def _stage_status_for_dates(start_date, end_date):
        today = timezone.localdate()
        if end_date and end_date < today:
            return 'completed'
        if start_date and start_date <= today:
            return 'in_progress'
        return 'upcoming'

    def _sync_affectation(self, candidature):
        if candidature.status == 'accepted':
            offer = candidature.offre_stage
            stage_status = self._stage_status_for_dates(offer.start_date, offer.end_date)
            affectation, created = AffectationStage.objects.get_or_create(
                candidature=candidature,
                defaults={
                    'student': candidature.student,
                    'offre_stage': offer,
                    'start_date': offer.start_date,
                    'end_date': offer.end_date,
                    'status': stage_status,
                },
            )
            if not created and affectation.status == 'cancelled':
                affectation.status = stage_status
                affectation.save(update_fields=['status'])
            return

        AffectationStage.objects.filter(candidature=candidature).exclude(
            status='completed'
        ).update(status='cancelled')
    
    @action(detail=False, methods=['get'], url_path='by-student/(?P<student_id>[^/.]+)')
    def by_student(self, request, student_id=None):
        candidatures = self.get_queryset().filter(student_id=student_id)
        serializer = self.get_serializer(candidatures, many=True)
        return Response(serializer.data)
    @action(detail=False, methods=['get'], url_path='by-company/(?P<company_id>[^/.]+)')
    def by_company(self, request, company_id=None):
        candidatures = self.get_queryset().filter(offre_stage__company_id=company_id)
        serializer = self.get_serializer(candidatures, many=True)
        return Response(serializer.data)

class AffectationStageViewSet(viewsets.ModelViewSet):
    queryset = AffectationStage.objects.select_related(
        'candidature', 'student__user', 'offre_stage__company'
    ).prefetch_related('weekly_reports').order_by('-assigned_on')
    serializer_class = AffectationStageSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        if user.is_staff:
            return queryset
        if user.role == 'student':
            return queryset.filter(student__user=user)
        company = company_for_user(user)
        if company:
            return queryset.filter(offre_stage__company=company)
        return queryset.none()

    def create(self, request, *args, **kwargs):
        raise PermissionDenied(
            "Une affectation est créée automatiquement après l'acceptation d'une candidature."
        )

    def perform_update(self, serializer):
        user = self.request.user
        if user.role == 'student' and not user.is_staff:
            raise PermissionDenied("Un étudiant ne peut pas modifier son parcours de stage.")

        allowed_company_fields = {
            'start_date', 'end_date', 'status', 'objectives',
            'convention_pdf', 'supervisor_name', 'supervisor_email',
        }
        if not user.is_staff and set(serializer.validated_data) - allowed_company_fields:
            raise PermissionDenied("Ces informations ne peuvent pas être modifiées par l'entreprise.")
        certified_fields = {'start_date', 'end_date', 'status', 'supervisor_name'}
        if (
            set(serializer.validated_data) & certified_fields
            and serializer.instance.certificates.filter(revoked_at__isnull=True).exists()
        ):
            raise ValidationError(
                "Une attestation valide protège ces informations. Révoquez-la avant toute correction."
            )
        serializer.save()

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Seul un administrateur peut supprimer un parcours de stage.")
        instance.delete()

    @action(detail=True, methods=['get'], url_path='attestation')
    def attestation(self, request, pk=None):
        affectation = self.get_object()
        if affectation.status != 'completed':
            raise ValidationError("Le stage doit être terminé avant la génération de l'attestation.")
        if not affectation.start_date or not affectation.end_date:
            raise ValidationError("Les dates du stage doivent être renseignées.")
        try:
            evaluation = affectation.candidature.evaluation
        except (AttributeError, ObjectDoesNotExist):
            raise ValidationError("L'évaluation finale doit être publiée avant l'attestation.")

        try:
            current_hash = certificate_data_hash(affectation, evaluation)
            certificate = StageCertificate.objects.filter(
                affectation=affectation,
                revoked_at__isnull=True,
            ).first()
            if certificate:
                if certificate.data_hash and certificate.data_hash != current_hash:
                    raise ValidationError(
                        "Les données ne correspondent plus à l'attestation active. Révoquez-la avant une nouvelle émission."
                    )
                if not certificate.data_hash:
                    certificate.data_hash = current_hash
                    certificate.save(update_fields=['data_hash'])
            else:
                last_version = StageCertificate.objects.filter(
                    affectation=affectation,
                ).aggregate(max_version=Max('version'))['max_version'] or 0
                certificate = StageCertificate.objects.create(
                    affectation=affectation,
                    version=last_version + 1,
                    data_hash=current_hash,
                )
            public_site_url = getattr(
                settings,
                'PUBLIC_SITE_URL',
                'https://totinda.com',
            ).rstrip('/')
            verification_url = (
                f"{public_site_url}/verifier-attestation"
                f"?reference={certificate.reference}"
            )
            pdf, reference = build_stage_certificate(
                affectation,
                evaluation,
                certificate.reference,
                verification_url,
            )
        except ValidationError:
            raise
        except Exception:
            logger.exception(
                "Échec de génération de l'attestation pour l'affectation %s",
                affectation.pk,
            )
            raise APIException(
                "La génération PDF a échoué. Consultez les logs du serveur."
            )
        student_name = affectation.student.user.username.replace(' ', '-').lower()
        return Response({
            'filename': f'attestation-stage-{student_name}.pdf',
            'reference': reference,
            'version': certificate.version,
            'issued_at': certificate.issued_at,
            'verification_count': certificate.verification_count,
            'content_base64': base64.b64encode(pdf).decode('ascii'),
        })


class StageCertificateViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action == 'verify':
            return [AllowAny()]
        return super().get_permissions()

    @action(detail=False, methods=['get'], url_path='verify')
    def verify(self, request):
        reference = request.query_params.get('reference', '').strip().upper()
        if not reference:
            raise ValidationError({'reference': "Saisissez une référence d'attestation."})
        certificate = StageCertificate.objects.select_related(
            'affectation__student__user',
            'affectation__offre_stage__company',
        ).filter(reference=reference).first()
        if not certificate:
            return Response({'valid': False, 'reference': reference})

        now = timezone.now()
        StageCertificate.objects.filter(pk=certificate.pk).update(
            verification_count=F('verification_count') + 1,
            last_verified_at=now,
        )
        certificate.verification_count += 1
        certificate.last_verified_at = now
        affectation = certificate.affectation
        user = affectation.student.user
        student_name = ' '.join(filter(None, [user.prenom, user.postnom, user.username]))
        return Response({
            'valid': certificate.is_valid,
            'reference': certificate.reference,
            'version': certificate.version,
            'student_name': student_name,
            'company_name': affectation.offre_stage.company.name,
            'internship_title': affectation.offre_stage.title,
            'start_date': affectation.start_date,
            'end_date': affectation.end_date,
            'issued_at': certificate.issued_at,
            'revoked_at': certificate.revoked_at,
        })

    @action(detail=False, methods=['get'], url_path='history')
    def history(self, request):
        stage_id = request.query_params.get('stage_id')
        if not stage_id:
            raise ValidationError({'stage_id': "Parcours de stage requis."})
        certificates = StageCertificate.objects.select_related(
            'affectation__student__user',
            'affectation__offre_stage__company',
        ).filter(affectation_id=stage_id)
        first = certificates.first()
        if first:
            affectation = first.affectation
            company = company_for_user(request.user)
            is_student = affectation.student.user_id == request.user.id
            is_company = company and affectation.offre_stage.company_id == company.id
            if not request.user.is_staff and not is_student and not is_company:
                raise PermissionDenied("Ce parcours ne vous appartient pas.")
        return Response([{
            'reference': item.reference,
            'version': item.version,
            'issued_at': item.issued_at,
            'valid': item.is_valid,
            'revoked_at': item.revoked_at,
            'revocation_reason': item.revocation_reason,
            'verification_count': item.verification_count,
            'last_verified_at': item.last_verified_at,
        } for item in certificates])

    @action(detail=True, methods=['post'], url_path='revoke')
    def revoke(self, request, pk=None):
        certificate = StageCertificate.objects.select_related(
            'affectation__offre_stage__company',
        ).filter(reference=pk).first()
        if not certificate:
            raise ValidationError("Attestation introuvable.")
        company = company_for_user(request.user)
        if not request.user.is_staff and (
            not company or certificate.affectation.offre_stage.company_id != company.id
        ):
            raise PermissionDenied("Seule l'entreprise émettrice peut révoquer cette attestation.")
        if not certificate.is_valid:
            raise ValidationError("Cette attestation est déjà révoquée.")
        reason = request.data.get('reason', '').strip()
        if len(reason) < 10:
            raise ValidationError({'reason': "Indiquez un motif précis d'au moins 10 caractères."})
        certificate.revoked_at = timezone.now()
        certificate.revoked_by = request.user
        certificate.revocation_reason = reason
        certificate.save(update_fields=['revoked_at', 'revoked_by', 'revocation_reason'])
        return Response({
            'reference': certificate.reference,
            'valid': False,
            'revoked_at': certificate.revoked_at,
            'revocation_reason': certificate.revocation_reason,
        })


class StageWeeklyReportViewSet(viewsets.ModelViewSet):
    queryset = StageWeeklyReport.objects.select_related(
        'affectation__student__user',
        'affectation__offre_stage__company',
        'validated_by',
    )
    serializer_class = StageWeeklyReportSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset
        affectation_id = self.request.query_params.get('affectation')
        if affectation_id:
            queryset = queryset.filter(affectation_id=affectation_id)
        if user.is_staff:
            return queryset
        if user.role == 'student':
            return queryset.filter(affectation__student__user=user)
        company = company_for_user(user)
        if company:
            return queryset.filter(affectation__offre_stage__company=company).exclude(status='draft')
        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user
        if user.is_staff:
            serializer.save()
            return
        if user.role != 'student':
            raise PermissionDenied("Seul l'étudiant peut créer un rapport hebdomadaire.")
        affectation = serializer.validated_data['affectation']
        if affectation.student.user_id != user.id:
            raise PermissionDenied("Ce parcours de stage ne vous appartient pas.")
        if affectation.status == 'cancelled':
            raise ValidationError("Impossible d'ajouter un rapport à un stage interrompu.")
        report_status = serializer.validated_data.get('status', 'draft')
        if report_status not in {'draft', 'submitted'}:
            raise ValidationError({'status': "Un étudiant ne peut pas valider son rapport."})
        report = serializer.save(
            submitted_at=timezone.now() if report_status == 'submitted' else None,
        )
        if report_status == 'submitted':
            student_name = report.affectation.student.user.username
            notify_company(
                report.affectation.offre_stage.company,
                'report_submitted',
                'Nouveau rapport hebdomadaire',
                f"{student_name} a soumis son rapport pour la semaine du {report.week_start}.",
                {'stage_id': report.affectation_id, 'report_id': report.id},
                f"report-submitted:{report.id}",
            )

    def perform_update(self, serializer):
        user = self.request.user
        report = serializer.instance
        company = company_for_user(user)
        # Un utilisateur d'entreprise peut aussi être marqué staff pour accéder
        # à l'administration. Il doit néanmoins suivre le workflow entreprise
        # afin d'enregistrer le validateur et de notifier l'étudiant.
        if user.is_staff and not company:
            serializer.save()
            return

        fields = set(serializer.validated_data)
        if user.role == 'student':
            if report.status == 'validated':
                raise PermissionDenied("Un rapport validé ne peut plus être modifié.")
            allowed = {'activities', 'learnings', 'difficulties', 'status'}
            if fields - allowed:
                raise PermissionDenied("Ces informations ne peuvent pas être modifiées par l'étudiant.")
            report_status = serializer.validated_data.get('status', report.status)
            if report_status not in {'draft', 'submitted'}:
                raise ValidationError({'status': "Un étudiant ne peut pas valider son rapport."})
            previous_status = report.status
            updated_report = serializer.save(
                submitted_at=timezone.now() if report_status == 'submitted' else None,
                validated_at=None,
                validated_by=None,
            )
            if previous_status != 'submitted' and report_status == 'submitted':
                notify_company(
                    updated_report.affectation.offre_stage.company,
                    'report_submitted',
                    'Nouveau rapport hebdomadaire',
                    f"{updated_report.affectation.student.user.username} a soumis son rapport pour la semaine du {updated_report.week_start}.",
                    {'stage_id': updated_report.affectation_id, 'report_id': updated_report.id},
                    f"report-submitted:{updated_report.id}",
                )
            return

        if not company or report.affectation.offre_stage.company_id != company.id:
            raise PermissionDenied("Ce rapport ne concerne pas votre entreprise.")
        if fields - {'company_comment', 'status'}:
            raise PermissionDenied("L'entreprise ne peut modifier que son commentaire et la validation.")
        report_status = serializer.validated_data.get('status', report.status)
        if report.status == 'draft' or report_status != 'validated':
            raise ValidationError({'status': "Seul un rapport soumis peut être validé."})
        company_comment = serializer.validated_data.get(
            'company_comment', report.company_comment
        ).strip()
        if not company_comment:
            raise ValidationError({
                'company_comment': "Un commentaire est requis pour valider le rapport."
            })
        updated_report = serializer.save(
            status='validated',
            company_comment=company_comment,
            validated_at=timezone.now(),
            validated_by=user,
        )
        notify_user(
            updated_report.affectation.student.user,
            'report_validated',
            'Rapport hebdomadaire validé',
            f"L’entreprise a validé votre rapport de la semaine du {updated_report.week_start} et a laissé un commentaire.",
            {'stage_id': updated_report.affectation_id, 'report_id': updated_report.id},
            f"report-validated:{updated_report.id}",
        )

    def perform_destroy(self, instance):
        if not self.request.user.is_staff:
            raise PermissionDenied("Seul un administrateur peut supprimer un rapport hebdomadaire.")
        instance.delete()

class EvaluationViewSet(viewsets.ModelViewSet):
    queryset = Evaluation.objects.all()
    serializer_class = EvaluationSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Evaluation.objects.all()
        company = company_for_user(self.request.user)
        if company:
            return Evaluation.objects.filter(candidature__offre_stage__company=company)
        return Evaluation.objects.filter(candidature__student__user=self.request.user)

    def _ensure_company_owns_candidature(self, candidature):
        if self.request.user.is_staff:
            return
        if company_for_user(self.request.user) != candidature.offre_stage.company:
            raise PermissionDenied("Seule l'entreprise concernée peut gérer cette évaluation.")

    def create(self, request, *args, **kwargs):
        if not request.user.is_staff and not company_for_user(request.user):
            raise PermissionDenied("Seule une entreprise peut créer une évaluation finale.")
        return super().create(request, *args, **kwargs)

    def perform_create(self, serializer):
        candidature = serializer.validated_data.get('candidature')
        self._ensure_company_owns_candidature(candidature)
        evaluation = serializer.save()
        notify_user(
            candidature.student.user,
            'evaluation_published',
            'Évaluation finale publiée',
            f"{candidature.offre_stage.company.name} a publié l’évaluation finale de votre stage.",
            {'stage_id': candidature.affectation.id, 'evaluation_id': evaluation.id},
            f"evaluation-published:{evaluation.id}",
        )

    def perform_update(self, serializer):
        self._ensure_company_owns_candidature(serializer.instance.candidature)
        candidature = serializer.instance.candidature
        if candidature.affectation.certificates.filter(revoked_at__isnull=True).exists():
            raise ValidationError(
                "Cette évaluation est protégée par une attestation valide. Révoquez l'attestation avant de la modifier."
            )
        evaluation = serializer.save(candidature=candidature)
        notify_user(
            candidature.student.user,
            'evaluation_published',
            'Évaluation finale mise à jour',
            f"{candidature.offre_stage.company.name} a mis à jour l’évaluation finale de votre stage.",
            {'stage_id': candidature.affectation.id, 'evaluation_id': evaluation.id},
        )

    def perform_destroy(self, instance):
        self._ensure_company_owns_candidature(instance.candidature)
        instance.delete()
    @action(detail=False, methods=['get'], url_path='by-candidature/(?P<candidature_id>[^/.]+)')
    def by_candidature(self, request, candidature_id=None):
        evaluations = self.get_queryset().filter(candidature_id=candidature_id)
        serializer = self.get_serializer(evaluations, many=True)
        return Response(serializer.data)


class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        return Response({'count': self.get_queryset().filter(read_at__isnull=True).count()})

    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.read_at:
            notification.read_at = timezone.now()
            notification.save(update_fields=['read_at'])
        return Response(self.get_serializer(notification).data)

    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({'updated': updated})


class PushDeviceViewSet(viewsets.ModelViewSet):
    serializer_class = PushDeviceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        return PushDevice.objects.filter(user=self.request.user)

    @action(detail=False, methods=['post'], url_path='deactivate')
    def deactivate(self, request):
        token = str(request.data.get('expo_push_token', '')).strip()
        if not token:
            raise ValidationError({'expo_push_token': "Ce champ est requis."})
        updated = self.get_queryset().filter(expo_push_token=token).update(is_active=False)
        return Response({'updated': updated})

class FormationViewSet(viewsets.ModelViewSet):
    queryset = Formation.objects.all()
    serializer_class = FormationSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Formation.objects.all()
        company = company_for_user(self.request.user)
        if company:
            return Formation.objects.filter(
                student__candidature__offre_stage__company=company
            ).distinct()
        return Formation.objects.filter(student__user=self.request.user)

    def perform_create(self, serializer):
        try:
            serializer.save(student=Student.objects.get(user=self.request.user))
        except Student.DoesNotExist:
            raise PermissionDenied("Profil étudiant requis.")

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.student.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez modifier que vos formations.")
        serializer.save(student=serializer.instance.student)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff and instance.student.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez supprimer que vos formations.")
        instance.delete()
    @action(detail=False, methods=['get'], url_path='by-student/(?P<student_id>[^/.]+)')
    def by_student(self, request, student_id=None):
        formations = self.get_queryset().filter(student_id=student_id)
        serializer = self.get_serializer(formations, many=True)
        return Response(serializer.data)

class CompetenceViewSet(viewsets.ModelViewSet):
    queryset = Competence.objects.all()
    serializer_class = CompetenceSerializer
    permission_classes = [IsAuthenticated, IsRelatedObjectOwnerOrStaff]

    def get_queryset(self):
        if self.request.user.is_staff:
            return Competence.objects.all()
        company = company_for_user(self.request.user)
        if company:
            return Competence.objects.filter(
                student__candidature__offre_stage__company=company
            ).distinct()
        return Competence.objects.filter(student__user=self.request.user)

    def perform_create(self, serializer):
        try:
            serializer.save(student=Student.objects.get(user=self.request.user))
        except Student.DoesNotExist:
            raise PermissionDenied("Profil étudiant requis.")

    def perform_update(self, serializer):
        if not self.request.user.is_staff and serializer.instance.student.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez modifier que vos compétences.")
        serializer.save(student=serializer.instance.student)

    def perform_destroy(self, instance):
        if not self.request.user.is_staff and instance.student.user_id != self.request.user.id:
            raise PermissionDenied("Vous ne pouvez supprimer que vos compétences.")
        instance.delete()
    @action(detail=False, methods=['get'], url_path='by-student/(?P<student_id>[^/.]+)')
    def by_student(self, request, student_id=None):
        competences = self.get_queryset().filter(student_id=student_id)
        serializer = self.get_serializer(competences, many=True)
        return Response(serializer.data)

class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):  # uniquement GET (list, retrieve)
    queryset = SubscriptionPlan.objects.all()
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [AllowAny]

    # serializer_class = CompanySubscriptionSerializer
    # permission_classes = [IsAuthenticated]
  
    # def get_queryset(self):
    #     company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()
    #     if company_user:
    #         company = company_user.company
    #     # On filtre les abonnements de la compagnie de l'utilisateur connecté
    #     return CompanySubscription.objects.filter(company=company)

class CompanySubscriptionViewSet(viewsets.ModelViewSet):
    serializer_class = CompanySubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        company_user = CompanyUser.objects.filter(user=self.request.user, is_active=True).first()

        if user.role != 'company' or not company_user:
            return CompanySubscription.objects.none()
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
        if plan.price > 0:
            raise PermissionDenied("Un paiement vérifié est requis pour activer ce plan.")

        # Calcul de la date de fin (exemple : 30 jours)
        end_date = timezone.now() + timedelta(days=30)
        if plan.max_offres is None:
            nbre_offres = None
        else:   
            nbre_offres = plan.max_offres  # Nombre d'offres 

        serializer.save(company=company, plan=plan, end_date=end_date, nbre_offres=nbre_offres)
        try:
            send_welcome_email.delay(
                self.request.user.email,
                self.request.user.username,
                plan.name,
                timezone.now(),
                end_date
            )  # Envoi de l'email de bienvenue en tâche de fond
        except Exception as e:
            pass

    def update(self, request, *args, **kwargs):
        """Changer ou renouveler l'abonnement"""
        instance = self.get_object()
        plan_id = request.data.get("plan_id")

        if not plan_id:
            raise APIException(detail={"error": "Plan requis."}, code=status.HTTP_400_BAD_REQUEST)

        try:
            new_plan = SubscriptionPlan.objects.get(id=plan_id)
        except SubscriptionPlan.DoesNotExist:
            raise APIException(detail={"error": "Plan invalide."}, code=status.HTTP_400_BAD_REQUEST)
        if new_plan.price > 0:
            raise PermissionDenied("Un paiement vérifié est requis pour modifier ce plan.")

        # ✅ Empêcher plusieurs changements planifiés
        if instance.next_plan:
            raise APIException(detail={
                "error": f"Un changement vers '{instance.next_plan.name}' est déjà programmé pour le {instance.change_effective_date}."
            }, code=status.HTTP_400_BAD_REQUEST)

        # ✅ Vérifier si abonnement actif
        is_active = instance.is_active()
        remaining = instance.remaining_offres()  # None si illimité
        current_is_unlimited = instance.plan.max_offres is None
        new_is_unlimited = new_plan.max_offres is None

        # Helper : appliquer immédiatement un plan
        def apply_plan(start_now=True):
            instance.plan = new_plan
            if start_now:
                instance.start_date = timezone.now()
            instance.end_date = timezone.now() + timedelta(days=new_plan.duration_days)
            instance.nbre_offres = None if new_is_unlimited else new_plan.max_offres
            instance.next_plan = None
            instance.change_effective_date = None
            instance.save()
            # Email asynchrone
            try:
                send_welcome_email.delay(
                    self.request.user.email,
                    self.request.user.username,
                    new_plan.name,
                    instance.start_date,
                    instance.end_date
                )
            except Exception:
                pass  # On ignore pour éviter un rollback API
            return Response({
                "status": "applied",
                "message": f"Le plan '{new_plan.name}' a été appliqué immédiatement.",
                "subscription": self.get_serializer(instance).data
            })

        if is_active:
            # ✅ Cas 1 : limité → illimité (appliquer immédiatement)
            if not current_is_unlimited and new_is_unlimited:
                return apply_plan()

            # ✅ Cas 2 : illimité → limité (planifier pour la fin)
            if current_is_unlimited and not new_is_unlimited:
                instance.next_plan = new_plan
                instance.change_effective_date = instance.end_date
                instance.save()
                return Response({
                    "status": "scheduled",
                    "message": f"Le changement vers '{new_plan.name}' sera appliqué à partir du {instance.end_date}.",
                    "subscription": self.get_serializer(instance).data
                })

            # ✅ Cas 3 : limité → limité
            if not current_is_unlimited and not new_is_unlimited:
                if remaining and remaining > 0:
                    # Ajouter les offres restantes + prolonger durée
                    instance.plan = new_plan
                    instance.end_date += timedelta(days=new_plan.duration_days)
                    instance.nbre_offres += new_plan.max_offres
                    instance.next_plan = None
                    instance.change_effective_date = None
                    instance.save()
                    send_welcome_email.delay(
                        self.request.user.email,
                        self.request.user.username,
                        new_plan.name,
                        instance.start_date,
                        instance.end_date
                    )
                    return Response({
                        "status": "applied",
                        "message": f"Le plan '{new_plan.name}' a été appliqué immédiatement avec {instance.nbre_offres} offres cumulées jusqu'au {instance.end_date}.",
                        "subscription": self.get_serializer(instance).data
                    })
                else:
                    # Limité mais sans offres → appliquer immédiatement
                    return apply_plan()

            # ✅ Cas 4 : illimité → illimité (peu courant, mais on force un reset)
            if current_is_unlimited and new_is_unlimited:
                instance.plan = new_plan
                instance.end_date += timedelta(days=new_plan.duration_days)
                instance.next_plan = None
                instance.change_effective_date = None
                instance.save()
                send_welcome_email.delay(
                    self.request.user.email,
                    self.request.user.username,
                    new_plan.name,
                    instance.start_date,
                    instance.end_date
                )
                return Response({
                    "status": "applied",
                    "message": f"Le plan '{new_plan.name}' a été prolongé jusqu'au {instance.end_date}.",
                    "subscription": self.get_serializer(instance).data
                })

        # ✅ Cas abonnement expiré → appliquer immédiatement
        return apply_plan()
    
    def destroy(self, request, *args, **kwargs):
        return Response({"error": "Suppression non autorisée."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class PaymentViewSet(viewsets.ReadOnlyModelViewSet):
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

    @staticmethod
    def _paypal_access_token():
        client_id = getattr(settings, 'PAYPAL_CLIENT_ID', '')
        client_secret = getattr(settings, 'PAYPAL_CLIENT_SECRET', '')
        base_url = getattr(settings, 'PAYPAL_API_URL', 'https://api-m.paypal.com')
        if not client_id or not client_secret:
            raise APIException("Configuration PayPal absente.")
        response = requests.post(
            f"{base_url}/v1/oauth2/token",
            auth=(client_id, client_secret),
            data={'grant_type': 'client_credentials'},
            timeout=15,
        )
        if not response.ok:
            raise APIException("Impossible de vérifier le paiement PayPal.")
        return base_url, response.json()['access_token']

    @classmethod
    def _verify_paypal(cls, order_id, expected_amount, company_id):
        base_url, token = cls._paypal_access_token()
        response = requests.get(
            f"{base_url}/v2/checkout/orders/{order_id}",
            headers={'Authorization': f'Bearer {token}'},
            timeout=15,
        )
        if not response.ok:
            raise ValidationError("Commande PayPal introuvable.")
        order = response.json()
        captures = [
            capture
            for unit in order.get('purchase_units', [])
            for capture in unit.get('payments', {}).get('captures', [])
            if capture.get('status') == 'COMPLETED'
        ]
        if order.get('status') != 'COMPLETED' or not captures:
            raise ValidationError("Le paiement PayPal n'est pas terminé.")
        if any(unit.get('custom_id') != str(company_id) for unit in order.get('purchase_units', [])):
            raise ValidationError("La commande PayPal appartient à une autre entreprise.")
        try:
            paid = sum(Decimal(c['amount']['value']) for c in captures)
        except (KeyError, InvalidOperation):
            raise ValidationError("Montant PayPal invalide.")
        if paid != expected_amount or any(c['amount'].get('currency_code') != 'USD' for c in captures):
            raise ValidationError("Le montant PayPal ne correspond pas au plan.")
        return f"paypal:{order_id}"

    @staticmethod
    def _verify_stripe(payment_intent_id, expected_amount, company_id, plan_id):
        secret = getattr(settings, 'STRIPE_SECRET_KEY', '')
        if not secret:
            raise APIException("Configuration Stripe absente.")
        response = requests.get(
            f"https://api.stripe.com/v1/payment_intents/{payment_intent_id}",
            auth=(secret, ''),
            timeout=15,
        )
        if not response.ok:
            raise ValidationError("Paiement Stripe introuvable.")
        payment = response.json()
        expected_cents = int(expected_amount * 100)
        if (
            payment.get('status') != 'succeeded'
            or payment.get('amount_received') != expected_cents
            or payment.get('currency') != 'usd'
            or payment.get('metadata', {}).get('company_id') != str(company_id)
            or payment.get('metadata', {}).get('plan_id') != str(plan_id)
        ):
            raise ValidationError("Le paiement Stripe ne correspond pas au plan.")
        return f"stripe:{payment_intent_id}"

    @action(detail=False, methods=['post'], url_path='confirm')
    def confirm(self, request):
        company = company_for_user(request.user)
        if not company:
            raise PermissionDenied("Compte entreprise requis.")
        try:
            plan = SubscriptionPlan.objects.get(pk=request.data.get('plan_id'))
        except (SubscriptionPlan.DoesNotExist, TypeError, ValueError):
            raise ValidationError("Plan invalide.")

        provider = request.data.get('provider')
        external_id = request.data.get('transaction_id')
        if plan.price == 0:
            transaction_id = f"free:{company.pk}:{plan.pk}"
        elif provider == 'paypal' and external_id:
            transaction_id = self._verify_paypal(external_id, plan.price, company.pk)
        elif provider == 'stripe' and external_id:
            transaction_id = self._verify_stripe(external_id, plan.price, company.pk, plan.pk)
        else:
            raise ValidationError("Fournisseur ou identifiant de paiement invalide.")

        with transaction.atomic():
            payment, payment_created = Payment.objects.select_for_update().get_or_create(
                transaction_id=transaction_id,
                defaults={
                    'company': company,
                    'amount': plan.price,
                    'status': 'success',
                },
            )
            if payment.company_id != company.pk or payment.amount != plan.price:
                raise PermissionDenied("Ce paiement est déjà associé à une autre opération.")
            if not payment_created:
                return Response({
                    'message': 'Paiement déjà confirmé.',
                    'payment': self.get_serializer(payment).data,
                })

            subscription, subscription_created = CompanySubscription.objects.select_for_update().get_or_create(
                company=company,
                defaults={
                    'plan': plan,
                    'end_date': timezone.now() + timedelta(days=plan.duration_days),
                    'nbre_offres': plan.max_offres,
                },
            )
            if subscription_created or subscription.plan_id != plan.pk or not subscription.is_active():
                subscription.plan = plan
                subscription.start_date = timezone.now()
                subscription.end_date = timezone.now() + timedelta(days=plan.duration_days)
                subscription.nbre_offres = plan.max_offres
            else:
                subscription.end_date += timedelta(days=plan.duration_days)
                if subscription.nbre_offres is not None and plan.max_offres is not None:
                    subscription.nbre_offres += plan.max_offres
            subscription.next_plan = None
            subscription.change_effective_date = None
            subscription.save()

        return Response({
            'message': 'Paiement vérifié et abonnement activé.',
            'payment': self.get_serializer(payment).data,
        }, status=status.HTTP_201_CREATED if payment_created else status.HTTP_200_OK)

    @action(detail=False, methods=['get'], url_path='by-company')
    def by_company(self, request):
        user = self.request.user
        print("DEBUG - User role:", user.role)
        if user.role != 'company':
            return Response({"error": "Ahh Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        
        company_user = CompanyUser.objects.filter(user=user, is_active=True).first()
        if not company_user:
            return Response({"error": "Aucune entreprise associée à ce compte."}, status=status.HTTP_403_FORBIDDEN)
        # if company_user.company.id != company_id:
        #     return Response({"error": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)
        payments = self.get_queryset().filter(company=company_user.company)
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)


class PartnerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Partner.objects.filter(is_active=True).order_by('position', 'id')
    serializer_class = PartnerSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    pagination_class = None


class ConfigViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer
    permission_classes = [AllowAny]
