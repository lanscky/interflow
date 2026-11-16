from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from django.contrib.auth.forms import UserCreationForm
from django import forms
from .models import Partner
from .models import User, Student, SocialIdentity, School, SchoolUser, Company,CompanyUser, OffreStage, Candidature, AffectationStage, StageWeeklyReport, StageCertificate, Notification, PushDevice, Evaluation, Competence, Formation, CompanySubscription, SubscriptionPlan, Payment, Config
# Register your models here.


class PartnerAdminForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = '__all__'

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Le logo ne doit pas dépasser 5 Mo.")
        return image


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    form = PartnerAdminForm
    list_display = ('name', 'position', 'is_active')
    list_editable = ('position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    ordering = ('position', 'id')


class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    list_display = ('id', 'username', 'is_active', 'email', 'postnom', 'prenom', 'role')
    search_fields = ('username', 'email', 'postnom', 'prenom')
    list_filter = ('role',)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role','telephone','profile_picture'),  # Ajoutez le champ "role" ici
        }),
    )
    fieldsets = UserAdmin.fieldsets + (
        ('Informations personnalisées', {
            'fields': ('postnom', 'prenom','role', 'telephone','profile_picture'),
        }),
    )
class OffreStageAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'company', 'start_date', 'end_date')
    search_fields = ('title', 'company__name')
    list_filter = ('company', 'start_date', 'end_date') 
    ordering = ('-start_date',)

class CandidatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'offre_stage', 'status', 'reviewed_at', 'created_at')
    search_fields = ('student__user__username', 'offre_stage__title')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)

class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'sigle', 'category', 'ownership', 'territory', 'province', 'approval_status', 'is_active')
    search_fields = ('name', 'sigle', 'territory', 'province', 'registry_id')
    list_filter = ('category', 'ownership', 'province', 'approval_status', 'is_active')
    ordering = ('name', 'province', 'territory')

class AffectationStageAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'offre_stage', 'status', 'start_date', 'end_date', 'assigned_on')
    search_fields = ('student__user__username', 'student__user__email', 'offre_stage__title')
    list_filter = ('status', 'start_date', 'end_date')
    ordering = ('-assigned_on',)

class StageWeeklyReportAdmin(admin.ModelAdmin):
    list_display = ('id', 'affectation', 'week_start', 'status', 'submitted_at', 'validated_at')
    search_fields = ('affectation__student__user__email', 'affectation__offre_stage__title')
    list_filter = ('status', 'week_start')
    ordering = ('-week_start',)
    
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'secteur')
    search_fields = ('name', 'secteur')
    ordering = ('name',)   
class CompanySubscriptionAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'plan', 'start_date', 'end_date','nbre_offres', 'next_plan', 'change_effective_date')
    search_fields = ('company__name', 'plan__name')
    ordering = ('-start_date',) 
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'duration_days', 'max_offres','price')
    search_fields = ('name',)
    ordering = ('-id',)  
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('id', 'company', 'amount', 'transaction_id', 'status', 'created_at')
    search_fields = ('company__name', 'transaction_id')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',) 
admin.site.register(User, CustomUserAdmin)
admin.site.register(Student, admin.ModelAdmin)  # Assuming StudentAdmin is not defined, using default ModelAdmin
admin.site.register(SocialIdentity, admin.ModelAdmin)
admin.site.register(School, SchoolAdmin)
admin.site.register(SchoolUser, admin.ModelAdmin)  # Assuming SchoolUserAdmin is not defined, using default ModelAdmin
admin.site.register(Company, CompanyAdmin)  # Assuming CompanyAdmin is not defined, using default ModelAdmin
admin.site.register(CompanyUser, admin.ModelAdmin)  # Assuming CompanyUserAdmin is not defined, using default ModelAdmin
admin.site.register(OffreStage, OffreStageAdmin)  # Using the defined OffreStageAdmin
admin.site.register(Candidature, CandidatureAdmin)  # Using the defined CandidatureAdmin
admin.site.register(AffectationStage, AffectationStageAdmin)
admin.site.register(StageWeeklyReport, StageWeeklyReportAdmin)
admin.site.register(StageCertificate, admin.ModelAdmin)
admin.site.register(Notification, admin.ModelAdmin)
admin.site.register(PushDevice, admin.ModelAdmin)
admin.site.register(Evaluation, admin.ModelAdmin)  # Assuming EvaluationAdmin is not defined, using default ModelAdmin
admin.site.register(Competence, admin.ModelAdmin)  # Assuming CompetenceAdmin is not defined, using default ModelAdmin
admin.site.register(Formation, admin.ModelAdmin)  # Assuming FormationAdmin is not defined, using default ModelAdmin
admin.site.register(CompanySubscription, CompanySubscriptionAdmin)  # Using the defined CompanySubscriptionAdmin
admin.site.register(SubscriptionPlan, SubscriptionPlanAdmin)  # Using the defined SubscriptionPlanAdmin
admin.site.register(Payment, PaymentAdmin)  # Using the defined PaymentAdmin
admin.site.register(Config, admin.ModelAdmin)  # Assuming ConfigAdmin is not defined, using default ModelAdmin
