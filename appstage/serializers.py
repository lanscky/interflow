# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    Student, School, SchoolUser, Company, CompanyUser,
    OffreStage, Candidature, AffectationStage, Evaluation
)

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role']
        extra_kwargs = {'password': {'write_only': True}}

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
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
