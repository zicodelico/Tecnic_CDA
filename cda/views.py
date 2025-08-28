from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse
from .models import Placa, Foto, UserProfile
from .forms import PlacaForm, FotoForm, CambiarContrasenaForm, CrearUsuarioFormIngeniero, CrearUsuarioFormSuperusuario
from django.template.loader import render_to_string
from django.contrib import messages
from django.utils import timezone
import os
import pdfkit

# 🔐 Funciones de rol
def is_inspector(user):
    try:
        return user.userprofile.role == 'inspector'
    except UserProfile.DoesNotExist:
        return False

def is_ingeniero(user):
    try:
        return user.userprofile.role == 'ingeniero'
    except UserProfile.DoesNotExist:
        return False

def is_superusuario(user):
    try:
        return user.userprofile.role == 'superusuario'
    except UserProfile.DoesNotExist:
        return user.is_superuser

# 🏠 Vista principal
@login_required
def home(request):
    return render(request, 'cda/home.html')

# 👤 ADMINISTRACIÓN DE USUARIOS
@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def lista_usuarios_admin(request):
    if is_superusuario(request.user):
        usuarios = User.objects.all().select_related('userprofile')
    else:
        # Ingenieros solo ven inspectores e ingenieros
        usuarios = User.objects.filter(
            userprofile__role__in=['inspector', 'ingeniero']
        ).select_related('userprofile')
    
    return render(request, 'cda/lista_usuarios.html', {'usuarios': usuarios})

@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def crear_usuario(request):
    if is_superusuario(request.user):
        FormClass = CrearUsuarioFormSuperusuario
    else:
        FormClass = CrearUsuarioFormIngeniero
    
    if request.method == 'POST':
        form = FormClass(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Crear perfil de usuario con el rol seleccionado
            grupo = form.cleaned_data['grupo']
            UserProfile.objects.create(user=user, role=grupo)
            
            messages.success(request, f'Usuario {user.username} creado correctamente como {grupo}.')
            return redirect('cda:lista_usuarios_admin')
    else:
        form = FormClass()
    
    return render(request, 'cda/crear_usuario.html', {'form': form})

@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def editar_usuario(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    
    if not hasattr(usuario, 'userprofile'):
        UserProfile.objects.create(user=usuario, role='inspector')
    
    user_profile = usuario.userprofile
    
    if is_ingeniero(request.user) and user_profile.role == 'superusuario':
        messages.error(request, 'No tienes permisos para editar superusuarios.')
        return redirect('cda:lista_usuarios_admin')
    
    if request.method == 'POST':
        # USAR NUESTRO FORMULARIO PERSONALIZADO
        form = CambiarContrasenaForm(user=usuario, data=request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'✅ Contraseña de {usuario.username} actualizada correctamente.')
            return redirect('cda:lista_usuarios_admin')
        else:
            messages.error(request, '❌ Error al cambiar la contraseña. Verifique los datos.')
    else:
        form = CambiarContrasenaForm(user=usuario)
    
    return render(request, 'cda/editar_usuario.html', {
        'form': form,
        'usuario': usuario
    })

@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def toggle_usuario(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    
    # Verificar si el usuario tiene perfil
    if not hasattr(usuario, 'userprofile'):
        UserProfile.objects.create(user=usuario, role='inspector')
    
    user_profile = usuario.userprofile
    
    # Verificar permisos
    if is_ingeniero(request.user) and user_profile.role == 'superusuario':
        messages.error(request, 'No tienes permisos para modificar superusuarios.')
        return redirect('cda:lista_usuarios_admin')
    
    usuario.is_active = not usuario.is_active
    usuario.save()
    
    estado = "activado" if usuario.is_active else "desactivado"
    messages.success(request, f'Usuario {usuario.username} {estado} correctamente.')
    return redirect('cda:lista_usuarios_admin')

# 🔑 Cambiar contraseña del usuario actual
@login_required
def cambiar_contrasena(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Contraseña cambiada correctamente.')
            return redirect('cda:home')
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, 'cda/cambiar_contrasena.html', {'form': form})

# 🚗 GESTIÓN DE PLACAS
@login_required
def lista_placas(request):
    placas = Placa.objects.all().order_by('-fecha_creacion')
    return render(request, 'cda/lista_placas.html', {'placas': placas})

@login_required
@user_passes_test(lambda u: is_inspector(u) or is_ingeniero(u) or is_superusuario(u))
def crear_placa(request):
    if request.method == 'POST':
        form = PlacaForm(request.POST)
        if form.is_valid():
            placa = form.save(commit=False)
            placa.creado_por = request.user
            placa.save()
            messages.success(request, 'Placa creada correctamente.')
            return redirect('cda:lista_placas')
    else:
        form = PlacaForm()
    return render(request, 'cda/crear_placa.html', {'form': form})

# 🖼️ AGREGAR FOTOS
@login_required
def agregar_fotos(request, placa_id):
    placa = get_object_or_404(Placa, id=placa_id)
    
    if request.method == 'POST' and 'photo_data' in request.POST:
        # PROCESAR FOTO DE CÁMARA
        photo_data = request.POST['photo_data']
        comentario = request.POST.get('comentario', 'Foto tomada con cámara')
        
        try:
            # Extraer datos base64
            if 'base64,' in photo_data:
                image_data = photo_data.split('base64,')[1]
            else:
                image_data = photo_data
                
            # Decodificar
            from django.core.files.base import ContentFile
            from base64 import b64decode
            
            decoded_image = b64decode(image_data)
            
            # Crear nombre de archivo
            filename = f"camara_{placa.id}_{timezone.now().strftime('%H%M%S')}.jpg"
            
            # Crear objeto Foto
            foto = Foto(
                placa=placa,
                comentario=comentario,
                creado_por=request.user
            )
            
            # Guardar imagen
            foto.imagen.save(filename, ContentFile(decoded_image), save=True)
            
            messages.success(request, '✅ Foto guardada correctamente!')
            return redirect('cda:agregar_fotos', placa_id=placa.id)
            
        except Exception as e:
            messages.error(request, f'❌ Error: {str(e)}')
            return redirect('cda:agregar_fotos', placa_id=placa.id)
    
    # MOSTRAR TEMPLATE
    fotos = Foto.objects.filter(placa=placa)
    return render(request, 'cda/agregar_fotos.html', {
        'placa': placa, 
        'fotos': fotos
    })



# 📄 GENERAR PDF CON VERIFICACIÓN DE IMÁGENES
@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def generar_pdf(request, placa_id):
    placa = get_object_or_404(Placa, id=placa_id)
    fotos = Foto.objects.filter(placa=placa)
    
    # Verificar que todas las imágenes existan físicamente
    for foto in fotos:
        if not os.path.exists(foto.imagen.path):
            messages.error(request, f'Error: La imagen {foto.imagen.name} no existe en el servidor.')
            return redirect('cda:agregar_fotos', placa_id=placa_id)
    
    try:
        html = render_to_string('cda/placa_pdf.html', {
            'placa': placa, 
            'fotos': fotos,
            'request': request
        })
        
        
            
    except TemplateDoesNotExist:
        messages.error(request, 'Error: Plantilla no encontrada.')
        return redirect('cda:agregar_fotos', placa_id=placa_id)
    
    try:
        # 🚨 CAMBIA ESTA LÍNEA - Ruta para PythonAnywhere (Linux)
        wkhtmltopdf_path = '/usr/bin/wkhtmltopdf'  # ← Ruta correcta para PythonAnywhere
        
        # Verificar que existe (opcional, pero buena práctica)
        if not os.path.exists(wkhtmltopdf_path):
            messages.error(request, 'Error: wkhtmltopdf no está instalado correctamente.')
            return redirect('cda:agregar_fotos', placa_id=placa_id)
        
        config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
        
        options = {
            'page-size': 'A4',
            'margin-top': '15mm',
            'margin-right': '15mm',
            'margin-bottom': '15mm',
            'margin-left': '15mm',
            'encoding': 'UTF-8',
            'enable-local-file-access': '',
            'quiet': '',
        }
        
        pdf = pdfkit.from_string(html, False, configuration=config, options=options)
        
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"reporte_placa_{placa.numero_placa}.pdf"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        return response
        
    except Exception as e:
        messages.error(request, f'Error al generar PDF. Contacte al administrador. Detalle: {str(e)}')
        return redirect('cda:agregar_fotos', placa_id=placa_id)

# 📊 Descargar PDF genérico
@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def descargar_pdf(request):
    html = render_to_string('cda/mi_reporte_pdf.html', {
        'usuario': request.user,
        'now': timezone.now()
    })
    
    try:
        # 🚨 CAMBIA ESTA LÍNEA TAMBIÉN
        config = pdfkit.configuration(wkhtmltopdf='/usr/bin/wkhtmltopdf')  # ← Ruta correcta
        pdf = pdfkit.from_string(html, False, configuration=config)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_general.pdf"'
        return response
    except Exception as e:
        messages.error(request, f'Error al generar PDF: {str(e)}')
        return redirect('cda:home')

# 📋 Dashboard
@login_required
def dashboard_view(request):
    return render(request, 'cda/dashboard.html')

# 📋 LISTA USUARIOS (para compatibilidad con URLs existentes)
@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def lista_usuarios(request):
    # Redirigir a la nueva vista de administración
    return redirect('cda:lista_usuarios_admin')

# 📋eliminar placa

@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def eliminar_placa(request, placa_id):
    placa = get_object_or_404(Placa, id=placa_id)
    if request.method == 'POST':
        placa.delete()
        messages.success(request, 'Placa eliminada correctamente.')
        return redirect('cda:lista_placas')
    return render(request, 'cda/confirmar_eliminacion.html', {'placa': placa})


# 🔑 Cambiar contraseña alos usuarios 
class CambiarContrasenaUsuarioForm(PasswordChangeForm):
    class Meta:
        model = User
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personalizar los campos
        self.fields['new_password1'].widget = forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nueva contraseña',
            'required': True
        })
        self.fields['new_password2'].widget = forms.PasswordInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Confirmar nueva contraseña',
            'required': True
        })


