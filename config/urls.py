from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from events.views import error_404, error_500

urlpatterns = [path('admin/', admin.site.urls), path('', include('events.urls'))]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404, handler500 = error_404, error_500
