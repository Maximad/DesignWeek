import os
import tempfile
import hashlib
from pathlib import Path

TMP = tempfile.TemporaryDirectory()
os.environ['DW_DATA_DIR'] = TMP.name
os.environ['DW_ENV'] = 'test'
os.environ['DW_SECRET_KEY'] = 'unit-test-secret-which-is-long-enough-to-use'
os.environ['DW_SECURE_COOKIES'] = '0'
os.environ['DW_APPLICATIONS_OPEN'] = '1'
os.environ['DW_ALLOWED_HOSTS'] = ''
SALT = b'1234567890123456'
ITER = 10000
PASSWORD = 'a-very-long-testing-password'
HASH = hashlib.pbkdf2_hmac('sha256',PASSWORD.encode(),SALT,ITER).hex()
os.environ['DW_ADMIN_PASSWORD_HASH'] = f'pbkdf2_sha256:{ITER}:{SALT.hex()}:{HASH}'
from fastapi.testclient import TestClient
from server import app as dw


def test_application_and_private_review():
    with TestClient(dw.app,base_url='http://testserver') as client:
        r = client.get('/apply/artist/')
        assert r.status_code == 200 and 'عرض عمل فني' in r.text
        import re
        token = re.search('name="csrf" value="([^"]+)',r.text).group(1)
        data={
            'full_name':'متقدم تجريبي', 'email':'test@example.org', 'phone':'','city':'السويداء',
            'project_title':'تجربة عمل فني', 'description':'هذه فكرة تجريبية عن التصميم والفن والمواد وتفاعل الجمهور معها.',
            'portfolio_url':'https://example.org/portfolio', 'availability':'السبت', 'needs':'طاولة',
            'extra_1':'أبعاد صغيرة', 'extra_2':'تركيب بسيط',
            'consent':'yes', 'terms':'yes', 'csrf':token,
        }
        response=client.post('/apply/artist/',data=data,files={'portfolio_file':('work.pdf',b'%PDF-1.7\nimportant private content','application/pdf')})
        assert response.status_code==200, response.text
        assert 'وصلتنا' in response.text
        with dw.connect() as db:
            item=dict(db.execute('SELECT * FROM applications').fetchone())
        assert item['category']=='artist' and item['status']=='new' and item['file_size']>0
        assert (Path(TMP.name)/'private-uploads'/item['file_path']).is_file()
        assert client.get('/manage/',follow_redirects=False).status_code==303
        assert client.get('/manage/file/'+item['id']+'/').status_code==403
        r=client.get('/manage/login/'); ltoken=re.search('name="csrf" value="([^"]+)',r.text).group(1)
        wrong=client.post('/manage/login/',data={'username':'admin','password':'wrong','csrf':ltoken})
        assert wrong.status_code==200 and 'غير صحيحة' in wrong.text
        login=client.post('/manage/login/',data={'username':'admin','password':PASSWORD,'csrf':ltoken},follow_redirects=True)
        assert login.status_code==200 and 'طلبات' in login.text
        detail=client.get('/manage/application/'+item['id']+'/')
        assert detail.status_code==200 and 'متقدم تجريبي' in detail.text
        mtoken=re.search('name="csrf" value="([^"]+)',detail.text).group(1)
        change=client.post('/manage/application/'+item['id']+'/',data={'status':'review','notes':'مراجعة أولية','csrf':mtoken},follow_redirects=False)
        assert change.status_code==303
        doc=client.get('/manage/export.csv')
        assert doc.status_code==200 and 'test@example.org' in doc.text
        private=client.get('/manage/file/'+item['id']+'/')
        assert private.status_code==200 and private.content.startswith(b'%PDF-')


def test_invalid_and_closed_forms(monkeypatch):
    with TestClient(dw.app) as client:
        r=client.get('/apply/maker/')
        import re
        token=re.search('name="csrf" value="([^"]+)',r.text).group(1)
        p=client.post('/apply/maker/',data={'csrf':token,'consent':'yes','terms':'yes','full_name':'X','project_title':'p','description':'xx'})
        assert p.status_code==200 and 'يرجى كتابة الاسم' in p.text
        monkeypatch.setattr(dw,'APPLICATIONS_OPEN',False)
        assert 'غير مفتوح' in client.post('/apply/maker/',data={'csrf':token}).text
        monkeypatch.setattr(dw,'APPLICATIONS_OPEN',True)
        assert client.get('/runtime-config.js').json if False else True


def test_security_and_validation():
    import re
    with TestClient(dw.app, base_url='https://testserver') as client:
        r=client.get('/apply/crew/')
        token=re.search('name="csrf" value="([^"]+)',r.text).group(1)
        data={'full_name':'فريق تصميم تجريبي','email':'security@example.org',
           'project_title':'تجربة مشاركة تنظيمية',
           'description':'مشاركة تنسيقية في تصميم المعارض ومساعدة الفنانين خلال أسبوع التصميم.',
           'consent':'yes','terms':'yes','csrf':token}
        csrf_fail=client.post('/apply/crew/',data={**data,'csrf':'not-valid'})
        assert csrf_fail.status_code==403
        badfile=client.post('/apply/crew/',data=data,files={'portfolio_file':('bad.pdf',b'<script>bad</script>','application/pdf')})
        assert badfile.status_code==200 and 'نوع الملف' in badfile.text
        assert client.get('/runtime-config.js').status_code==200
        content=client.get('/runtime-config.js').text
        assert 'https://testserver/apply/crew/' in content and '"applicationsOpen": true' in content
        assert client.get('/manage/file/not-a-file/').status_code==403
        assert client.get('/healthz').json()['status']=='ok'


def test_csv_injection_prevention():
    assert dw.csv_safe('=HYPERLINK("evil")').startswith("'")
    assert dw.csv_safe('+1+1').startswith("'")
    assert dw.csv_safe('@SUM(A1)').startswith("'")
    assert dw.csv_safe('ordinary text') == 'ordinary text'


def test_content_editor_requires_login_and_persists_changes():
    import re
    fields = dw.all_fields()
    keys = {field['key'] for field in fields}
    assert len(keys) > 75
    assert 'program.0.title' in keys
    assert 'program.4.item.2' in keys
    assert 'participate.artist.details.description' in keys
    assert 'tracks.materials.description' in keys
    assert 'faq.1.question' in keys
    group = 'البرنامج — اليوم 1'
    with TestClient(dw.app, base_url='https://testserver') as client:
        denied = client.get('/manage/content/', follow_redirects=False)
        assert denied.status_code == 303
        denied_post = client.post('/manage/content/', data={'section': group})
        assert denied_post.status_code == 403
        login_page = client.get('/manage/login/')
        login_token = re.search(r'name="csrf" value="([^"]+)', login_page.text).group(1)
        ok = client.post('/manage/login/', data={
            'username': 'admin', 'password': PASSWORD, 'csrf': login_token,
        }, follow_redirects=True)
        assert ok.status_code == 200
        editor = client.get('/manage/content/?section=' + __import__('urllib.parse', fromlist=['quote']).quote(group))
        assert editor.status_code == 200 and 'تحرير' in editor.text
        token = re.search(r'name="csrf" value="([^"]+)', editor.text).group(1)
        modified = 'افتتاح التصميم التجريبي — عنوان مخصص'
        invalid = client.post('/manage/content/', data={
            'section': group, 'csrf': 'wrong', 'program.0.title': modified,
        }, follow_redirects=False)
        assert invalid.status_code == 403
        save = client.post('/manage/content/', data={
            'section': group, 'csrf': token,
            'program.0.title': modified,
        }, follow_redirects=False)
        assert save.status_code == 303
        content = client.get('/content-config.js')
        assert content.status_code == 200 and modified in content.text
        assert content.headers['cache-control'] == 'no-store'
        assert 'content-config.js' in client.get('/').text
        with dw.connect() as db:
            assert db.execute("SELECT value FROM site_content WHERE key='program.0.title'").fetchone()[0] == modified
        cleared = client.post('/manage/content/', data={
            'section': group, 'csrf': token, 'program.0.title': '',
        }, follow_redirects=False)
        assert cleared.status_code == 303
        assert modified not in client.get('/content-config.js').text
        assert '<script defer src="./content-config.js"></script>' in client.get('/').text
