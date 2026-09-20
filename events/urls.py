from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("e/<slug:slug>/", views.event_detail, name="event-detail"),
    path("e/<slug:slug>/upload/", views.upload_photo, name="upload-photo"),
    path("e/<slug:slug>/photos/", views.photo_page, name="photo-page"),
    path("e/<slug:slug>/updates/", views.photo_updates, name="photo-updates"),
    path("e/<slug:slug>/new/", views.photo_newer, name="photo-newer"),
    path("e/<slug:slug>/share/", views.share_text, name="share-text"),
    path("photos/<int:pk>/", views.photo_detail, name="photo-detail"),
    path("photos/<int:pk>/react/", views.react, name="react"),
    path("casal/", views.couple_dashboard, name="couple-dashboard"),
    path("casal/photos/<int:pk>/download/", views.download_photo, name="download-photo"),
    path("casal/events/<int:pk>/download/", views.download_album, name="download-album"),
    path("staff/event/<int:pk>/qrcode/", views.qrcode_page, name="qrcode"),
]
