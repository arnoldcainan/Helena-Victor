import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.contrib.auth import get_user_model
from events.models import Event


def main():
    User = get_user_model()
    username = os.getenv("DJANGO_SUPERUSER_USERNAME", "admin")
    email = os.getenv("DJANGO_SUPERUSER_EMAIL", "admin@example.com")
    password = os.getenv("DJANGO_SUPERUSER_PASSWORD")

    if not password:
        print("[create_admin] AVISO: DJANGO_SUPERUSER_PASSWORD não foi informada nas variáveis de ambiente. Pulando criação.")
        return

    user = User.objects.filter(username=username).first()
    if not user:
        user = User.objects.create_superuser(username=username, email=email, password=password)
        print(f"[create_admin] Superusuário '{username}' criado com sucesso.")
    else:
        changed = False
        if not user.is_superuser or not user.is_staff:
            user.is_superuser = True
            user.is_staff = True
            changed = True
        if changed:
            user.save()
        print(f"[create_admin] Superusuário '{username}' já existe e está ativo.")

    event = Event.objects.first()
    if event and not event.users.filter(pk=user.pk).exists():
        event.users.add(user)
        print(f"[create_admin] Usuário '{username}' associado ao evento '{event.name}'.")


if __name__ == "__main__":
    main()
