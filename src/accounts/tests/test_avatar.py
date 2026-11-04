import re
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.avatars import AVATAR_SIZE, MAX_AVATAR_BYTES

pytestmark = pytest.mark.django_db

URL = '/api/auth/me/avatar/'


def make_image(size=(200, 200), fmt='PNG', mode='RGB', **save_kwargs):
    buffer = BytesIO()
    Image.new(mode, size, (200, 30, 30) if mode == 'RGB' else (200, 30, 30, 128)).save(buffer, fmt, **save_kwargs)
    return buffer.getvalue()


def upload(client, content, name='me.png', content_type='image/png'):
    return client.put(URL, {'avatar': SimpleUploadedFile(name, content, content_type=content_type)}, format='multipart')


class AvatarUploadTests:
    def test_upload_stores_square_webp_and_returns_relative_url(self, auth_client, user, media_root):
        response = upload(auth_client, make_image((300, 200)))

        assert response.status_code == 200
        user.refresh_from_db()
        assert response.data['avatar'] == user.avatar.url
        assert re.fullmatch(r'/media/avatars/testuser_[A-Za-z0-9]{8}\.webp', response.data['avatar'])
        with Image.open(user.avatar.path) as stored:
            assert stored.format == 'WEBP'
            assert stored.size == (AVATAR_SIZE, AVATAR_SIZE)

    def test_filename_is_sanitised_for_unusual_usernames(self, auth_client, user, api_client):
        user.username = 'jo hn@x+y'
        user.save()

        response = upload(auth_client, make_image())

        assert re.fullmatch(r'/media/avatars/jo_hnxy_[A-Za-z0-9]{8}\.webp', response.data['avatar'])
        assert api_client.get(response.data['avatar']).status_code == 200

    def test_upload_strips_exif_metadata(self, auth_client, user):
        exif = Image.Exif()
        exif[0x010F] = 'SecretCamera'
        upload(auth_client, make_image(fmt='JPEG', exif=exif.tobytes()), 'me.jpg', 'image/jpeg')

        user.refresh_from_db()
        with Image.open(user.avatar.path) as stored:
            assert not stored.getexif()

    def test_upload_keeps_transparency(self, auth_client, user):
        upload(auth_client, make_image(mode='RGBA'))

        user.refresh_from_db()
        with Image.open(user.avatar.path) as stored:
            assert stored.mode == 'RGBA'

    def test_replacing_deletes_previous_file(self, auth_client, user):
        upload(auth_client, make_image())
        user.refresh_from_db()
        first = user.avatar.path

        upload(auth_client, make_image())
        user.refresh_from_db()

        assert user.avatar.path != first
        assert not Path(first).exists()

    @pytest.mark.parametrize(
        ('content', 'name'),
        [
            (b'not an image', 'me.png'),
            (b'<svg xmlns="http://www.w3.org/2000/svg"/>', 'me.svg'),
            (make_image(fmt='GIF'), 'me.gif'),
            (make_image((32, 32)), 'tiny.png'),
            (make_image((5000, 100)), 'wide.png'),
        ],
    )
    def test_rejects_invalid_images(self, auth_client, user, content, name):
        response = upload(auth_client, content, name)

        assert response.status_code == 400
        assert 'avatar' in response.data
        user.refresh_from_db()
        assert not user.avatar

    def test_rejects_oversized_upload(self, auth_client, user):
        response = upload(auth_client, b'0' * (MAX_AVATAR_BYTES + 1))

        assert response.status_code == 400
        assert 'MB' in str(response.data['avatar'][0])

    def test_rejects_missing_file(self, auth_client):
        assert auth_client.put(URL, {}, format='multipart').status_code == 400

    def test_rejects_json_body(self, auth_client):
        assert auth_client.put(URL, {'avatar': 'x'}, format='json').status_code == 415

    def test_requires_authentication(self, api_client):
        assert upload(api_client, make_image()).status_code == 401
        assert api_client.delete(URL).status_code == 401

    def test_upload_is_throttled(self, auth_client):
        rates = {**django_settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'], 'avatar_upload': '1/hour'}
        with patch('rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES', rates):
            assert upload(auth_client, make_image()).status_code == 200
            assert upload(auth_client, make_image()).status_code == 429


class AvatarRemovalTests:
    def test_delete_removes_file_and_clears_field(self, auth_client, user):
        upload(auth_client, make_image())
        user.refresh_from_db()
        path = user.avatar.path

        response = auth_client.delete(URL)

        assert response.status_code == 200
        assert response.data['avatar'] is None
        user.refresh_from_db()
        assert not user.avatar
        assert not Path(path).exists()

    def test_delete_without_avatar_is_a_noop(self, auth_client):
        response = auth_client.delete(URL)

        assert response.status_code == 200
        assert response.data['avatar'] is None


class AvatarExposureTests:
    def test_patch_me_ignores_avatar(self, auth_client, user):
        response = auth_client.patch('/api/auth/me/', {'avatar': 'avatars/x_abc12345.webp'}, format='json')

        assert response.status_code == 200
        user.refresh_from_db()
        assert not user.avatar

    def test_avatar_appears_in_profile_and_user_cards(self, auth_client, user, user2):
        auth_client.force_authenticate(user=user2)
        upload(auth_client, make_image())
        user2.refresh_from_db()
        auth_client.force_authenticate(user=user)

        assert auth_client.get(f'/api/auth/users/{user2.username}/').data['avatar'] == user2.avatar.url
        assert auth_client.get('/api/auth/users/search/', {'q': user2.username}).data[0]['avatar'] == user2.avatar.url

    def test_avatar_files_are_publicly_served_with_long_cache(self, auth_client, user, api_client):
        upload(auth_client, make_image())
        user.refresh_from_db()

        response = api_client.get(user.avatar.url)

        assert response.status_code == 200
        assert response['Content-Type'] == 'image/webp'
        assert 'immutable' in response['Cache-Control']

    def test_other_media_stays_private(self, api_client, media_root):
        private = media_root / 'imports' / 'abc'
        private.mkdir(parents=True)
        (private / 'data.csv').write_text('secret')

        assert api_client.get('/media/imports/abc/data.csv').status_code == 404
        assert api_client.get('/media/avatars/../imports/abc/data.csv').status_code in {400, 404}
