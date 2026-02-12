from django import forms
from .models import Placa, Foto
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from django.contrib.auth.forms import PasswordChangeForm, SetPasswordForm
from django.utils.translation import gettext_lazy as _

# 🚗 Formulario para registrar una nueva placa
class PlacaForm(forms.ModelForm):
    class Meta:
        model = Placa
        fields = ['numero_placa']
        labels = {
            'numero_placa': 'Número de placa',
        }
        widgets = {
            'numero_placa': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ingrese número de placa'}),
        }

# 🖼️ Formulario para subir una fotografía con comentario
class FotoForm(forms.ModelForm):
    class Meta:
        model = Foto
        fields = ['imagen', 'comentario']
        widgets = {
            'comentario': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describa lo que muestra la foto',
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['imagen'].widget.attrs.update({
            'class': 'form-control',
            'accept': 'image/*',
            'capture': 'camera'  # Esto permite usar la cámara en dispositivos móviles
        })

# 👤 Formulario para crear usuarios (base)
class BaseCrearUsuarioForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre de usuario'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
        self.fields['password2'].widget = forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar contraseña'})
        
        # ✅ ELIMINAR VALIDADORES POR DEFECTO DE DJANGO
        self.fields['username'].validators = []
        self.fields['username'].help_text = 'Requerido. 150 caracteres o menos. Letras, números y caracteres: - _ . / @ +'
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            import re
            if not re.match(r'^[a-zA-Z0-9\-_./@+]+$', username):
                raise forms.ValidationError('El nombre de usuario solo puede contener letras, números y los caracteres: - _ . / @ +')
            if User.objects.filter(username__iexact=username).exists():
                raise forms.ValidationError('Este nombre de usuario ya está en uso.')
        return username

# 👤 Formulario para Ingenieros (solo Inspector e Ingeniero)
class CrearUsuarioFormIngeniero(BaseCrearUsuarioForm):
    ROLE_CHOICES = [
        ('inspector', 'Inspector'),
        ('ingeniero', 'Ingeniero'),
    ]
    grupo = forms.ChoiceField(choices=ROLE_CHOICES, label='Rol', widget=forms.Select(attrs={'class': 'form-control'}))

# 👤 Formulario para Superusuarios (todos los roles)
class CrearUsuarioFormSuperusuario(BaseCrearUsuarioForm):
    ROLE_CHOICES = [
        ('inspector', 'Inspector'),
        ('ingeniero', 'Ingeniero'),
        ('superusuario', 'Super Usuario'),
    ]
    grupo = forms.ChoiceField(choices=ROLE_CHOICES, label='Rol', widget=forms.Select(attrs={'class': 'form-control'}))

# 🔑 Formulario para cambiar contraseña de usuarios
class CambiarContrasenaForm(PasswordChangeForm):
    class Meta:
        model = User
        fields = ['old_password', 'new_password1', 'new_password2']
        widgets = {
            'old_password': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña actual'}),
            'new_password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Nueva contraseña'}),
            'new_password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmar nueva contraseña'}),
        }


class CambiarContrasenaForm(SetPasswordForm):
    """
    Formulario personalizado para cambiar contraseña con mensajes en español
    """
    new_password1 = forms.CharField(
        label=_("Nueva Contraseña"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ingrese nueva contraseña',
            'autocomplete': 'new-password'
        }),
        strip=False,
        help_text=_(
            "Su contraseña debe contener al menos 8 caracteres.<br>"
            "No puede ser similar a su información personal.<br>"
            "No puede ser una contraseña comúnmente utilizada.<br>"
            "No puede ser completamente numérica."
        )
    )
    
    new_password2 = forms.CharField(
        label=_("Confirmar Contraseña"),
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirme la nueva contraseña',
            'autocomplete': 'new-password'
        }),
        strip=False,
        help_text=_("Ingrese la misma contraseña para verificación.")
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar mensajes de error
        self.fields['new_password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Ingrese nueva contraseña'
        })
        self.fields['new_password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirme la nueva contraseña'
        })
