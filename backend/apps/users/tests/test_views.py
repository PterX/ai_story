from django.contrib.auth.models import User
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase


class AdminAccessTests(APITestCase):
    def test_staff_user_without_superuser_cannot_access_admin(self):
        user = User.objects.create_user(
            username='staff-user',
            password='secret123',
            is_staff=True,
            is_superuser=False,
        )
        self.client.force_login(user)

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('/admin/login/', response['Location'])

    def test_superuser_can_access_admin(self):
        user = User.objects.create_superuser(
            username='root-user',
            email='root@example.com',
            password='secret123',
        )
        self.client.force_login(user)

        response = self.client.get('/admin/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class RegisterViewTests(APITestCase):
    def _payload(self, **overrides):
        payload = {
            'username': 'linknow-user',
            'email': 'linknow@example.com',
            'password': 'secret123',
            'password_confirm': 'secret123',
            'invite_code': 'invite-123',
        }
        payload.update(overrides)
        return payload

    @override_settings(LINKNOW_REGISTRATION_INVITE_CODE='invite-123')
    def test_register_with_valid_invite_code_returns_tokens(self):
        response = self.client.post('/api/v1/users/register/', self._payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['user']['username'], 'linknow-user')
        self.assertIn('access', response.data['data']['tokens'])
        self.assertIn('refresh', response.data['data']['tokens'])
        self.assertTrue(User.objects.filter(username='linknow-user').exists())

    @override_settings(LINKNOW_REGISTRATION_INVITE_CODE='invite-123')
    def test_register_rejects_invalid_invite_code(self):
        response = self.client.post(
            '/api/v1/users/register/',
            self._payload(invite_code='wrong'),
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('invite_code', response.data)
        self.assertFalse(User.objects.filter(username='linknow-user').exists())

    @override_settings(LINKNOW_REGISTRATION_INVITE_CODE='')
    def test_register_rejects_when_invite_code_not_configured(self):
        response = self.client.post('/api/v1/users/register/', self._payload(), format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['invite_code'][0], '注册邀请码未配置')
        self.assertFalse(User.objects.filter(username='linknow-user').exists())
