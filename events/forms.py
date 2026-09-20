from PIL import Image, UnidentifiedImageError
from django import forms
from django.conf import settings

from .models import Photo
from .services import sanitize_uploaded_image


class PhotoForm(forms.ModelForm):
    image = forms.ImageField(
        widget=forms.FileInput(attrs={"accept": "image/*"}),
        error_messages={
            "required": "Escolha uma foto para continuar.",
            "invalid_image": "Não conseguimos processar essa imagem. Tente outra foto.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        uploaded = self.files.get("image")
        self.declared_image_content_type = getattr(uploaded, "content_type", "")

    class Meta:
        model = Photo
        fields = ["guest_name", "caption", "category", "image"]
        widgets = {
            "guest_name": forms.TextInput(attrs={"placeholder": "Seu nome (opcional)"}),
            "caption": forms.TextInput(attrs={"placeholder": "Uma breve legenda (opcional)"}),
            "category": forms.Select(),
        }

    def clean_image(self):
        uploaded = self.cleaned_data.get("image")
        if not uploaded or uploaded.size == 0:
            raise forms.ValidationError("Escolha uma foto para continuar.")
        if uploaded.size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise forms.ValidationError(f"A foto deve ter no máximo {settings.MAX_UPLOAD_SIZE_MB} MB.")

        try:
            uploaded.seek(0)
            with Image.open(uploaded) as image:
                detected_format = (image.format or "").upper()
                width, height = image.size
                if detected_format not in settings.ALLOWED_IMAGE_FORMATS:
                    if detected_format in {"HEIC", "HEIF"}:
                        raise forms.ValidationError("Fotos HEIC/HEIF ainda não são aceitas. No iPhone, escolha uma foto convertida para JPEG.")
                    raise forms.ValidationError("Formato não aceito. Envie uma foto JPEG, PNG ou WebP.")
                if width <= 0 or height <= 0 or width * height > settings.MAX_IMAGE_PIXELS:
                    raise forms.ValidationError("A resolução dessa imagem é muito alta. Escolha uma foto menor.")
                image.verify()
        except forms.ValidationError:
            raise
        except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError):
            raise forms.ValidationError("Não conseguimos processar essa imagem. Tente outra foto.")

        if self.declared_image_content_type not in settings.ALLOWED_IMAGE_MIME_TYPES.get(detected_format, set()):
            raise forms.ValidationError("O tipo do arquivo não corresponde ao conteúdo da imagem.")
        try:
            return sanitize_uploaded_image(uploaded, detected_format)
        except (Image.DecompressionBombError, OSError, ValueError):
            raise forms.ValidationError("Não conseguimos processar essa imagem. Tente outra foto.")
