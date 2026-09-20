from django.contrib import admin

from .models import Event, Photo, Reaction, UploadAttempt


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    list_display = ("name", "date", "slug")


@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "event", "guest_name", "category", "caption", "is_approved", "created_at")
    list_filter = ("event", "category", "is_approved", "created_at")
    search_fields = ("guest_name", "caption")
    list_editable = ("is_approved",)


@admin.register(Reaction)
class ReactionAdmin(admin.ModelAdmin):
    list_display = ("photo", "emoji", "created_at")


@admin.register(UploadAttempt)
class UploadAttemptAdmin(admin.ModelAdmin):
    list_display = ("event", "created_at")
    list_filter = ("event", "created_at")
    readonly_fields = ("event", "session_hash", "ip_hash", "created_at")
