# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Student, School, SchoolUser, Company, CompanyUser,
    OffreStage, Candidature, AffectationStage, Evaluation, Formation, Competence 
)
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()



class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        user = self.user

        # ✅ Récupérer request depuis le contexte
        request = self.context.get('request')
        # Construire l'URL absolue de la photo de profil
        profile_picture_url = (
            request.build_absolute_uri(user.profile_picture.url)
            if user.profile_picture and request
            else None
        )
        # Infos de base du user
        user_data = {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "profile_picture": user.profile_picture.url if user.profile_picture else None,
            "profile_picture_url": profile_picture_url,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "role_user": user.role
        }
        

        # Ajouter les infos spécifiques selon le rôle
        if user.role == 'student':
            try:
                student = Student.objects.select_related('school').get(user=user)
                user_data["student"] = {
                    "id_student": student.id,
                    "filiere": student.filiere,
                    "niveau": student.niveau,
                    "cv": student.cv.url if student.cv else None,
                    "school": {
                        "id": student.school.id,
                        "name": student.school.name,
                        "email": student.school.contact_email,
                        "address": student.school.address
                    } if student.school else None
                }
            except Student.DoesNotExist:
                user_data["student"] = None

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
                        "address": school.address
                    }
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
                        "description": company.description
                    }
                }
            except CompanyUser.DoesNotExist:
                user_data["company_user"] = None

        # Injecter les données dans la réponse JWT
        data["user"] = user_data

        return data
# class UserSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'password', 'role']
#         extra_kwargs = {'password': {'write_only': True}}

#     def create(self, validated_data):
#         user = User.objects.create_user(**validated_data)
#         return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'is_superuser', 'is_staff']
        extra_kwargs = {
            'password': {'write_only': True},
            'is_superuser': {'write_only': True},
            'is_staff': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password')
        is_superuser = validated_data.pop('is_superuser', False)
        is_staff = validated_data.pop('is_staff', False)

        user = User(**validated_data)
        user.set_password(password)
        user.is_superuser = is_superuser
        user.is_staff = is_staff
        user.save()
        return user


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
        user = User.objects.create_user(**user_data)
        school_user = SchoolUser.objects.create(user=user, school=school, **validated_data)
        return school_user

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

class CompanyUserSerializer(serializers.ModelSerializer):
    user = UserSerializer()
    company = CompanySerializer()

    class Meta:
        model = CompanyUser
        fields = ['user', 'company', 'role']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        company_data = validated_data.pop('company')
        company, _ = Company.objects.get_or_create(name=company_data['name'], defaults={"secteur": company_data['secteur'], "description": company_data['description']})
        user_data['role'] = 'company'
        user = User.objects.create_user(**user_data)
        company_user = CompanyUser.objects.create(user=user, company=company, **validated_data)
        return company_user

class StudentSerializer(serializers.ModelSerializer):
    user = UserSerializer()

    class Meta:
        model = Student
        fields = ['user', 'school', 'filiere', 'niveau', 'cv']

    def create(self, validated_data):
        user_data = validated_data.pop('user')
        user_data['role'] = 'student'
        user = User.objects.create_user(**user_data)
        student = Student.objects.create(user=user, **validated_data)
        return student

class OffreStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OffreStage
        fields = '__all__'

class CandidatureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidature
        fields = '__all__'

class AffectationStageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AffectationStage
        fields = '__all__'

class EvaluationSerializer(serializers.ModelSerializer):
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