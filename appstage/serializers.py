# serializers.py
from urllib import request
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Partner
from .models import (
    Student, School, SchoolUser, Company, CompanyUser,
    OffreStage, Candidature, AffectationStage, StageWeeklyReport, Notification, PushDevice, Evaluation, Formation, Competence, CompanySubscription, SubscriptionPlan, Payment, Config
)
from .profiles import student_profile_completion
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
# Mail de verification
from .tasks import send_activation_email
from .utils import generate_activation_token
User = get_user_model()

from django.db import transaction
from datetime import timedelta
from django.utils import timezone



def serialize_user_for_session(user, request=None):
    profile_picture_url = (
        request.build_absolute_uri(user.profile_picture.url)
        if user.profile_picture and request
        else (user.profile_picture.url if user.profile_picture else None)
    )
    user_data = {
        "id": user.id,
        "username": user.username,
        "prenom": user.prenom,
        "postnom": user.postnom,
        "telephone": user.telephone,
        "email": user.email,
        "profile_picture": profile_picture_url,
        "profile_picture_url": profile_picture_url,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role_user": user.role,
        "is_active_user": user.is_active,
        "auth_providers": list(
            user.social_identities.values_list('provider', flat=True)
        ),
        "has_usable_password": user.has_usable_password(),
    }

    if user.role == 'student':
        try:
            student = Student.objects.select_related('school').get(user=user)
            cv_url = (
                request.build_absolute_uri(student.cv.url)
                if student.cv and request
                else (student.cv.url if student.cv else None)
            )
            user_data["student"] = {
                "id_student": student.id,
                "filiere": student.filiere,
                "niveau": student.niveau,
                "cv": cv_url,
                "custom_school_name": student.custom_school_name,
                "school": {
                    "id": student.school.id,
                    "name": student.school.name,
                    "sigle": student.school.sigle,
                    "logo": (
                        request.build_absolute_uri(student.school.logo.url)
                        if student.school.logo and request
                        else (student.school.logo.url if student.school.logo else None)
                    ),
                    "category": student.school.category,
                    "ownership": student.school.ownership,
                    "territory": student.school.territory,
                    "province": student.school.province,
                    "contact_email": student.school.contact_email,
                    "address": student.school.address,
                } if student.school else None,
            }
        except Student.DoesNotExist:
            student = None
            user_data["student"] = None
        user_data["profile_completion"] = student_profile_completion(user, student)

    elif user.role == 'school':
        try:
            school_user = SchoolUser.objects.select_related('school').get(user=user)
            school = school_user.school
            user_data["school_user"] = {
                "id_school_user": school_user.id,
                "role_school": school_user.role,
                "is_active": school_user.is_active,
                "school": {
                    "id": school.id,
                    "name": school.name,
                    "email": school.contact_email,
                    "address": school.address,
                },
            }
        except SchoolUser.DoesNotExist:
            user_data["school_user"] = None

    elif user.role == 'company':
        try:
            company_user = CompanyUser.objects.select_related('company').get(user=user)
            company = company_user.company
            user_data["company_user"] = {
                "id_company_user": company_user.id,
                "role_company": company_user.role,
                "is_active": company_user.is_active,
                "company": {
                    "id": company.id,
                    "name": company.name,
                    "secteur": company.secteur,
                    "description": company.description,
                },
            }
        except CompanyUser.DoesNotExist:
            user_data["company_user"] = None

    return user_data


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = serialize_user_for_session(
            self.user,
            self.context.get('request'),
        )
        return data

class UserSerializer(serializers.ModelSerializer):
    def validate_profile_picture(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("La photo de profil ne doit pas dépasser 5 Mo.")
        return value

    class Meta:
        model = User
        fields = ['id', 'username','postnom', 'prenom', 'email', 'password', 'role','telephone', 'profile_picture']
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'read_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.is_superuser = False
        user.is_staff = False
        user.is_active = False
        user.save()

        token = generate_activation_token(user)
        activation_link = f"https://totinda.com/activate?token={token}"

        # Utilisation de Celery
        send_activation_email.delay(user.email, user.username, activation_link)

        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        instance = super().update(instance, validated_data)
        if password:
            instance.set_password(password)
            instance.save(update_fields=['password'])
        return instance


class SchoolSerializer(serializers.ModelSerializer):
    class Meta:
        model = School
        fields = '__all__'

class SchoolUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    school = SchoolSerializer()

    class Meta:
        model = SchoolUser
        fields = ['user', 'school', 'role']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        school_data = validated_data.pop('school')
        school, _ = School.objects.get_or_create(
            name=school_data['name'], defaults={"address": school_data['address'], "contact_email": school_data['contact_email']})
        user_data['role'] = 'school'
        user_data.pop('is_staff', None)
        user_data.pop('is_superuser', None)
        user = User.objects.create_user(**user_data)
        school_user = SchoolUser.objects.create(user=user, school=school, **validated_data)
        return school_user

class CompanySerializer(serializers.ModelSerializer):
    def validate_logo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Le logo ne doit pas dépasser 5 Mo.")
        return value

    class Meta:
        model = Company
        fields = '__all__'

class CompanyUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    company = CompanySerializer()

    class Meta:
        model = CompanyUser
        fields = ['user', 'company', 'role']
    
    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        company_data = validated_data.pop('company')
        company, _ = Company.objects.get_or_create(name=company_data['name'], defaults={"secteur": company_data['secteur'], "description": company_data['description']})
        user_data['role'] = 'company'
        user_data['is_active'] = False  # L'utilisateur n'est pas actif par défaut
        user_data.pop('is_staff', None)
        user_data.pop('is_superuser', None)
        user = User.objects.create_user(**user_data)
        company_user = CompanyUser.objects.create(user=user, company=company, **validated_data)

        token = generate_activation_token(user)
        activation_link = f"https://totinda.com/activate?token={token}"

        # Utilisation de Celery
        send_activation_email.delay(user.email, user.username, activation_link)
        return company_user

class StudentProfileUpdateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    postnom = serializers.CharField(max_length=150, trim_whitespace=True)
    prenom = serializers.CharField(max_length=150, trim_whitespace=True)
    telephone = serializers.CharField(max_length=15, trim_whitespace=True)
    filiere = serializers.CharField(max_length=100, trim_whitespace=True)
    niveau = serializers.CharField(max_length=100, trim_whitespace=True)
    school = serializers.PrimaryKeyRelatedField(
        queryset=School.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )
    custom_school_name = serializers.CharField(
        max_length=200,
        trim_whitespace=True,
        required=False,
        allow_blank=True,
    )

    def validate(self, attrs):
        school = attrs.get('school')
        custom_school_name = attrs.get('custom_school_name', '').strip()
        if bool(school) == bool(custom_school_name):
            raise serializers.ValidationError({
                'school': "Sélectionnez un établissement ou saisissez son nom manuellement.",
            })
        return attrs


class GoogleAuthSerializer(serializers.Serializer):
    id_token = serializers.CharField(trim_whitespace=True)
    password = serializers.CharField(
        required=False,
        allow_blank=False,
        write_only=True,
        style={'input_type': 'password'},
    )


class StudentSerializer(serializers.ModelSerializer):
    #user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all()) si je souhaite juste recuperer l'id de l'utilisateur
    user = UserSerializer()
    profile_completion = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = ['id', 'user', 'school', 'custom_school_name', 'filiere', 'niveau', 'cv', 'profile_completion']

    def validate(self, attrs):
        school = attrs.get('school', getattr(self.instance, 'school', None))
        custom_school_name = attrs.get(
            'custom_school_name',
            getattr(self.instance, 'custom_school_name', ''),
        ).strip()
        if school and custom_school_name:
            raise serializers.ValidationError({
                'school': "Choisissez un établissement de la liste ou utilisez la saisie manuelle, pas les deux.",
            })
        if self.instance is None and not school and not custom_school_name:
            raise serializers.ValidationError({
                'school': "Sélectionnez un établissement ou saisissez son nom manuellement.",
            })
        return attrs

    def get_profile_completion(self, obj):
        return student_profile_completion(obj.user, obj)

    @transaction.atomic
    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'student'
        user_data['is_active'] = False  # L'utilisateur n'est pas actif par défaut
        user_data.pop('is_staff', None)
        user_data.pop('is_superuser', None)
        user = User.objects.create_user(**user_data)
        student = Student.objects.create(user=user, **validated_data)

        token = generate_activation_token(user)
        activation_link = f"https://totinda.com/activate?token={token}"

        # Utilisation de Celery
        send_activation_email.delay(user.email, user.username, activation_link)
        return student

class OffreStageSerializer(serializers.ModelSerializer):
    nombre_candidats = serializers.IntegerField(read_only=True)
    plan_entreprise = serializers.SerializerMethodField()
    days_remaining = serializers.SerializerMethodField()
    nom_entreprise = serializers.CharField(source='company.name', read_only=True)
    logo_entreprise = serializers.ImageField(source='company.logo', read_only=True)
    class Meta:
        model = OffreStage
        fields = "__all__"

    def get_plan_entreprise(self, obj):
        sub = getattr(obj.company, "companysubscription", None)
        if sub and sub.plan:
            return sub.plan.price
        return None

    def get_days_remaining(self, obj):
        return max((obj.end_date - timezone.localdate()).days, 0)
    

class CandidatureSerializer(serializers.ModelSerializer):
    offre_title = serializers.CharField(source='offre_stage.title', read_only=True)
    company_name = serializers.CharField(source='offre_stage.company.name', read_only=True)
    localisation = serializers.CharField(source='offre_stage.localisation', read_only=True)
    type_contrat = serializers.CharField(source='offre_stage.type_contrat', read_only=True)
    duration = serializers.CharField(source='offre_stage.duration', read_only=True)
    affectation_id = serializers.IntegerField(
        source='affectation.id', read_only=True, allow_null=True
    )

    def validate_letter_of_support(self, value):
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError(
                "La lettre de recommandation ne doit pas dépasser 5 Mo."
            )
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError(
                "La lettre de recommandation doit être un fichier PDF."
            )
        content_type = getattr(value, 'content_type', '')
        if content_type and content_type not in {'application/pdf', 'application/octet-stream'}:
            raise serializers.ValidationError(
                "La lettre de recommandation doit être un fichier PDF."
            )
        position = value.tell()
        signature = value.read(5)
        value.seek(position)
        if signature != b'%PDF-':
            raise serializers.ValidationError(
                "Le contenu de la lettre de recommandation n'est pas un PDF valide."
            )
        return value

    class Meta:
        model = Candidature
        fields = '__all__'
        read_only_fields = ['student', 'reviewed_at', 'reviewed_by']

class AffectationStageSerializer(serializers.ModelSerializer):
    offre_title = serializers.CharField(source='offre_stage.title', read_only=True)
    company_name = serializers.CharField(source='offre_stage.company.name', read_only=True)
    student_name = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    def get_student_name(self, obj):
        user = obj.student.user
        return ' '.join(filter(None, [user.prenom, user.postnom, user.username]))

    def get_progress(self, obj):
        reports = list(obj.weekly_reports.all())
        validated_weeks = sum(report.status == 'validated' for report in reports)
        submitted_weeks = sum(report.status == 'submitted' for report in reports)
        draft_weeks = sum(report.status == 'draft' for report in reports)

        if not obj.start_date or not obj.end_date:
            return {
                'total_weeks': 0,
                'elapsed_weeks': 0,
                'validated_weeks': validated_weeks,
                'pending_reports': submitted_weeks,
                'draft_reports': draft_weeks,
                'missing_weeks': 0,
                'percentage': 0,
            }

        first_monday = obj.start_date - timedelta(days=obj.start_date.weekday())
        last_monday = obj.end_date - timedelta(days=obj.end_date.weekday())
        total_weeks = ((last_monday - first_monday).days // 7) + 1
        today = timezone.localdate()
        elapsed_end = min(today, obj.end_date)
        elapsed_weeks = 0
        missing_weeks = 0
        if elapsed_end >= obj.start_date:
            elapsed_monday = elapsed_end - timedelta(days=elapsed_end.weekday())
            elapsed_weeks = ((elapsed_monday - first_monday).days // 7) + 1
            existing_weeks = {report.week_start for report in reports}
            missing_weeks = sum(
                first_monday + timedelta(weeks=index) not in existing_weeks
                for index in range(elapsed_weeks)
            )

        return {
            'total_weeks': total_weeks,
            'elapsed_weeks': elapsed_weeks,
            'validated_weeks': validated_weeks,
            'pending_reports': submitted_weeks,
            'draft_reports': draft_weeks,
            'missing_weeks': missing_weeks,
            'percentage': round((validated_weeks / total_weeks) * 100) if total_weeks else 0,
        }

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))
        if start_date and end_date and end_date < start_date:
            raise serializers.ValidationError({
                'end_date': "La date de fin doit être postérieure ou égale à la date de début."
            })
        return attrs

    def validate_convention_pdf(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("La convention ne doit pas dépasser 10 Mo.")
        if not value.name.lower().endswith('.pdf'):
            raise serializers.ValidationError("La convention doit être un fichier PDF.")
        return value

    class Meta:
        model = AffectationStage
        fields = '__all__'
        read_only_fields = ['candidature', 'student', 'offre_stage', 'assigned_on']


class StageWeeklyReportSerializer(serializers.ModelSerializer):
    week_end = serializers.SerializerMethodField()
    student_name = serializers.SerializerMethodField()
    offre_title = serializers.CharField(source='affectation.offre_stage.title', read_only=True)
    validated_by_name = serializers.SerializerMethodField()

    def get_week_end(self, obj):
        return obj.week_start + timedelta(days=6)

    def get_student_name(self, obj):
        user = obj.affectation.student.user
        return ' '.join(filter(None, [user.prenom, user.postnom, user.username]))

    def get_validated_by_name(self, obj):
        if not obj.validated_by:
            return None
        user = obj.validated_by
        return ' '.join(filter(None, [user.prenom, user.postnom, user.username]))

    def validate_week_start(self, value):
        if value.weekday() != 0:
            raise serializers.ValidationError("La semaine doit commencer un lundi.")
        return value

    def validate(self, attrs):
        affectation = attrs.get('affectation', getattr(self.instance, 'affectation', None))
        week_start = attrs.get('week_start', getattr(self.instance, 'week_start', None))
        if affectation and week_start:
            week_end = week_start + timedelta(days=6)
            if affectation.start_date and week_end < affectation.start_date:
                raise serializers.ValidationError({
                    'week_start': "Cette semaine précède le début du stage."
                })
            if affectation.end_date and week_start > affectation.end_date:
                raise serializers.ValidationError({
                    'week_start': "Cette semaine suit la fin du stage."
                })
        return attrs

    class Meta:
        model = StageWeeklyReport
        fields = '__all__'
        read_only_fields = [
            'submitted_at', 'validated_at', 'validated_by',
            'created_at', 'updated_at',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    is_read = serializers.BooleanField(read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'notification_type', 'title', 'message', 'data',
            'is_read', 'read_at', 'created_at',
        ]
        read_only_fields = fields


class PushDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = ['id', 'expo_push_token', 'platform', 'is_active', 'updated_at']
        read_only_fields = ['id', 'is_active', 'updated_at']

    def validate_expo_push_token(self, value):
        value = value.strip()
        if not (
            value.startswith('ExponentPushToken[')
            or value.startswith('ExpoPushToken[')
        ):
            raise serializers.ValidationError("Jeton Expo Push invalide.")
        return value

    def create(self, validated_data):
        device, _ = PushDevice.objects.update_or_create(
            expo_push_token=validated_data['expo_push_token'],
            defaults={
                'user': self.context['request'].user,
                'platform': validated_data['platform'],
                'is_active': True,
                'last_error': '',
            },
        )
        return device

class EvaluationSerializer(serializers.ModelSerializer):
    score = serializers.IntegerField(min_value=1, max_value=10)

    def validate_comments(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Un commentaire final est requis.")
        return value

    def validate(self, attrs):
        candidature = attrs.get('candidature', getattr(self.instance, 'candidature', None))
        if not candidature:
            raise serializers.ValidationError({'candidature': "Candidature requise."})
        if candidature.status != 'accepted':
            raise serializers.ValidationError({
                'candidature': "Seule une candidature acceptée peut être évaluée."
            })
        try:
            affectation = candidature.affectation
        except AffectationStage.DoesNotExist:
            raise serializers.ValidationError({
                'candidature': "Aucun parcours de stage n'est associé à cette candidature."
            })
        if affectation.status != 'completed':
            raise serializers.ValidationError({
                'candidature': "Le stage doit être marqué comme terminé avant son évaluation."
            })
        return attrs

    class Meta:
        model = Evaluation
        fields = '__all__'
class FormationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Formation
        fields = '__all__'


class CompetenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Competence
        fields = '__all__'

    def create(self, validated_data):
        student = validated_data.pop('student')
        competence = Competence.objects.create(student=student, **validated_data)
        return competence
    
class CompanySubscriptionSerializer(serializers.ModelSerializer):
    is_active = serializers.SerializerMethodField()
    remaining_offres = serializers.SerializerMethodField()

    class Meta:
        model = CompanySubscription
        fields = ['id', 'start_date', 'end_date', 'is_active', 'remaining_offres', 'plan','nbre_offres']
        read_only_fields = ['start_date', 'end_date', 'is_active', 'remaining_offres','nbre_offres']

    def get_is_active(self, obj):
        return obj.is_active()

    def get_remaining_offres(self, obj):
        return obj.remaining_offres() 
       
class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ['id', 'company', 'amount', 'transaction_id', 'status', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        payment = Payment.objects.create(**validated_data)
        return payment
class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'name', 'price', 'max_offres', 'duration_days']
        read_only_fields = ['*']

class PartnerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Partner
        fields = ['id', 'name', 'image']
        read_only_fields = fields


class ConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = Config
        fields = [
            'id', 'site_name', 'logo', 'homepage_banner',
            'contact_email', 'phone_number',
            'facebook_link', 'twitter_link', 'linkedin_link', 'updated_at'
        ]
