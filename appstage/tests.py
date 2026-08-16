from datetime import date, timedelta
import base64
from importlib import import_module
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.apps import apps
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .models import (
    AffectationStage,
    Candidature,
    Company,
    CompanySubscription,
    CompanyUser,
    Evaluation,
    Notification,
    OffreStage,
    Payment,
    PushDevice,
    SocialIdentity,
    StageWeeklyReport,
    Student,
    SubscriptionPlan,
    User,
)
from .tasks import create_weekly_stage_reminders, send_push_notification


class ApiSecurityTests(APITestCase):
    def create_user(self, email, role, **extra):
        if role == "student":
            extra.setdefault("prenom", "Jean")
            extra.setdefault("postnom", "Test")
            extra.setdefault("telephone", "+243000000000")
        return User.objects.create_user(
            username=email.split("@")[0],
            email=email,
            password="StrongPassword123!",
            role=role,
            is_active=True,
            **extra,
        )

    @patch("appstage.views.google_id_token.verify_oauth2_token")
    def test_google_login_creates_an_incomplete_student_profile(self, verify_token):
        verify_token.return_value = {
            "sub": "google-user-1",
            "aud": "totinda-client",
            "email": "google@example.com",
            "email_verified": True,
            "given_name": "Amina",
            "family_name": "Kalala",
        }

        with self.settings(GOOGLE_OAUTH_CLIENT_IDS=["totinda-client"]):
            response = self.client.post(
                "/api/auth/google/",
                {"id_token": "valid-google-token"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertFalse(response.data["user"]["profile_completion"]["can_apply"])
        self.assertIn("postnom", response.data["user"]["profile_completion"]["missing_fields"])
        self.assertTrue(Student.objects.filter(user__email="google@example.com").exists())
        self.assertTrue(SocialIdentity.objects.filter(provider_user_id="google-user-1").exists())

    @patch("appstage.views.google_id_token.verify_oauth2_token")
    def test_google_login_requires_password_to_link_existing_account(self, verify_token):
        user = self.create_user("existing@example.com", "student")
        Student.objects.create(user=user, filiere="Info", niveau="L3")
        verify_token.return_value = {
            "sub": "google-user-existing",
            "aud": "totinda-client",
            "email": user.email,
            "email_verified": True,
        }

        with self.settings(GOOGLE_OAUTH_CLIENT_IDS=["totinda-client"]):
            first = self.client.post(
                "/api/auth/google/",
                {"id_token": "valid-google-token"},
                format="json",
            )
            linked = self.client.post(
                "/api/auth/google/",
                {
                    "id_token": "valid-google-token",
                    "password": "StrongPassword123!",
                },
                format="json",
            )

        self.assertEqual(first.status_code, status.HTTP_409_CONFLICT)
        self.assertEqual(first.data["code"], "account_link_required")
        self.assertEqual(linked.status_code, status.HTTP_200_OK)
        self.assertTrue(SocialIdentity.objects.filter(user=user).exists())

    def test_incomplete_profile_is_blocked_then_can_complete_and_apply(self):
        user = self.create_user(
            "incomplete@example.com",
            "student",
            postnom="",
            telephone="",
        )
        Student.objects.create(user=user)
        company = Company.objects.create(name="Profile Corp", secteur="Tech", description="Test")
        offer = self.create_offer(company)
        self.client.force_authenticate(user)

        blocked = self.client.post(
            "/api/candidatures/",
            {"offre_stage": offer.pk, "motivation": "Motivé"},
            format="json",
        )
        completed = self.client.patch(
            "/api/users/complete-student-profile/",
            {
                "username": "Kalala",
                "postnom": "Mbuyi",
                "prenom": "Amina",
                "telephone": "+243000000000",
                "filiere": "Informatique",
                "niveau": "Licence LMD (Bac +3)",
            },
            format="json",
        )
        user.refresh_from_db()
        self.client.force_authenticate(user)
        created = self.client.post(
            "/api/candidatures/",
            {"offre_stage": offer.pk, "motivation": "Motivé"},
            format="json",
        )

        self.assertEqual(blocked.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(blocked.data["code"], "incomplete_profile")
        self.assertIn("postnom", blocked.data["missing_fields"])
        self.assertEqual(completed.status_code, status.HTTP_200_OK)
        self.assertTrue(completed.data["profile_completion"]["can_apply"])
        self.assertEqual(created.status_code, status.HTTP_201_CREATED, created.data)

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

    def test_user_can_upload_own_profile_picture(self):
        user = self.create_user("picture@example.com", "student")
        Student.objects.create(user=user, filiere="Info", niveau="L3")
        self.client.force_authenticate(user)
        picture = SimpleUploadedFile(
            "profile.png",
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.patch(
                f"/api/users/{user.pk}/",
                {"profile_picture": picture},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("profile_pictures/", response.data["profile_picture"])

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

    def test_active_offer_exposes_company_name_and_logo(self):
        student_user = self.create_user("branding@example.com", "student")
        Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(
            name="Brand Corp",
            secteur="Tech",
            description="Test",
            logo="company_logos/brand.png",
        )
        self.create_offer(company, title="Stage Brand")
        self.client.force_authenticate(student_user)

        response = self.client.get("/api/offres-stage/offresactives/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]["nom_entreprise"], "Brand Corp")
        self.assertIn("company_logos/brand.png", response.data[0]["logo_entreprise"])

    def test_company_user_can_upload_company_logo(self):
        company = Company.objects.create(name="Logo Corp", secteur="Tech", description="Test")
        company_user = self.create_user("logo-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        self.client.force_authenticate(company_user)
        logo = SimpleUploadedFile(
            "logo.png",
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
            ),
            content_type="image/png",
        )

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.patch(
                f"/api/companies/{company.pk}/",
                {"logo": logo},
                format="multipart",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("company_logos/", response.data["logo"])

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

    def test_student_sees_company_decision_with_offer_details(self):
        student_user = self.create_user("decision@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="Licence LMD")
        company = Company.objects.create(name="Decision Corp", secteur="Tech", description="Test")
        company_user = self.create_user("decision-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        offer = self.create_offer(company, title="Stage Mobile")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Motivé",
        )

        self.client.force_authenticate(company_user)
        update = self.client.patch(
            f"/api/candidatures/{candidature.pk}/",
            {
                "status": "accepted",
                "company_message": "Présentez-vous lundi à 9 heures.",
            },
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)
        candidature.refresh_from_db()
        self.assertEqual(candidature.reviewed_by, company_user)
        self.assertIsNotNone(candidature.reviewed_at)
        self.assertFalse(Evaluation.objects.filter(candidature=candidature).exists())
        affectation = AffectationStage.objects.get(candidature=candidature)
        self.assertEqual(affectation.student, student)
        self.assertEqual(affectation.offre_stage, offer)
        self.assertEqual(affectation.start_date, offer.start_date)
        self.assertEqual(affectation.end_date, offer.end_date)
        self.assertEqual(affectation.status, "in_progress")

        self.client.force_authenticate(student_user)
        response = self.client.get("/api/candidatures/?limit=100")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        item = response.data["results"][0]
        self.assertEqual(item["status"], "accepted")
        self.assertEqual(item["offre_title"], "Stage Mobile")
        self.assertEqual(item["company_name"], "Decision Corp")
        self.assertEqual(item["company_message"], "Présentez-vous lundi à 9 heures.")
        self.assertIsNotNone(item["reviewed_at"])
        self.assertEqual(item["affectation_id"], affectation.pk)

    def test_rejected_application_does_not_create_an_affectation(self):
        company = Company.objects.create(name="Reject Corp", secteur="Tech", description="Test")
        company_user = self.create_user("reject-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("reject-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="Test",
        )
        self.client.force_authenticate(company_user)

        response = self.client.patch(
            f"/api/candidatures/{candidature.pk}/",
            {"status": "rejected", "company_message": "Profil non retenu."},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(AffectationStage.objects.filter(candidature=candidature).exists())

    def test_company_manages_stage_and_student_has_read_only_access(self):
        company = Company.objects.create(name="Stage Corp", secteur="Tech", description="Test")
        company_user = self.create_user("stage-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("stage-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company, title="Stage API"),
            motivation="Test",
        )
        self.client.force_authenticate(company_user)
        decision = self.client.patch(
            f"/api/candidatures/{candidature.pk}/",
            {"status": "accepted", "company_message": "Bienvenue."},
            format="json",
        )
        self.assertEqual(decision.status_code, status.HTTP_200_OK)
        affectation = AffectationStage.objects.get(candidature=candidature)
        decision_notification = Notification.objects.get(
            recipient=student_user,
            notification_type="application_decision",
        )
        self.assertEqual(decision_notification.data["stage_id"], affectation.pk)
        self.assertEqual(decision_notification.data["status"], "accepted")

        update = self.client.patch(
            f"/api/affectations-stage/{affectation.pk}/",
            {
                "objectives": "Participer au développement de l'application.",
                "supervisor_name": "Marie Responsable",
                "supervisor_email": "marie@example.com",
            },
            format="json",
        )
        self.assertEqual(update.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(student_user)
        listing = self.client.get("/api/affectations-stage/")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        item = listing.data["results"][0]
        self.assertEqual(item["id"], affectation.pk)
        self.assertEqual(item["offre_title"], "Stage API")
        self.assertEqual(item["company_name"], "Stage Corp")
        self.assertEqual(item["objectives"], "Participer au développement de l'application.")

        forbidden = self.client.patch(
            f"/api/affectations-stage/{affectation.pk}/",
            {"objectives": "Objectif falsifié"},
            format="json",
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_cannot_access_another_company_stage(self):
        owner = Company.objects.create(name="Owner Corp", secteur="Tech", description="Test")
        outsider = Company.objects.create(name="Outsider Corp", secteur="Tech", description="Test")
        outsider_user = self.create_user("outsider-stage@example.com", "company")
        CompanyUser.objects.create(user=outsider_user, company=outsider, is_active=True)
        student_user = self.create_user("private-stage@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(owner)
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Test",
            status="accepted",
        )
        affectation = AffectationStage.objects.create(
            candidature=candidature,
            student=student,
            offre_stage=offer,
        )
        self.client.force_authenticate(outsider_user)

        response = self.client.get(f"/api/affectations-stage/{affectation.pk}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_stage_dates_must_be_consistent(self):
        company = Company.objects.create(name="Dates Corp", secteur="Tech", description="Test")
        company_user = self.create_user("dates-stage@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("dates-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(company)
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Test",
            status="accepted",
        )
        affectation = AffectationStage.objects.create(
            candidature=candidature,
            student=student,
            offre_stage=offer,
            start_date=offer.start_date,
            end_date=offer.end_date,
        )
        self.client.force_authenticate(company_user)

        response = self.client.patch(
            f"/api/affectations-stage/{affectation.pk}/",
            {"end_date": (offer.start_date - timedelta(days=1)).isoformat()},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("end_date", response.data)

    def test_company_decision_requires_a_message(self):
        company = Company.objects.create(name="No Message Corp", secteur="Tech", description="Test")
        company_user = self.create_user("no-message@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("no-message-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="Test",
        )
        self.client.force_authenticate(company_user)

        response = self.client.patch(
            f"/api/candidatures/{candidature.pk}/",
            {"status": "rejected", "company_message": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        candidature.refresh_from_db()
        self.assertEqual(candidature.status, "pending")
        self.assertEqual(candidature.company_message, "")
        self.assertIsNone(candidature.reviewed_at)

    def test_decision_migration_preserves_legacy_message(self):
        student_user = self.create_user("legacy-decision@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Legacy Corp", secteur="Tech", description="Test")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="Test",
            status="accepted",
        )
        evaluation = Evaluation.objects.create(
            candidature=candidature,
            score=0,
            comments="Ancien message préservé",
        )

        migration = import_module(
            "appstage.migrations.0017_candidature_decision_fields"
        )
        migration.migrate_decision_messages(apps, None)

        candidature.refresh_from_db()
        self.assertEqual(candidature.company_message, "Ancien message préservé")
        self.assertEqual(candidature.reviewed_at, evaluation.created_at)
        self.assertFalse(Evaluation.objects.filter(pk=evaluation.pk).exists())

    def test_stage_migration_creates_missing_accepted_affectation(self):
        student_user = self.create_user("legacy-stage@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Legacy Stage Corp", secteur="Tech", description="Test")
        offer = self.create_offer(company, title="Stage historique")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Test",
            status="accepted",
        )

        migration = import_module(
            "appstage.migrations.0018_affectationstage_lifecycle"
        )
        migration.link_and_create_affectations(apps, None)

        affectation = AffectationStage.objects.get(candidature=candidature)
        self.assertEqual(affectation.student, student)
        self.assertEqual(affectation.offre_stage, offer)
        self.assertEqual(affectation.start_date, offer.start_date)
        self.assertEqual(affectation.end_date, offer.end_date)
        self.assertEqual(affectation.status, "in_progress")

    def test_student_cannot_write_company_decision_fields(self):
        student_user = self.create_user("student-decision@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Protected Corp", secteur="Tech", description="Test")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=self.create_offer(company),
            motivation="Test",
        )
        self.client.force_authenticate(student_user)

        response = self.client.patch(
            f"/api/candidatures/{candidature.pk}/",
            {"company_message": "Message falsifié"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        candidature.refresh_from_db()
        self.assertEqual(candidature.company_message, "")

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

    def test_company_can_only_evaluate_a_completed_stage_with_valid_score(self):
        company = Company.objects.create(name="Final Eval Corp", secteur="Tech", description="Test")
        company_user = self.create_user("final-eval-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("final-eval-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(company)
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Test",
            status="accepted",
        )
        affectation = AffectationStage.objects.create(
            candidature=candidature,
            student=student,
            offre_stage=offer,
            status="in_progress",
            start_date=offer.start_date,
            end_date=offer.end_date,
        )
        self.client.force_authenticate(company_user)

        too_early = self.client.post(
            "/api/evaluations/",
            {"candidature": candidature.pk, "score": 8, "comments": "Bon stage."},
            format="json",
        )
        self.assertEqual(too_early.status_code, status.HTTP_400_BAD_REQUEST)

        affectation.status = "completed"
        affectation.save(update_fields=["status"])
        invalid_score = self.client.post(
            "/api/evaluations/",
            {"candidature": candidature.pk, "score": 11, "comments": "Bon stage."},
            format="json",
        )
        self.assertEqual(invalid_score.status_code, status.HTTP_400_BAD_REQUEST)

        created = self.client.post(
            "/api/evaluations/",
            {"candidature": candidature.pk, "score": 9, "comments": "Très bonne progression."},
            format="json",
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Evaluation.objects.get().score, 9)
        self.assertTrue(Notification.objects.filter(
            recipient=student_user,
            notification_type="evaluation_published",
        ).exists())

        certificate = self.client.get(
            f"/api/affectations-stage/{affectation.pk}/attestation/"
        )
        self.assertEqual(certificate.status_code, status.HTTP_200_OK)
        self.assertTrue(base64.b64decode(certificate.data["content_base64"]).startswith(b"%PDF"))
        self.assertIn("TOT-", certificate.data["reference"])

        self.client.force_authenticate(user=None)
        verification = self.client.get(
            "/api/attestations/verify/",
            {"reference": certificate.data["reference"].lower()},
        )
        self.assertEqual(verification.status_code, status.HTTP_200_OK)
        self.assertTrue(verification.data["valid"])
        self.assertEqual(verification.data["company_name"], company.name)
        self.assertEqual(verification.data["internship_title"], offer.title)
        self.assertNotIn("score", verification.data)
        self.assertNotIn("comments", verification.data)

        unknown = self.client.get(
            "/api/attestations/verify/",
            {"reference": "TOT-INCONNUE"},
        )
        self.assertEqual(unknown.status_code, status.HTTP_200_OK)
        self.assertFalse(unknown.data["valid"])

        self.client.force_authenticate(company_user)
        protected_evaluation = self.client.patch(
            f"/api/evaluations/{created.data['id']}/",
            {"score": 10, "comments": "Correction prématurée."},
            format="json",
        )
        self.assertEqual(protected_evaluation.status_code, status.HTTP_400_BAD_REQUEST)

        history = self.client.get(
            "/api/attestations/history/",
            {"stage_id": affectation.pk},
        )
        self.assertEqual(history.status_code, status.HTTP_200_OK)
        self.assertEqual(history.data[0]["version"], 1)
        self.assertEqual(history.data[0]["verification_count"], 1)

        revoked = self.client.post(
            f"/api/attestations/{certificate.data['reference']}/revoke/",
            {"reason": "La note finale doit être corrigée."},
            format="json",
        )
        self.assertEqual(revoked.status_code, status.HTTP_200_OK)
        self.assertFalse(revoked.data["valid"])

        corrected = self.client.patch(
            f"/api/evaluations/{created.data['id']}/",
            {"score": 10, "comments": "Évaluation finale corrigée."},
            format="json",
        )
        self.assertEqual(corrected.status_code, status.HTTP_200_OK)
        replacement = self.client.get(
            f"/api/affectations-stage/{affectation.pk}/attestation/"
        )
        self.assertEqual(replacement.status_code, status.HTTP_200_OK)
        self.assertEqual(replacement.data["version"], 2)
        self.assertNotEqual(replacement.data["reference"], certificate.data["reference"])

    def test_student_submits_weekly_report_and_company_validates_it(self):
        company = Company.objects.create(name="Journal Corp", secteur="Tech", description="Test")
        company_user = self.create_user("journal-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("journal-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(company, title="Stage journal")
        candidature = Candidature.objects.create(
            student=student,
            offre_stage=offer,
            motivation="Test",
            status="accepted",
        )
        affectation = AffectationStage.objects.create(
            candidature=candidature,
            student=student,
            offre_stage=offer,
            start_date=offer.start_date,
            end_date=offer.end_date,
            status="in_progress",
        )
        week_start = date.today() - timedelta(days=date.today().weekday())

        self.client.force_authenticate(student_user)
        creation = self.client.post(
            "/api/rapports-stage/",
            {
                "affectation": affectation.pk,
                "week_start": week_start.isoformat(),
                "activities": "Développement de l'API.",
                "learnings": "Tests automatisés.",
                "difficulties": "Configuration locale.",
                "status": "submitted",
            },
            format="json",
        )
        self.assertEqual(creation.status_code, status.HTTP_201_CREATED)
        report = StageWeeklyReport.objects.get()
        self.assertIsNotNone(report.submitted_at)
        self.assertTrue(Notification.objects.filter(
            recipient=company_user,
            notification_type="report_submitted",
        ).exists())

        # Certains responsables d'entreprise ont aussi accès au Django admin.
        # Ce statut ne doit pas contourner le workflow de validation.
        company_user.is_staff = True
        company_user.save(update_fields=["is_staff"])
        self.client.force_authenticate(company_user)
        listing = self.client.get(f"/api/rapports-stage/?affectation={affectation.pk}")
        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["results"][0]["id"], report.pk)

        validation = self.client.patch(
            f"/api/rapports-stage/{report.pk}/",
            {"status": "validated", "company_comment": "Très bonne progression."},
            format="json",
        )
        self.assertEqual(validation.status_code, status.HTTP_200_OK)
        report.refresh_from_db()
        self.assertEqual(report.status, "validated")
        self.assertEqual(report.validated_by, company_user)
        self.assertIsNotNone(report.validated_at)
        self.assertTrue(Notification.objects.filter(
            recipient=student_user,
            notification_type="report_validated",
        ).exists())
        progress_response = self.client.get(
            f"/api/affectations-stage/{affectation.pk}/"
        )
        self.assertEqual(progress_response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress_response.data["progress"]["validated_weeks"], 1)
        self.assertEqual(progress_response.data["progress"]["pending_reports"], 0)
        self.assertEqual(progress_response.data["progress"]["missing_weeks"], 0)
        self.assertGreater(progress_response.data["progress"]["total_weeks"], 0)

        self.client.force_authenticate(student_user)
        forbidden = self.client.patch(
            f"/api/rapports-stage/{report.pk}/",
            {"activities": "Contenu modifié après validation."},
            format="json",
        )
        self.assertEqual(forbidden.status_code, status.HTTP_403_FORBIDDEN)

    def test_company_cannot_see_draft_weekly_report(self):
        company = Company.objects.create(name="Draft Corp", secteur="Tech", description="Test")
        company_user = self.create_user("draft-company@example.com", "company")
        CompanyUser.objects.create(user=company_user, company=company, is_active=True)
        student_user = self.create_user("draft-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        offer = self.create_offer(company)
        affectation = AffectationStage.objects.create(student=student, offre_stage=offer)
        StageWeeklyReport.objects.create(
            affectation=affectation,
            week_start=date.today() - timedelta(days=date.today().weekday()),
            activities="Brouillon privé",
        )
        self.client.force_authenticate(company_user)

        listing = self.client.get("/api/rapports-stage/")

        self.assertEqual(listing.status_code, status.HTTP_200_OK)
        self.assertEqual(listing.data["count"], 0)

    def test_notifications_are_private_and_can_be_marked_read(self):
        owner = self.create_user("notification-owner@example.com", "student")
        outsider = self.create_user("notification-outsider@example.com", "student")
        notification = Notification.objects.create(
            recipient=owner,
            notification_type="weekly_reminder",
            title="Rappel",
            message="Complétez votre rapport.",
        )
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get("/api/notifications/").data["count"], 0)
        self.assertEqual(
            self.client.post(f"/api/notifications/{notification.pk}/mark-read/").status_code,
            status.HTTP_404_NOT_FOUND,
        )

        self.client.force_authenticate(owner)
        unread = self.client.get("/api/notifications/unread-count/")
        self.assertEqual(unread.data["count"], 1)
        marked = self.client.post(f"/api/notifications/{notification.pk}/mark-read/")
        self.assertEqual(marked.status_code, status.HTTP_200_OK)
        self.assertTrue(marked.data["is_read"])

    def test_weekly_reminder_is_non_blocking_and_deduplicated(self):
        student_user = self.create_user("reminder-student@example.com", "student")
        student = Student.objects.create(user=student_user, filiere="Info", niveau="L3")
        company = Company.objects.create(name="Reminder Corp", secteur="Tech", description="Test")
        offer = self.create_offer(company)
        AffectationStage.objects.create(
            student=student,
            offre_stage=offer,
            status="in_progress",
        )

        create_weekly_stage_reminders()
        create_weekly_stage_reminders()

        self.assertEqual(Notification.objects.filter(
            recipient=student_user,
            notification_type="weekly_reminder",
        ).count(), 1)

    def test_push_device_registration_is_private_and_can_be_deactivated(self):
        owner = self.create_user("push-owner@example.com", "student")
        outsider = self.create_user("push-outsider@example.com", "student")
        token = "ExponentPushToken[test-device-token]"
        self.client.force_authenticate(owner)

        created = self.client.post("/api/push-devices/", {
            "expo_push_token": token,
            "platform": "android",
        }, format="json")

        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        self.assertEqual(PushDevice.objects.get().user, owner)
        self.client.force_authenticate(outsider)
        self.assertEqual(self.client.get("/api/push-devices/").data["count"], 0)
        self.client.force_authenticate(owner)
        deactivated = self.client.post("/api/push-devices/deactivate/", {
            "expo_push_token": token,
        }, format="json")
        self.assertEqual(deactivated.status_code, status.HTTP_200_OK)
        self.assertFalse(PushDevice.objects.get().is_active)

    @patch("appstage.tasks.requests.post")
    def test_push_delivery_deactivates_an_expired_expo_token(self, post):
        owner = self.create_user("expired-push@example.com", "student")
        device = PushDevice.objects.create(
            user=owner,
            expo_push_token="ExponentPushToken[expired-device]",
            platform="android",
        )
        notification = Notification.objects.create(
            recipient=owner,
            notification_type="weekly_reminder",
            title="Rappel",
            message="Complétez votre rapport.",
        )
        post.return_value.raise_for_status.return_value = None
        post.return_value.json.return_value = {
            "data": [{
                "status": "error",
                "message": "Device is not registered",
                "details": {"error": "DeviceNotRegistered"},
            }],
        }

        sent = send_push_notification(notification.id)

        device.refresh_from_db()
        self.assertEqual(sent, 0)
        self.assertFalse(device.is_active)


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
