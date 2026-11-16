PROFILE_FIELDS = (
    ('username', lambda user, student: user.username),
    ('postnom', lambda user, student: user.postnom),
    ('prenom', lambda user, student: user.prenom),
    ('telephone', lambda user, student: user.telephone),
    ('filiere', lambda user, student: student.filiere if student else None),
    ('niveau', lambda user, student: student.niveau if student else None),
    ('school', lambda user, student: (
        student.school_id or student.custom_school_name if student else None
    )),
    ('cv', lambda user, student: student.cv if student else None),
    ('profile_picture', lambda user, student: user.profile_picture),
)

APPLICATION_REQUIRED_FIELDS = (
    'username',
    'postnom',
    'prenom',
    'telephone',
    'filiere',
    'niveau',
    'school',
)


def _has_value(value):
    if hasattr(value, 'name'):
        value = value.name
    return bool(str(value).strip()) if value is not None else False


def student_profile_completion(user, student=None):
    if student is None:
        try:
            student = user.student
        except Student.DoesNotExist:
            student = None

    completed_fields = [
        field
        for field, getter in PROFILE_FIELDS
        if _has_value(getter(user, student))
    ]
    all_fields = [field for field, _getter in PROFILE_FIELDS]
    missing_fields = [
        field for field in APPLICATION_REQUIRED_FIELDS if field not in completed_fields
    ]

    return {
        'percentage': round(len(completed_fields) / len(all_fields) * 100),
        'can_apply': bool(student) and not missing_fields,
        'missing_fields': missing_fields,
        'completed_fields': completed_fields,
        'total_fields': len(all_fields),
    }
from .models import Student
