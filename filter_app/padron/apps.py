from django.apps import AppConfig


class PadronConfig(AppConfig):
    name = 'padron'

    def ready(self):
        from . import signals  # noqa: F401
