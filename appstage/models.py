# models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import secrets


def generate_certificate_reference():
    return f"TOT-{secrets.token_hex(8).upper()}"

# 1. Utilisateur générique avec rôle
class User(AbstractUser):
    ROLE_CHOICES = (
        ('student', 'Étudiant'),
        ('school', 'École'),
        ('company', 'Entreprise'),
    )
    username = models.CharField(max_length=150, unique=False, blank=False, null=False)
    email = models.EmailField(unique=True)
    USERNAME_FIELD = 'email'

    postnom = models.CharField(max_length=150, blank=True, null=True)  # Optionnel
    prenom = models.CharField(max_length=150, blank=True, null=True)  # Optionnel
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    telephone = models.CharField(max_length=15, null=True, blank=True)  

    REQUIRED_FIELDS = ['username']


class SocialIdentity(models.Model):
    PROVIDER_GOOGLE = 'google'
    PROVIDER_CHOICES = ((PROVIDER_GOOGLE, 'Google'),)

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_identities')
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    provider_user_id = models.CharField(max_length=255)
    email_at_link = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'provider_user_id'],
                name='unique_social_provider_identity',
            ),
            models.UniqueConstraint(
                fields=['user', 'provider'],
                name='unique_social_provider_per_user',
            ),
        ]

    def __str__(self):
        return f"{self.provider} - {self.user.email}"


# 2. Profil étudiant
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    school = models.ForeignKey('School', on_delete=models.SET_NULL, null=True)
    custom_school_name = models.CharField(max_length=200, blank=True, default='')
    filiere = models.CharField(max_length=100, blank=True, default='') # ex: Informatique, Mathématiques, etc.
    niveau = models.CharField(max_length=100, blank=True, default='')  # ex: Licence 3, Master 1, etc.
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
    name = models.CharField(max_length=255)
    sigle = models.CharField(max_length=80, blank=True, default='')
    logo = models.ImageField(upload_to='schools/logos/', null=True, blank=True)
    category = models.CharField(max_length=100, blank=True, default='')
    ownership = models.CharField(max_length=20, blank=True, default='')
    territory = models.CharField(max_length=100, blank=True, default='')
    province = models.CharField(max_length=100, blank=True, default='')
    approval_status = models.CharField(max_length=100, blank=True, default='')
    registry_id = models.PositiveIntegerField(null=True, blank=True, unique=True)
    source_url = models.URLField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    address = models.TextField(blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')

    class Meta:
        ordering = ('name', 'province', 'territory')
        indexes = [
            models.Index(fields=['name'], name='school_name_idx'),
            models.Index(fields=['sigle'], name='school_sigle_idx'),
            models.Index(fields=['province'], name='school_province_idx'),
        ]
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
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)

class CompanyUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='company_user')  # rôle "company"
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
    company_message = models.TextField(blank=True, default='')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_candidatures',
    )
    def __str__(self):
        return f"{self.student.user.username} - {self.offre_stage.title} ({self.status})"


# 7. Stage validé
class AffectationStage(models.Model):
    STATUS_CHOICES = [
        ('upcoming', 'À venir'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('cancelled', 'Interrompu'),
    ]

    candidature = models.OneToOneField(
        Candidature,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='affectation',
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    offre_stage = models.ForeignKey(OffreStage, on_delete=models.CASCADE)
    assigned_on = models.DateTimeField(auto_now_add=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')
    objectives = models.TextField(blank=True, default='')
    convention_pdf = models.FileField(upload_to='conventions/', null=True, blank=True)
    supervisor_name = models.CharField(max_length=150, null=True, blank=True)
    supervisor_email = models.EmailField(null=True, blank=True)
    def __str__(self):
        return f"{self.student.user.username} - {self.offre_stage.title} (Affecté le {self.assigned_on})"


class StageWeeklyReport(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('submitted', 'Soumis'),
        ('validated', 'Validé'),
    ]

    affectation = models.ForeignKey(
        AffectationStage,
        on_delete=models.CASCADE,
        related_name='weekly_reports',
    )
    week_start = models.DateField()
    activities = models.TextField()
    learnings = models.TextField(blank=True, default='')
    difficulties = models.TextField(blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    company_comment = models.TextField(blank=True, default='')
    submitted_at = models.DateTimeField(null=True, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    validated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='validated_stage_reports',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-week_start', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['affectation', 'week_start'],
                name='unique_stage_report_per_week',
            ),
        ]

    def __str__(self):
        return f"Semaine du {self.week_start} - {self.affectation.student.user.username}"


class StageCertificate(models.Model):
    affectation = models.ForeignKey(
        AffectationStage,
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    reference = models.CharField(
        max_length=24,
        unique=True,
        default=generate_certificate_reference,
        editable=False,
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    version = models.PositiveIntegerField(default=1)
    data_hash = models.CharField(max_length=64, blank=True, default='')
    verification_count = models.PositiveIntegerField(default=0)
    last_verified_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    revoked_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='revoked_stage_certificates',
    )
    revocation_reason = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-issued_at']
        constraints = [
            models.UniqueConstraint(
                fields=['affectation', 'version'],
                name='unique_stage_certificate_version',
            ),
        ]

    @property
    def is_valid(self):
        return self.revoked_at is None

    def __str__(self):
        return self.reference


class Notification(models.Model):
    TYPE_CHOICES = [
        ('application_decision', 'Décision de candidature'),
        ('report_submitted', 'Rapport soumis'),
        ('report_validated', 'Rapport validé'),
        ('evaluation_published', 'Évaluation publiée'),
        ('weekly_reminder', 'Rappel hebdomadaire'),
    ]

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=40, choices=TYPE_CHOICES)
    title = models.CharField(max_length=180)
    message = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    unique_key = models.CharField(max_length=180, unique=True, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_read(self):
        return self.read_at is not None

    def __str__(self):
        return f"{self.recipient.email} - {self.title}"


class PushDevice(models.Model):
    PLATFORM_CHOICES = [
        ('android', 'Android'),
        ('ios', 'iOS'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    expo_push_token = models.CharField(max_length=255, unique=True)
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    is_active = models.BooleanField(default=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.user.email} - {self.platform}"



# 8. Évaluation finale
class Evaluation(models.Model):
    candidature = models.OneToOneField(Candidature, null=True, blank=True, on_delete=models.CASCADE)
    score = models.IntegerField()  # de 1 à 10
    comments = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Évaluation de {self.candidature.student.user.username} pour {self.candidature.offre_stage.title} (Score: {self.score})"

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    max_offres = models.IntegerField(null=True, blank=True)  # null = illimité
    duration_days = models.IntegerField()  # ex: 30 pour un mois

    def __str__(self):
        return f"{self.name} ({'Illimité' if self.max_offres is None else self.max_offres} offres)"


class CompanySubscription(models.Model):
    company = models.OneToOneField(Company, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    nbre_offres = models.IntegerField(default=0, null=True, blank=True)  # Nombre d'offres utilisées

    # Nouveau champ pour plan futur
    next_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True, blank=True, related_name='future_subscriptions')
    change_effective_date = models.DateTimeField(null=True, blank=True)

    def is_active(self):
        return self.end_date >= timezone.now()

    def remaining_offres(self):
        if self.nbre_offres is None:
            return None  # illimité
        used = OffreStage.objects.filter(company=self.company, published_at__gte=self.start_date).count()
        return self.nbre_offres - used
    
    def __str__(self):
        company_name = self.company.name if self.company else "Aucune entreprise"
        plan_name = self.plan.name if self.plan else "Aucun plan"
        return f"{company_name} - {plan_name}"


class Payment(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=[('pending', 'En attente'), ('success', 'Succès'), ('failed', 'Échoué')])
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return f"Paiement de {self.company.name} - {self.amount}€ ({self.status})"
    

class Partner(models.Model):
    name = models.CharField("Nom", max_length=150)
    image = models.ImageField("Logo", upload_to='partners/')
    position = models.PositiveIntegerField("Ordre d’affichage", default=0)
    is_active = models.BooleanField("Afficher sur le site", default=True)

    class Meta:
        ordering = ('position', 'id')
        verbose_name = "Partenaire de l’écosystème"
        verbose_name_plural = "Partenaires de l’écosystème"

    def __str__(self):
        return self.name


class Config(models.Model):
    site_name = models.CharField(max_length=255, default="Totinda")
    logo = models.ImageField(upload_to='config/', null=True, blank=True)
    homepage_banner = models.ImageField(upload_to='config/', null=True, blank=True)
    contact_email = models.EmailField(default="contact@totinda.com")
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    facebook_link = models.URLField(blank=True, null=True)
    twitter_link = models.URLField(blank=True, null=True)
    linkedin_link = models.URLField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration"
        verbose_name_plural = "Configurations"

    def __str__(self):
        return self.site_name
