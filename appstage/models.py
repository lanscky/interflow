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
    postnom = models.CharField(max_length=150, blank=True, null=True)  # Optionnel
    prenom = models.CharField(max_length=150, blank=True, null=True)  # Optionnel
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    telephone = models.CharField(max_length=15, null=True, blank=True)  


# 2. Profil étudiant
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True)
    filiere = models.CharField(max_length=100) # ex: Informatique, Mathématiques, etc.
    niveau = models.CharField(max_length=50)  # ex: Licence 3, Master 1, etc.
    cv = models.FileField(upload_to='cvs/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.filiere} ({self.niveau})"


class Competence(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)  # ex: Python, Java, Gestion de projet, etc.
    level = models.CharField(max_length=50)  # ex: Débutant, Intermédiaire, Avancé
    description = models.TextField(null=True, blank=True)  # Optionnel
    created_at = models.DateTimeField(auto_now_add=True)  # Date de création de la compétence
    updated_at = models.DateTimeField(auto_now=True)  # Date de dernière mise à jour de la compétence
    is_active = models.BooleanField(default=True)  # Indique si la compétence est active ou non

    def __str__(self):
        return f"{self.name} ({self.level}) - {self.student.user.username}"
    
class Formation(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)  # ex: "Master en Informatique"
    institution = models.CharField(max_length=100)  # ex: "Université de Paris"
    start_date = models.DateField()
    end_date = models.DateField()
    description = models.TextField(null=True, blank=True)  # Optionnel
    def __str__(self):
        return f"{self.title} - {self.institution} ({self.start_date} - {self.end_date})"

# 3. École
class School(models.Model):
    name = models.CharField(max_length=150)
    address = models.TextField()
    contact_email = models.EmailField()
    def __str__(self):
        return self.name

class SchoolUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)  # rôle "school"
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=50,
        choices=[('admin', 'Admin'), ('editor', 'Éditeur'), ('viewer', 'Lecteur')],
        default='editor'
    )
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.school.name} ({self.role})"


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
    def __str__(self):
        return f"{self.user.username} - {self.company.name} ({self.role})"


# 5. Offre de stage
class OffreStage(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    title = models.CharField(max_length=150)
    type_contrat = models.CharField(max_length=50, choices=[
        ('stage', 'Stage'),
        ('alternance', 'Alternance'),
        ('freelance', 'Freelance'),
        ('cdi', 'CDI'),
        ('cdd', 'CDD'),
    ])
    remuneration = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  # Montant en euros
    duration = models.CharField(max_length=50)  # ex: "3 mois", "6 mois", "1 an"
    description = models.TextField()
    localisation = models.CharField(max_length=150)
    niveau_requis = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    published_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    def __str__(self):
        return f"{self.title} - {self.company.name} ({self.start_date} - {self.end_date})"


# 6. Candidature
class Candidature(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    offre_stage = models.ForeignKey(OffreStage, on_delete=models.CASCADE)
    motivation = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    letter_of_support = models.FileField(upload_to='letters_of_support/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'En attente'),
        ('accepted', 'Acceptée'),
        ('rejected', 'Rejetée'),
    ], default='pending')
    def __str__(self):
        return f"{self.student.user.username} - {self.offre_stage.title} ({self.status})"


# 7. Stage validé
class AffectationStage(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    offre_stage = models.ForeignKey(OffreStage, on_delete=models.CASCADE)
    assigned_on = models.DateTimeField(auto_now_add=True)
    convention_pdf = models.FileField(upload_to='conventions/', null=True, blank=True)
    supervisor_name = models.CharField(max_length=150, null=True, blank=True)
    supervisor_email = models.EmailField(null=True, blank=True)
    def __str__(self):
        return f"{self.student.user.username} - {self.offre_stage.title} (Affecté le {self.assigned_on})"



# 8. Évaluation finale
class Evaluation(models.Model):
    candidature = models.OneToOneField(Candidature, null=True, blank=True, on_delete=models.CASCADE)
    score = models.IntegerField()  # de 1 à 10
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Évaluation de {self.candidature.student.user.username} pour {self.candidature.offre_stage.title} (Score: {self.score})"

