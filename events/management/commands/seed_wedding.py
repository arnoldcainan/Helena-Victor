from datetime import date
from django.core.management.base import BaseCommand
from events.models import Event
class Command(BaseCommand):
    help = 'Cria o evento Helena & Victor para desenvolvimento.'
    def handle(self, *args, **kwargs):
        event, created = Event.objects.get_or_create(slug='helena-e-victor', defaults={'name':'Helena & Victor','date':date(2026,10,3),'welcome_text':'Hoje, cada olhar e cada sorriso fazem parte da nossa história.'})
        self.stdout.write(self.style.SUCCESS('Evento criado.' if created else 'Evento já existe.'))
