import logging

from cloudinary.exceptions import Error as CloudinaryError
from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver


logger = logging.getLogger(__name__)


class Event(models.Model):
    name = models.CharField(max_length=150)
    slug = models.SlugField(unique=True, db_index=True)
    date = models.DateField()
    location_name = models.CharField(max_length=180, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    welcome_text = models.TextField(blank=True)
    users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="events",
        verbose_name="Usuários com acesso ao painel",
        help_text="Usuários (noivos/casal) com acesso ao painel deste evento e moderação das fotos.",
    )

    def __str__(self):
        return self.name


class Photo(models.Model):
    class Category(models.TextChoices):
        CEREMONY = "ceremony", "Cerimônia"
        PARTY = "party", "Festa"
        DANCE_FLOOR = "dance-floor", "Pista"
        FRIENDS = "friends", "Amigos"
        FAMILY = "family", "Família"

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="photos", db_index=True)
    image = models.ImageField(upload_to="wedding/%Y/%m/")
    guest_name = models.CharField(max_length=70, blank=True)
    caption = models.CharField(max_length=220, blank=True)
    category = models.CharField(max_length=20, choices=Category.choices, blank=True, db_index=True)
    is_approved = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["event", "is_approved", "-created_at", "-id"], name="photo_gallery_idx")
        ]

    def __str__(self):
        return f'{self.event}: {self.guest_name or "Convidado"}'

    @property
    def reacted_emojis(self):
        return [reaction.emoji for reaction in getattr(self, "current_session_reactions", [])]


class Reaction(models.Model):
    class Emoji(models.TextChoices):
        HEART = "heart", "❤️"
        LOVE = "love", "😍"
        TOUCHED = "touched", "🥹"
        SPARKLE = "sparkle", "✨"

    photo = models.ForeignKey(Photo, on_delete=models.CASCADE, related_name="reactions")
    session_key = models.CharField(max_length=64)
    emoji = models.CharField(max_length=10, choices=Emoji.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["photo", "session_key", "emoji"], name="unique_session_reaction")]


class UploadAttempt(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="upload_attempts")
    session_hash = models.CharField(max_length=64, db_index=True)
    ip_hash = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=["event", "session_hash", "-created_at"], name="upload_session_idx"),
            models.Index(fields=["event", "ip_hash", "-created_at"], name="upload_ip_idx"),
        ]


@receiver(post_delete, sender=Photo)
def delete_photo_file_after_commit(sender, instance, **kwargs):
    """Remove the stored image after the database deletion is committed."""
    if not instance.image or not instance.image.name:
        return
    storage = instance.image.storage
    name = instance.image.name

    def delete_file():
        try:
            storage.delete(name)
        except (OSError, CloudinaryError):
            logger.warning("Não foi possível remover um arquivo de foto do storage.")

    transaction.on_commit(delete_file)
