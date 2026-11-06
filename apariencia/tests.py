import hashlib
import re
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, DatabaseError
from django.test import SimpleTestCase, TestCase, Client
from django.urls import reverse
from gestion_tables.models import ConfiguracionTable
from .models import BrandImage, WebAppearance, PrintIdentity
from .services import web_branding, print_branding
from .specs import DEFAULT_COLORS
from .validators import validate_image


def svg(slot='print_left',content='<path d="M0 0h10v10z" fill="#682145"/>',width=None,height=None):
    from .specs import SLOTS
    w,h=SLOTS[slot][2:]
    w=width if width is not None else w
    h=height if height is not None else h
    return SimpleUploadedFile('identidad.svg',f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">{content}</svg>'.encode(),content_type='image/svg+xml')


class ImageValidationTests(SimpleTestCase):
    def test_accepts_original_svg_canvas_and_exact_raster_dimensions(self):
        self.assertEqual(validate_image(svg(),'print_left')['mime'],'image/svg+xml')
        output=BytesIO();Image.new('RGB',(477,149),'white').save(output,format='PNG')
        self.assertEqual(validate_image(SimpleUploadedFile('logo.png',output.getvalue()),'print_left')['width'],477)
        self.assertEqual(validate_image(svg('print_right'),'print_right')['width'],986.18)

    def test_rejects_incorrect_canvas_fake_images_and_oversized_files(self):
        for upload in [svg(width=500),SimpleUploadedFile('falso.png',b'no es imagen'),SimpleUploadedFile('imagen.svg',b'x'*(5*1024*1024+1))]:
            with self.assertRaises(ValidationError):validate_image(upload,'print_left')

    def test_rejects_svg_scripts_external_references_and_active_content(self):
        contents=['<script>alert(1)</script>','<g onload="alert(1)"/>',
                  '<image href="https://example.invalid/a.png"/>','<foreignObject/>',
                  '<use href="https://example.invalid/a.svg#id"/>',
                  '<path style="fill:url(https://example.invalid/a)"/>',
                  '<style>@import "https://example.invalid/style";</style>',
                  '<animate attributeName="href"/>', '<path style="fill:ur\\6c(https://example.invalid/a)"/>']
        for content in contents:
            with self.subTest(content=content):
                with self.assertRaises(ValidationError):validate_image(svg(content=content),'print_left')
        payload=b'<!DOCTYPE svg [<!ENTITY x "unsafe">]><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 477 149"><text>&x;</text></svg>'
        instruction=b'<?xml-stylesheet href="https://example.invalid/style.css" type="text/css"?><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 477 149"/>'
        for raw in [payload,payload.decode().encode('utf-16'),instruction,instruction.decode().encode('utf-16')]:
            with self.assertRaises(ValidationError):validate_image(SimpleUploadedFile('logo.svg',raw),'print_left')

    def test_print_styles_remain_byte_for_byte_identical(self):
        source=(Path(settings.BASE_DIR)/'documento/templates/documento/formato_oficio.html').read_text()
        style=re.search(r'<style>(.*?)</style>',source,re.S).group(1)
        self.assertEqual(hashlib.sha256(style.encode()).hexdigest(),'7e025a5a4af221f61d2c1a35f73b0b9b12ce774ea256ab8e94c2a1a353d29d2b')


class AppearanceAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User=get_user_model()
        cls.admin=User.objects.create_superuser(username='brand_admin',email='',password=None)
        cls.staff=User.objects.create_user(username='brand_staff',is_staff=True)
        ConfiguracionTable.objects.create(anno=2044)
        with connection.cursor() as cursor:
            cursor.execute("""INSERT INTO oficios_ucg_2044 (fecha_recibido,fecha_oficio,enviado_por,procedencia,asunto,pendiente)
                              VALUES ('2044-01-02','2044-01-01','Ana','Local','Conservar información',FALSE) RETURNING id,folio""")
            cls.record_id,cls.folio=cursor.fetchone()

    def setUp(self):
        self.media=TemporaryDirectory();self.addCleanup(self.media.cleanup)
        self.override=self.settings(MEDIA_ROOT=self.media.name);self.override.enable();self.addCleanup(self.override.disable)
        self.client.force_login(self.admin)
        self.web_url='/admin/apariencia/webappearance/1/change/'

    def colors(self):
        return {**DEFAULT_COLORS,'primary':'#315577','action':'#195084','accent':'#117766'}

    def test_default_identity_matches_existing_assets_and_only_one_web_configuration(self):
        self.assertEqual(WebAppearance.objects.count(),1)
        self.assertTrue(web_branding()['site_logo'].endswith('/ivem.png'))
        self.assertTrue(print_branding(2044)['print_left'].endswith('/ivem-horizontal.png'))
        page=self.client.get(self.web_url)
        self.assertContains(page,'1985 × 617')
        self.assertContains(page,'Vista previa sin guardar')
        self.assertEqual(self.client.get('/admin/apariencia/webappearance/add/').status_code,403)

    def test_preview_validates_without_saving_or_publishing_images(self):
        response=self.client.post(self.web_url,{**self.colors(),'site_logo_upload':svg('site_logo'),'_preview':'1'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'data:image/svg+xml;base64,')
        self.assertEqual(BrandImage.objects.count(),0)
        self.assertEqual(WebAppearance.objects.get(pk=1).primary,DEFAULT_COLORS['primary'])
        self.assertEqual(list(Path(self.media.name).rglob('*.svg')),[])

    def test_saved_identity_changes_web_and_public_asset_is_restricted_svg(self):
        response=self.client.post(self.web_url,{**self.colors(),'site_logo_upload':svg('site_logo'),'_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        config=WebAppearance.objects.get(pk=1)
        self.assertEqual(config.primary,'#315577')
        self.assertEqual(config.updated_by,self.admin)
        asset=config.site_logo
        self.assertEqual(asset.slot,'site_logo')
        self.assertTrue(Path(self.media.name,asset.file.name).exists())
        anonymous=Client()
        response=anonymous.get(asset.public_url)
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'image/svg+xml')
        self.assertIn('sandbox',response['Content-Security-Policy'])
        b''.join(response.streaming_content)
        login=anonymous.get('/')
        self.assertContains(login,reverse('apariencia:theme'))
        css=anonymous.get(reverse('apariencia:theme'))
        self.assertContains(css,'--ivem-primary:#315577')
        self.assertEqual(css['Content-Type'],'text/css; charset=utf-8')

    def test_invalid_upload_and_unreadable_colors_preserve_settings(self):
        response=self.client.post(self.web_url,{**self.colors(),'site_logo_upload':svg('site_logo',width=1),'_save':'Guardar'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(BrandImage.objects.count(),0)
        response=self.client.post(self.web_url,{**DEFAULT_COLORS,'text':'#ffffff','_save':'Guardar'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'4.5:1')
        self.assertEqual(WebAppearance.objects.get(pk=1).text,DEFAULT_COLORS['text'])

    def test_print_profiles_are_per_year_and_preserve_layout_and_record(self):
        response=self.client.post('/admin/apariencia/printidentity/add/',{
            'year':2044,'print_left_upload':svg('print_left'),'print_right_upload':svg('print_right'),'_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        profile=PrintIdentity.objects.get(year=2044)
        response=self.client.get(f'/oficios/imprimir/ucg/2044/{self.record_id}/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.content.decode().count(profile.print_left.public_url),2)
        self.assertEqual(response.content.decode().count(profile.print_right.public_url),2)
        self.assertNotContains(response,'tema.css')
        self.assertContains(response,'Conservar información')
        self.assertTrue(print_branding(2045)['print_left'].endswith('ivem-horizontal.png'))
        with connection.cursor() as cursor:
            cursor.execute('SELECT folio,asunto FROM oficios_ucg_2044 WHERE id=%s',[self.record_id])
            self.assertEqual(cursor.fetchone(),(self.folio,'Conservar información'))

    def test_print_preview_uses_fixed_format_without_automatic_print_or_saving(self):
        response=self.client.post('/admin/apariencia/printidentity/add/',{
            'year':2044,'print_left_upload':svg('print_left'),'_preview':'1'})
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'srcdoc=')
        self.assertNotContains(response,'window.print')
        self.assertEqual(PrintIdentity.objects.count(),0)
        self.assertEqual(BrandImage.objects.count(),0)

    def test_restore_keeps_uploaded_files_and_does_not_touch_print_profiles(self):
        self.client.post(self.web_url,{**self.colors(),'site_logo_upload':svg('site_logo'),'_save':'Guardar'})
        asset=BrandImage.objects.get()
        profile=PrintIdentity.objects.create(year=2044)
        response=self.client.post(self.web_url,{**self.colors(),'restore_defaults':'on','_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        config=WebAppearance.objects.get(pk=1)
        self.assertIsNone(config.site_logo)
        self.assertEqual(config.primary,DEFAULT_COLORS['primary'])
        self.assertTrue(Path(self.media.name,asset.file.name).exists())
        self.assertTrue(PrintIdentity.objects.filter(pk=profile.pk).exists())

    def test_only_authorized_staff_can_change_appearance(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(self.web_url).status_code,403)
        self.assertEqual(self.client.post(self.web_url,self.colors()).status_code,403)
        self.assertEqual(WebAppearance.objects.get(pk=1).primary,DEFAULT_COLORS['primary'])

    def test_database_failure_keeps_old_settings_and_cleans_new_file(self):
        with patch('apariencia.models.WebAppearance.save',side_effect=DatabaseError('Fallo simulado')):
            with self.assertLogs('apariencia.admin',level='ERROR'):
                response=self.client.post(self.web_url,{**self.colors(),'site_logo_upload':svg('site_logo'),'_save':'Guardar'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(BrandImage.objects.count(),0)
        self.assertEqual(WebAppearance.objects.get(pk=1).primary,DEFAULT_COLORS['primary'])
        self.assertEqual(list(Path(self.media.name).rglob('*.svg')),[])

    def test_configuration_forms_require_csrf(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response=client.post(self.web_url,self.colors())
        self.assertEqual(response.status_code,403)
        self.assertEqual(WebAppearance.objects.get(pk=1).primary,DEFAULT_COLORS['primary'])
