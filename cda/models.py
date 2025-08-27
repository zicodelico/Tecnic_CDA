from django.db import models
from django.contrib.auth.models import User

# Eliminar el modelo CustomUser y usar perfiles en su lugar
class UserProfile(models.Model):
    ROLES = (
        ('inspector', 'Inspector'),
        ('ingeniero', 'Ingeniero'),
        ('superusuario', 'Super Usuario'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default='inspector')
    
    def __str__(self):
        return f"{self.user.username} ({self.role})"

class Placa(models.Model):
    numero_placa = models.CharField(max_length=20, unique=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.numero_placa

class Foto(models.Model):
    placa = models.ForeignKey(Placa, related_name='fotos', on_delete=models.CASCADE)
    imagen = models.ImageField(upload_to='fotos/')
    comentario = models.TextField()
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    creado_por = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return f"Foto {self.id} para placa {self.placa.numero_placa}"


