from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from django.contrib.auth.forms import UserCreationForm
from .models import User, Student, School, SchoolUser, Company,CompanyUser, OffreStage, Candidature, AffectationStage, Evaluation, Competence, Formation, CompanySubscription, SubscriptionPlan, Payment
# Register your models here.

class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'role')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('role',)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role','telephone','profile_picture'),  # Ajoutez le champ "role" ici
        }),
    )
    fieldsets = UserAdmin.fieldsets + (
        ('Informations personnalisées', {
            'fields': ('role', 'telephone','profile_picture'),
        }),
    )
class OffreStageAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'company', 'start_date', 'end_date')
    search_fields = ('title', 'company__name')
    list_filter = ('company', 'start_date', 'end_date') 
    ordering = ('-start_date',)

class CandidatureAdmin(admin.ModelAdmin):
    list_display = ('id', 'student', 'offre_stage', 'status', 'created_at')
    search_fields = ('student__user__username', 'offre_stage__title')
    list_filter = ('status', 'created_at')
    ordering = ('-created_at',)
    
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
admin.site.register(School, admin.ModelAdmin)  # Assuming SchoolAdmin is not defined, using default ModelAdmin
admin.site.register(SchoolUser, admin.ModelAdmin)  # Assuming SchoolUserAdmin is not defined, using default ModelAdmin
admin.site.register(Company, CompanyAdmin)  # Assuming CompanyAdmin is not defined, using default ModelAdmin
admin.site.register(CompanyUser, admin.ModelAdmin)  # Assuming CompanyUserAdmin is not defined, using default ModelAdmin
admin.site.register(OffreStage, OffreStageAdmin)  # Using the defined OffreStageAdmin
admin.site.register(Candidature, CandidatureAdmin)  # Using the defined CandidatureAdmin
admin.site.register(AffectationStage, admin.ModelAdmin)  # Assuming AffectationStageAdmin is not defined, using default ModelAdmin
admin.site.register(Evaluation, admin.ModelAdmin)  # Assuming EvaluationAdmin is not defined, using default ModelAdmin
admin.site.register(Competence, admin.ModelAdmin)  # Assuming CompetenceAdmin is not defined, using default ModelAdmin
admin.site.register(Formation, admin.ModelAdmin)  # Assuming FormationAdmin is not defined, using default ModelAdmin
admin.site.register(CompanySubscription, CompanySubscriptionAdmin)  # Using the defined CompanySubscriptionAdmin
admin.site.register(SubscriptionPlan, SubscriptionPlanAdmin)  # Using the defined SubscriptionPlanAdmin
admin.site.register(Payment, PaymentAdmin)  # Using the defined PaymentAdmin
