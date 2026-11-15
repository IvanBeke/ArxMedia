from io import BytesIO

from django.core.files.base import ContentFile
from django.utils.translation import gettext as _
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import serializers

AVATAR_SIZE = 512
MAX_AVATAR_BYTES = 5 * 1024 * 1024
MIN_AVATAR_SIDE = 64
MAX_AVATAR_SIDE = 4096
ALLOWED_AVATAR_FORMATS = {'JPEG', 'PNG', 'WEBP'}


def process_avatar(upload) -> ContentFile:
    """Validate an uploaded image and re-encode it as a square WebP.

    Re-encoding drops EXIF/GPS metadata and any non-image payload in the file.
    """
    if upload.size > MAX_AVATAR_BYTES:
        raise serializers.ValidationError(
            _('Image must be %(size)s MB or smaller.') % {'size': MAX_AVATAR_BYTES // (1024 * 1024)}
        )
    try:
        with Image.open(upload) as image:
            if image.format not in ALLOWED_AVATAR_FORMATS:
                raise serializers.ValidationError(_('Image must be a JPEG, PNG or WebP file.'))
            if min(image.size) < MIN_AVATAR_SIDE or max(image.size) > MAX_AVATAR_SIDE:
                raise serializers.ValidationError(
                    _('Image sides must be between %(min)s and %(max)s pixels.')
                    % {'min': MIN_AVATAR_SIDE, 'max': MAX_AVATAR_SIDE}
                )
            image.load()
            square = ImageOps.fit(ImageOps.exif_transpose(image), (AVATAR_SIZE, AVATAR_SIZE))
            buffer = BytesIO()
            square.convert('RGBA' if square.has_transparency_data else 'RGB').save(buffer, 'WEBP', quality=88)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise serializers.ValidationError(_('Could not read the image.')) from exc
    return ContentFile(buffer.getvalue())
