from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user_model = get_user_model()

    def test_register_creates_user_and_returns_token(self):
        response = self.client.post(
            "/auth/register",
            {
                "username": "alice",
                "email": "alice@example.com",
                "password": "SecurePass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIn("access_token", response.data)
        self.assertTrue(self.user_model.objects.filter(username="alice").exists())

    def test_login_returns_jwt_token(self):
        self.user_model.objects.create_user(
            username="bob",
            email="bob@example.com",
            password="SecurePass123!",
        )

        response = self.client.post(
            "/auth/login",
            {
                "identifier": "bob",
                "password": "SecurePass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.data)

