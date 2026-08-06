from datetime import date, timedelta
from unittest.mock import patch

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    Candidature,
    Company,
    CompanySubscription,
    CompanyUser,
    Evaluation,
    OffreStage,
    Payment,
    Student,
    SubscriptionPlan,
    User,
)


class ApiSecurityTests(APITestCase):
    def create_user(self, email, role, **extra):
        return User.objects.create_user(
            username=email.split("@")[0],
            email=email,
            password="StrongPassword123!",
            role=role,
            is_active=True,
            **extra,
        )

    def create_offer(self, company, title="Stage Django"):
        return OffreStage.objects.create(
            company=company,
            title=title,
            type_contrat="stage",
            duration="3 mois",
            description="Description",
            localisation="Kinshasa",
            niveau_requis="L3",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=90),
        )

    @patch("appstage.serializers.send_activation_email.delay")
    def test_student_registration_cannot_set_admin_flags(self, _send_email):
        payload = {
            "user": {
                "username": "attacker",
                "email": "attacker@example.com",
                "password": "StrongPassword123!",
                "role": "company",
                "is_staff": True,
                "is_superuser": True,
            },
            "school": None,
            "filiere": "Informatique",
            "niveau": "L3",
        }
        response = self.client.post("/api/students/", payload, format="json")
        user = User.objects.filter(email="attacker@example.com").first()
        self.assertTrue(response.status_code in {status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST})
        if user:
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertEqual(user.role, "student")

    @patch("appstage.serializers.send_activation_email.delay")
    def test_company_registration_cannot_set_admin_flags(self, _send_email):
        payload = {
            "user": {
                "username": "company",
                "email": "company@example.com",
                "password": "StrongPassword123!",
                "is_staff": True,
                "is_superuser": True,
            },
            "company": {"name": "Safe Corp", "secteur": "Tech", "description": "Test"},
            "role": "admin",
        }
        response = self.client.post("/api/company-users/", payload, format="json")
        user = User.objects.filter(email="company@example.com").first()
        self.assertTrue(response.status_code in {status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST})
        if user:
            self.assertFalse(user.is_staff)
            self.assertFalse(user.is_superuser)
            self.assertEqual(user.role, "company")

    def test_anonymous_user_list_is_blocked(self):
        response = self.client.get("/api/users/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_account_deletion_requires_authentication(self):
        response = self.client.delete(
            "/api/users/delete-account/",
            {"password": "StrongPassword123!"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_account_deletion_rejects_wrong_password(self):
        user = self.create_user("delete-wrong@example.com", "student")
        Student.objects.create(user=user, filiere="Info", niveau="L3")
        self.client.force_authenticate(user)

        response = self.client.delete(
            "/api/users/delete-account/",
            {"password": "WrongPassword!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(pk=user.pk).exists())

    def test_account_deletion_removes_user_and_student_data(self):
        user = self.create_user("delete@example.com", "student")
        student = Student.objects.create(user=user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Delete Corp", secteur="Tech", description="Test")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="À supprimer",
        )
        user_id = user.pk
        student_id = student.pk
        candidature_id = candidature.pk
        self.client.force_authenticate(user)

        response = self.client.delete(
            "/api/users/delete-account/",
            {"password": "StrongPassword123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(pk=user_id).exists())
        self.assertFalse(Student.objects.filter(pk=student_id).exists())
        self.assertFalse(Candidature.objects.filter(pk=candidature_id).exists())

    def test_student_cannot_access_another_student(self):
        user_a = self.create_user("a@example.com", "student")
        user_b = self.create_user("b@example.com", "student")
        Student.objects.create(user=user_a, filiere="Info", niveau="L3")
        student_b = Student.objects.create(user=user_b, filiere="Droit", niveau="L2")
        self.client.force_authenticate(user_a)
        response = self.client.get(f"/api/students/{student_b.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_company_cannot_modify_another_company_offer(self):
        company_a = Company.objects.create(name="A", secteur="Tech", description="A")
        company_b = Company.objects.create(name="B", secteur="Tech", description="B")
        user_a = self.create_user("company-a@example.com", "company")
        CompanyUser.objects.create(user=user_a, company=company_a, is_active=True)
        offer_b = self.create_offer(company_b)
        self.client.force_authenticate(user_a)
        response = self.client.patch(f"/api/offres-stage/{offer_b.pk}/", {"title": "Piraté"}, format="json")
        self.assertIn(response.status_code, {status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND})
        offer_b.refresh_from_db()
        self.assertEqual(offer_b.title, "Stage Django")

    def test_application_is_bound_to_authenticated_student(self):
        student_user = self.create_user("student@example.com", "student")
        other_user = self.create_user("other@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        other = Student.objects.create(user=other_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Company", secteur="Tech", description="Test")
        offer = self.create_offer(company)
        self.client.force_authenticate(student_user)
        response = self.client.post(
            "/api/candidatures/",
            {"student": other.pk, "offre_stage": offer.pk, "motivation": "Motivé"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Candidature.objects.get().student, student)

    def test_company_can_read_but_not_modify_an_applicant_profile(self):
        company = Company.objects.create(name="Recruiter", secteur="Tech", description="Test")
        company_user = self.create_user("recruiter@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("candidate@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(company)
        Candidature.objects.create(student=student, offre_stage=offer, motivation="Test")
        self.client.force_authenticate(company_user)

        read = self.client.get(f"/api/students/{student.pk}/")
        update = self.client.patch(f"/api/students/{student.pk}/", {"niveau": "Piraté"}, format="json")

        self.assertEqual(read.status_code, status.HTTP_200_OK)
        self.assertEqual(update.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_cannot_create_an_evaluation(self):
        student_user = self.create_user("student-eval@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Eval Corp", secteur="Tech", description="Test")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="Test",
        )
        self.client.force_authenticate(student_user)
        response = self.client.post(
            "/api/evaluations/",
            {"candidature": candidature.pk, "score": 10, "comments": "Auto-évaluation"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Evaluation.objects.exists())


class PaymentConfirmationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="billing",
            email="billing@example.com",
            password="StrongPassword123!",
            role="company",
            is_active=True,
        )
        self.company = Company.objects.create(name="Billing", secteur="Tech", description="Test")
        CompanyUser.objects.create(user=self.user, company=self.company, is_active=True)
        self.plan = SubscriptionPlan.objects.create(name="Pro", price="9.90", max_offres=3, duration_days=30)
        self.client.force_authenticate(self.user)

    @patch("appstage.views.PaymentViewSet._verify_paypal", return_value="paypal:order-1")
    def test_verified_payment_is_idempotent(self, _verify):
        payload = {"provider": "paypal", "transaction_id": "order-1", "plan_id": self.plan.pk}
        first = self.client.post("/api/payments/confirm/", payload, format="json")
        subscription = CompanySubscription.objects.get(company=self.company)
        first_end_date = subscription.end_date
        second = self.client.post("/api/payments/confirm/", payload, format="json")
        subscription.refresh_from_db()

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(Payment.objects.count(), 1)
        self.assertEqual(subscription.end_date, first_end_date)

    def test_paid_plan_cannot_be_activated_without_confirmation(self):
        response = self.client.post(
            "/api/company-subscriptions/",
            {"plan_id": self.plan.pk, "end_date": timezone.now() + timedelta(days=30)},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
