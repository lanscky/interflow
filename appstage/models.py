# models.py

from django.db import models
from django.contrib.auth.models import AbstractUser

# 1. Utilisateur générique avec rôle
class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Étudiant'),
        ('school', 'École'),
        ('company', 'Entreprise'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)

# 2. Profil étudiant
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True)
    filiere = models.CharField(max_length=100) # ex: Informatique, Mathématiques, etc.
    niveau = models.CharField(max_length=50)  # ex: Licence 3, Master 1, etc.
    cv = models.FileField(upload_to='cvs/', null=True, blank=True)

# 3. École
class School(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField()
    contact_email = models.EmailField()

class SchoolUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # rôle "school"
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=50,
        choices=[('admin', 'Admin'), ('editor', 'Éditeur'), ('viewer', 'Lecteur')],
        default='editor'
    )
    is_active = models.BooleanField(default=True)
# 4. Entreprise
class Company(models.Model):
    name = models.CharField(max_length=150)
    secteur = models.CharField(max_length=100)
    description = models.TextField()

class CompanyUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # rôle "company"
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=50,
        choices=[('admin', 'Admin'), ('hr', 'RH'), ('viewer', 'Consultation')],
        default='hr'
    )
    is_active = models.BooleanField(default=True)

# 5. Offre de stage
class OffreStage(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    description = models.TextField()
    localisation = models.CharField(max_length=150)
    niveau_requis = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    published_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

# 6. Candidature
class Candidature(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    offer = models.ForeignKey(OffreStage, on_delete=models.CASCADE)
    motivation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    letter_of_support = models.FileField(upload_to='letters_of_support/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Rejetée'),
    ], default='pending')

# 7. Stage validé
class AffectationStage(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    offer = models.ForeignKey(OffreStage, on_delete=models.CASCADE)
    assigned_on = models.DateTimeField(auto_now_add=True)
    convention_pdf = models.FileField(upload_to='conventions/', null=True, blank=True)
    supervisor_name = models.CharField(max_length=150, null=True, blank=True)
    supervisor_email = models.EmailField(null=True, blank=True)

# 8. Évaluation finale
class Evaluation(models.Model):
    internship = models.OneToOneField(AffectationStage, on_delete=models.CASCADE)
    score = models.IntegerField()  # de 1 à 10
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
