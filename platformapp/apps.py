from django.apps import AppConfig


class PlatformappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "platformapp"

    def ready(self) -> None:
        from src.service.predictor import warm_classical_cache

        warm_classical_cache()
