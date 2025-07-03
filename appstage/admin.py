from django.contrib import admin
from django.contrib.auth.admin import UserAdmin 
from django.contrib.auth.forms import UserCreationForm
from .models import User, Student, School, SchoolUser, Company, CompanyUser, OffreStage, Candidature, AffectationStage, Evaluation, Competence, Formation
# Register your models here.

class CustomUserAdmin(UserAdmin):
    add_form = UserCreationForm
    list_display = ('id', 'username', 'email', 'first_name', 'last_name', 'role')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    list_filter = ('role',)
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'role','telephone'),  # Ajoutez le champ "role" ici
        }),
    )
admin.site.register(User, CustomUserAdmin)
admin.site.register(Student, admin.ModelAdmin)  # Assuming StudentAdmin is not defined, using default ModelAdmin
admin.site.register(School, admin.ModelAdmin)  # Assuming SchoolAdmin is not defined, using default ModelAdmin
admin.site.register(SchoolUser, admin.ModelAdmin)  # Assuming SchoolUserAdmin is not defined, using default ModelAdmin
admin.site.register(Company, admin.ModelAdmin)  # Assuming CompanyAdmin is not defined, using default ModelAdmin
admin.site.register(CompanyUser, admin.ModelAdmin)  # Assuming CompanyUserAdmin is not defined, using default ModelAdmin
admin.site.register(OffreStage, admin.ModelAdmin)  # Assuming OffreStageAdmin is not defined, using default ModelAdmin
admin.site.register(Candidature, admin.ModelAdmin)  # Assuming CandidatureAdmin is not defined, using default ModelAdmin
admin.site.register(AffectationStage, admin.ModelAdmin)  # Assuming AffectationStageAdmin is not defined, using default ModelAdmin
admin.site.register(Evaluation, admin.ModelAdmin)  # Assuming EvaluationAdmin is not defined, using default ModelAdmin
admin.site.register(Competence, admin.ModelAdmin)  # Assuming CompetenceAdmin is not defined, using default ModelAdmin
admin.site.register(Formation, admin.ModelAdmin)  # Assuming FormationAdmin is not defined, using default ModelAdmin
