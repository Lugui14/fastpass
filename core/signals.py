from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Usuario, Conta

@receiver(post_save, sender=Usuario)
def criar_conta_usuario(sender, instance, created, **kwargs):
    if created:
        Conta.objects.create(usuario=instance)
