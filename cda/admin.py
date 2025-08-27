from django.contrib import admin
from .models import UserProfile, Placa, Foto

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role']
    list_filter = ['role']

@admin.register(Placa)
class PlacaAdmin(admin.ModelAdmin):
    list_display = ['numero_placa', 'creado_por', 'fecha_creacion']
    list_filter = ['fecha_creacion']

@admin.register(Foto)
class FotoAdmin(admin.ModelAdmin):
    list_display = ['placa', 'creado_por', 'fecha_creacion']
    list_filter = ['fecha_creacion']
