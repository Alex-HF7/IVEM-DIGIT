from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import redis
from django.contrib.auth import get_user_model, SESSION_KEY
from django.conf import settings
from django.test import TestCase, SimpleTestCase, Client, RequestFactory, override_settings
from . import throttle


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
                   LOGIN_PAIR_LIMIT=3, LOGIN_ACCOUNT_LIMIT=6, LOGIN_IP_LIMIT=20,
                   LOGIN_RATE_SECONDS=60)
class LoginSecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.user=User.objects.create_user(username='operador_login',password='PasswordTestOnly')
        User.objects.create_user(username='cuenta_inactiva',password='PasswordTestOnly',is_active=False)
        cls.admin=User.objects.create_superuser(username='admin_login',email='',password='PasswordTestOnly')

    def setUp(self):
        self.prefix='test:login:'+uuid4().hex+':'
        self.override=self.settings(LOGIN_RATE_PREFIX=self.prefix)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.cache=throttle.connection(settings.LOGIN_REDIS_URL)
        self.cache.ping()
        self.addCleanup(self.clear_keys)

    def clear_keys(self):
        keys=list(self.cache.scan_iter(match=self.prefix+'*'))
        if keys:self.cache.delete(*keys)

    def post(self,username='operador_login',password='Incorrecta',**extra):
        return self.client.post('/',{'username':username,'password':password,**extra},REMOTE_ADDR='198.51.100.20')

    def test_form_has_accessibility_and_no_third_party_scripts(self):
        response=self.client.get('/')
        self.assertContains(response,'autocomplete="username"')
        self.assertContains(response,'autocomplete="current-password"')
        self.assertContains(response,'password-toggle')
        self.assertContains(response,'csrfmiddlewaretoken')
        self.assertNotContains(response,'<script src="https://')
        self.assertIn("script-src 'self'",response['Content-Security-Policy'])
        self.assertIn('no-store',response['Cache-Control'])

    def test_invalid_unknown_and_inactive_accounts_have_same_message_and_hide_password(self):
        for username in ['operador_login','no_existe','cuenta_inactiva']:
            response=self.post(username)
            self.assertContains(response,'Usuario o contraseña incorrectos.')
            self.assertNotContains(response,'value="Incorrecta"')
            self.assertNotIn(SESSION_KEY,self.client.session)

    def test_lockout_applies_even_with_correct_password_and_expires(self):
        for _ in range(3):self.assertEqual(self.post().status_code,200)
        response=self.post(password='PasswordTestOnly')
        self.assertEqual(response.status_code,429)
        self.assertGreater(int(response['Retry-After']),0)
        self.assertContains(response,'Demasiados intentos',status_code=429)
        self.assertNotIn(SESSION_KEY,self.client.session)
        for key in self.cache.scan_iter(match=self.prefix+'*'):self.cache.expire(key,0)
        response=self.post(password='PasswordTestOnly')
        self.assertRedirects(response,'/inicio/',fetch_redirect_response=False)

    def test_success_rotates_session_and_csrf_and_blocks_external_next(self):
        response=self.client.get('/')
        csrf_before=response.cookies['csrftoken'].value
        session=self.client.session
        session['test']='retained';session.save()
        old_key=session.session_key
        self.client.cookies['sessionid']=old_key
        response=self.post(password='PasswordTestOnly',next='https://example.invalid/steal')
        self.assertRedirects(response,'/inicio/',fetch_redirect_response=False)
        self.assertNotEqual(self.client.session.session_key,old_key)
        self.assertEqual(self.client.session[SESSION_KEY],str(self.user.pk))
        self.assertNotEqual(response.cookies['csrftoken'].value,csrf_before)
        self.assertTrue(response.cookies['sessionid']['httponly'])
        self.assertEqual(response.cookies['sessionid']['samesite'],'Lax')

    def test_admin_and_public_login_share_protection(self):
        for _ in range(3):
            self.client.post('/admin/login/',{'username':'admin_login','password':'Incorrecta'},REMOTE_ADDR='198.51.100.20')
        response=self.post(username='admin_login',password='PasswordTestOnly')
        self.assertEqual(response.status_code,429)
        self.assertNotIn(SESSION_KEY,self.client.session)

    def test_csrf_and_cache_failure_do_not_allow_authentication(self):
        from unittest.mock import patch
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post('/',{'username':'operador_login','password':'PasswordTestOnly'}).status_code,403)
        with patch('login.throttle.reserve',side_effect=redis.ConnectionError()):
            with self.assertLogs('login.backends',level='ERROR'):
                response=self.post(password='PasswordTestOnly')
        self.assertEqual(response.status_code,503)
        self.assertNotIn(SESSION_KEY,self.client.session)

    def test_rate_reservation_is_atomic_and_keys_do_not_store_usernames_or_passwords(self):
        def reserve(_):
            return throttle.reserve(RequestFactory().post('/',REMOTE_ADDR='198.51.100.30'),'operador_login')
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes=list(executor.map(reserve,range(12)))
        self.assertEqual(sum(retry==0 for _,retry in outcomes),3)
        for key in self.cache.scan_iter(match=self.prefix+'*'):
            self.assertNotIn(b'operador_login',key)
            self.assertNotIn(b'PasswordTestOnly',key)
            self.assertGreater(self.cache.ttl(key),0)

    def test_distributed_account_attempts_and_ip_spraying_are_limited(self):
        factory=RequestFactory()
        for index in range(6):
            _,retry=throttle.reserve(factory.post('/',REMOTE_ADDR=f'198.51.100.{index+1}'),'cuenta')
            self.assertEqual(retry,0)
        _,retry=throttle.reserve(factory.post('/',REMOTE_ADDR='198.51.100.99'),'cuenta')
        self.assertGreater(retry,0)
        for index in range(20):
            _,retry=throttle.reserve(factory.post('/',REMOTE_ADDR='203.0.113.1'),f'cuenta_{index}')
            self.assertEqual(retry,0)
        _,retry=throttle.reserve(factory.post('/',REMOTE_ADDR='203.0.113.1'),'otra')
        self.assertGreater(retry,0)


class TrustedProxyTests(SimpleTestCase):
    @override_settings(LOGIN_TRUSTED_PROXIES=[])
    def test_forwarded_header_cannot_spoof_untrusted_peer(self):
        request=RequestFactory().get('/',REMOTE_ADDR='198.51.100.3',HTTP_X_FORWARDED_FOR='203.0.113.50')
        self.assertEqual(throttle.client_ip(request),'198.51.100.3')

    @override_settings(LOGIN_TRUSTED_PROXIES=['127.0.0.1/32'])
    def test_only_trusted_proxy_chain_is_used(self):
        request=RequestFactory().get('/',REMOTE_ADDR='127.0.0.1',HTTP_X_FORWARDED_FOR='203.0.113.50, 198.51.100.3')
        self.assertEqual(throttle.client_ip(request),'198.51.100.3')
        request.META['HTTP_X_FORWARDED_FOR']='malformed'
        self.assertEqual(throttle.client_ip(request),'127.0.0.1')
