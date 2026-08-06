from rest_framework import permissions


class IsStaffPermission(permissions.DjangoModelPermissions):

    # def has_permission(self, request, view):
    #     if not request.user.is_staff:
    #         return False
    #     return super().has_permission(request, view)

    perms_map = {
        'GET': ['%(app_label)s.view_%(model_name)s'],
        'OPTIONS': [],
        'HEAD': [],
        'POST': ['%(app_label)s.add_%(model_name)s'],
        'PUT': ['%(app_label)s.change_%(model_name)s'],
        'PATCH': ['%(app_label)s.change_%(model_name)s'],
        'DELETE': ['%(app_label)s.delete_%(model_name)s'],
    }


def company_for_user(user):
    """Retourne l'entreprise active de l'utilisateur sans lever d'exception."""
    if not getattr(user, "is_authenticated", False):
        return None
    relation = user.company_user.filter(is_active=True).select_related("company").first()
    return relation.company if relation else None


class IsRelatedObjectOwnerOrStaff(permissions.BasePermission):
    """Autorise les administrateurs et le propriétaire fonctionnel d'un objet."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        if user.is_staff or user.is_superuser:
            return True

        owner = getattr(obj, "user", None)
        if owner == user:
            return True

        student = obj if obj.__class__.__name__ == "Student" else getattr(obj, "student", None)
        if student is not None and getattr(student, "user_id", None) == user.id:
            return True
        candidature = getattr(obj, "candidature", None)
        if candidature is not None and candidature.student.user_id == user.id:
            return True

        user_company = company_for_user(user)
        if student is not None and user_company is not None:
            if student.candidature_set.filter(offre_stage__company=user_company).exists():
                return True

        company = obj if obj.__class__.__name__ == "Company" else getattr(obj, "company", None)
        if company is None and hasattr(obj, "offre_stage"):
            company = obj.offre_stage.company
        if company is None and hasattr(obj, "candidature") and obj.candidature:
            company = obj.candidature.offre_stage.company

        return company is not None and user_company == company
