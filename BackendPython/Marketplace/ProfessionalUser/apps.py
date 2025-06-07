from django.apps import AppConfig


class ProfessionaluserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'ProfessionalUser'

    def ready(self):
        import ProfessionalUser.signals