from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse
from .models import Placa, Foto, UserProfile
from .forms import PlacaForm, FotoForm, CambiarContrasenaForm, CrearUsuarioFormIngeniero, CrearUsuarioFormSuperusuario
from django.template.loader import render_to_string
from django.contrib import messages
from django.utils import timezone
import os
import pdfkit
from django.http import JsonResponse
from django.template.exceptions import TemplateDoesNotExist
import json
from django.views.decorators.http import require_http_methods
from django.core.files.base import ContentFile
import base64

import time
#ESTA PARTE ES PARA EL MAEJO DE SECCIONES 
from django.contrib.auth import authenticate, login
from django.contrib.sessions.models import Session
from django.contrib.auth import logout


# 🔐 Funciones de rol
def is_inspector(user):
    try:
        return user.userprofile.role == 'inspector'
    except UserProfile.DoesNotExist:
        return False

def is_ingeniero(user):
    """Verifica si el usuario es ingeniero"""
    if not user.is_authenticated:
        return False
    return hasattr(user, 'userprofile') and user.userprofile.role == 'ingeniero'

def is_superusuario(user):
    """Verifica si el usuario es superusuario (Django o custom)"""
    if not user.is_authenticated:
        return False
    return user.is_superuser or (hasattr(user, 'userprofile') and user.userprofile.role == 'superusuario')

def es_superusuario_o_ingeniero(user):
    """Verifica si el usuario tiene permisos de administración"""
    if not user.is_authenticated:
        return False
    return is_superusuario(user) or is_ingeniero(user)

# 🏠 Vista principal
@login_required
def home(request):
    return render(request, 'cda/home.html')

# 👤 ADMINISTRACIÓN DE USUARIOS
@login_required
@user_passes_test(es_superusuario_o_ingeniero, login_url='/accounts/login/')
def lista_usuarios_admin(request):
    """
    Vista para gestionar usuarios - Solo superusuarios e ingenieros
    """
    try:
        if is_superusuario(request.user):
            # Superusuarios ven TODOS los usuarios
            usuarios = User.objects.all().select_related('userprofile').order_by('date_joined')
        else:
            # Ingenieros solo ven inspectores e ingenieros (NO superusuarios)
            usuarios = User.objects.filter(
                userprofile__role__in=['inspector', 'ingeniero']
            ).select_related('userprofile').order_by('date_joined')
        
        return render(request, 'cda/lista_usuarios.html', {'usuarios': usuarios})
        
    except Exception as e:
        # Log del error en consola
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en lista_usuarios_admin: {str(e)}")
        
        # Redirigir a home con mensaje de error
        messages.error(request, 'Error al cargar la lista de usuarios. Contacte al administrador.')
        return redirect('cda:home')

@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def crear_usuario(request):
    if is_superusuario(request.user):
        FormClass = CrearUsuarioFormSuperusuario
    else:
        FormClass = CrearUsuarioFormIngeniero  # ✅ Usa el formulario limitado
    
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
    
    # Verificar permisos
    if is_ingeniero(request.user) and user_profile.role == 'superusuario':
        messages.error(request, 'No tienes permisos para editar superusuarios.')
        return redirect('cda:lista_usuarios_admin')
    
    if request.method == 'POST':
        # Actualizar datos básicos del usuario
        usuario.first_name = request.POST.get('first_name', usuario.first_name)
        usuario.last_name = request.POST.get('last_name', usuario.last_name)
        usuario.email = request.POST.get('email', usuario.email)
        usuario.username = request.POST.get('username', usuario.username)
        
        # Actualizar estado activo
        usuario.is_active = 'is_active' in request.POST
        usuario.save()
        
        # ✅ ACTUALIZAR ROL - NUEVA LÓGICA
        nuevo_rol = request.POST.get('role', user_profile.role)
        
        # Superusuarios pueden cambiar cualquier rol
        if is_superusuario(request.user):
            if user_profile.role != nuevo_rol:
                user_profile.role = nuevo_rol
                user_profile.save()
                messages.info(request, f'Rol de {usuario.username} actualizado a {nuevo_rol}.')
        
        # ✅ Ingenieros pueden cambiar solo entre inspector e ingeniero
        elif is_ingeniero(request.user) and nuevo_rol in ['inspector', 'ingeniero']:
            if user_profile.role != nuevo_rol:
                user_profile.role = nuevo_rol
                user_profile.save()
                messages.info(request, f'Rol de {usuario.username} actualizado a {nuevo_rol}.')
        
        messages.success(request, f'Usuario {usuario.username} actualizado correctamente.')
        return redirect('cda:lista_usuarios_admin')
    
    return render(request, 'cda/editar_usuario.html', {
        'usuario': usuario
    })

@login_required
@user_passes_test(es_superusuario_o_ingeniero)
def eliminar_usuario(request, user_id):
    # Obtener el usuario a eliminar
    usuario_a_eliminar = get_object_or_404(User, id=user_id)
    
    # No permitir auto-eliminación
    if usuario_a_eliminar == request.user:
        messages.error(request, 'No puedes eliminar tu propia cuenta.')
        return redirect('cda:lista_usuarios_admin')
    
    # No permitir que ingenieros eliminen superusuarios
    if (usuario_a_eliminar.is_superuser and 
        not is_superusuario(request.user) and
        is_ingeniero(request.user)):
        messages.error(request, 'No tienes permisos para eliminar superusuarios.')
        return redirect('cda:lista_usuarios_admin')
    
    if request.method == 'POST':
        # Verificar confirmación
        confirm_text = request.POST.get('confirm_text', '').strip()
        if confirm_text.upper() != 'ELIMINAR':
            messages.error(request, 'Debe escribir "ELIMINAR" para confirmar la eliminación.')
            return redirect('cda:eliminar_usuario', user_id=user_id)
        
        # Guardar información para el mensaje
        username = usuario_a_eliminar.username
        
        # Eliminar el usuario
        usuario_a_eliminar.delete()
        
        messages.success(request, f'Usuario {username} eliminado permanentemente.')
        return redirect('cda:lista_usuarios_admin')
    
    # Si es GET, mostrar template de confirmación
    return render(request, 'cda/eliminar_usuario.html', {
        'usuario': usuario_a_eliminar
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

@login_required
@user_passes_test(es_superusuario_o_ingeniero)
def cambiar_password_admin(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    
    if is_ingeniero(request.user) and (usuario.is_superuser or is_superusuario(usuario)):
        messages.error(request, 'No tienes permisos para cambiar la contraseña de superusuarios.')
        return redirect('cda:lista_usuarios_admin')  # ← Ahora este nombre SÍ existe
    
    if request.method == 'POST':
        form = AdminPasswordChangeForm(user=usuario, data=request.POST)
        
        if form.is_valid():
            user = form.save()
            messages.success(request, f'✅ Contraseña de {usuario.username} cambiada correctamente.')
            return redirect('cda:lista_usuarios_admin')  # ← Mismo nombre
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'Error en {field}: {error}')
    else:
        form = AdminPasswordChangeForm(user=usuario)
    
    return render(request, 'cda/cambiar_password_admin.html', {
        'form': form,
        'usuario': usuario
    })

#FUNCION PARA UNA SOLO SECCION POR USUARIO 

def login_view(request):
    if request.user.is_authenticated:
        # Si ya está autenticado, redirigir a home
        return redirect('cda:home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            # ✅ PASO CRÍTICO: Eliminar TODAS las sesiones existentes ANTES de hacer login
            active_sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            )
            
            deleted_count = 0
            for session in active_sessions:
                try:
                    session_data = session.get_decoded()
                    if '_auth_user_id' in session_data and session_data['_auth_user_id'] == str(user.id):
                        session.delete()
                        deleted_count += 1
                        print(f"🗑️ Sesión eliminada durante login: {session.session_key[:10]}...")
                except Exception as e:
                    print(f"Error procesando sesión: {e}")
                    continue
            
            print(f"✅ {deleted_count} sesiones anteriores eliminadas para {username}")
            
            # Ahora hacer login
            login(request, user)
            
            # Forzar creación de nueva sesión
            request.session.save()
            
            # Verificar que se creó la sesión
            print(f"✅ Nueva sesión creada: {request.session.session_key}")
            
            # Agregar user_id a la sesión para facilitar búsqueda
            request.session['user_id'] = user.id
            
            messages.success(request, f'¡Bienvenido {user.username}!')
            return redirect('cda:home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos')
    
    return render(request, 'cda/login.html')

# Eliminar todas las sesiones del usuario
def logout_view(request):
    
    if request.user.is_authenticated:
        Session.objects.filter(
            expire_date__gte=timezone.now()
        ).filter(
            session_data__contains=str(request.user.id)
        ).delete()
    
    logout(request)
    return redirect('cda:login')

#Cierra TODAS las sesiones activas del usuario actual
@login_required
def cerrar_todas_las_sesiones(request):
    
    if request.method == 'POST':
        # Eliminar todas las sesiones del usuario
        user_sessions = Session.objects.filter(
            expire_date__gte=timezone.now()
        ).filter(
            session_data__contains=str(request.user.id)
        )
        
        count = user_sessions.count()
        user_sessions.delete()
        
        # Cerrar la sesión actual también
        logout(request)
        
        messages.success(request, f'Se cerraron {count} sesiones activas. Por favor, inicia sesión nuevamente.')
        return redirect('cda:login')
    
    return render(request, 'cda/confirmar_cerrar_sesiones.html')
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
# agregar funciones para eliminar fotos
@login_required
@user_passes_test(lambda u: is_ingeniero(u) or is_superusuario(u))
def eliminar_foto(request, foto_id):
    """
    Vista para eliminar una foto específica
    """
    foto = get_object_or_404(Foto, id=foto_id)
    placa_id = foto.placa.id  # Guardar ID de placa antes de eliminar
    
    # Verificar permisos (solo ingeniero o superusuario pueden eliminar)
    if not (is_ingeniero(request.user) or is_superusuario(request.user)):
        messages.error(request, 'No tienes permisos para eliminar fotos.')
        return redirect('cda:agregar_fotos', placa_id=placa_id)
    
    if request.method == 'POST':
        # Eliminar el archivo físico si existe
        if foto.imagen and os.path.exists(foto.imagen.path):
            os.remove(foto.imagen.path)
        
        # Eliminar el registro de la base de datos
        foto.delete()
        
        messages.success(request, '✅ Foto eliminada correctamente.')
        
        # Si es una petición AJAX, retornar JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': 'Foto eliminada correctamente'})
        
        return redirect('cda:agregar_fotos', placa_id=placa_id)
    
    # Si es GET, mostrar template de confirmación (opcional)
    return render(request, 'cda/confirmar_eliminacion_foto.html', {'foto': foto})

# 📍 Agregar función para obtener detalles de fotos (para el carrusel)
@login_required
def obtener_detalles_foto(request, foto_id):
    """
    API para obtener detalles de una foto específica (para el carrusel)
    """
    try:
        foto = get_object_or_404(Foto, id=foto_id)
        
        data = {
            'id': foto.id,
            'imagen_url': foto.imagen.url,
            'comentario': foto.comentario,
            'fecha': foto.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
            'creado_por': foto.creado_por.get_full_name() or foto.creado_por.username,
            'placa_id': foto.placa.id,
            'placa_numero': foto.placa.numero_placa
        }
        
        return JsonResponse({'success': True, 'foto': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

# 📍 Agregar función para obtener lista de fotos de una placa
@login_required
def obtener_fotos_placa(request, placa_id):
    """
    API para obtener todas las fotos de una placa (para navegación)
    """
    try:
        placa = get_object_or_404(Placa, id=placa_id)
        fotos = Foto.objects.filter(placa=placa).order_by('fecha_creacion')
        
        fotos_data = []
        for foto in fotos:
            fotos_data.append({
                'id': foto.id,
                'imagen_url': foto.imagen.url,
                'comentario': foto.comentario,
                'fecha': foto.fecha_creacion.strftime('%d/%m/%Y %H:%M'),
                'indice': len(fotos_data)  # Índice para navegación
            })
        
        return JsonResponse({'success': True, 'fotos': fotos_data, 'total': len(fotos_data)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
#EDICION DE FOTOS POR EL ROL ING Y SUPER USUAIO 
@login_required
@require_http_methods(["POST"])
def editar_foto(request, foto_id):
    """Vista para editar una foto existente"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Usuario no autenticado'}, status=401)
    
    # Verificar permisos (solo ingenieros y superusuarios pueden editar)
    user_profile = getattr(request.user, 'userprofile', None)
    if not (user_profile and user_profile.role in ['ingeniero', 'superusuario']) and not request.user.is_superuser:
        return JsonResponse({'success': False, 'error': 'Permisos insuficientes'}, status=403)
    
    try:
        foto = Foto.objects.get(id=foto_id)
        
        # Obtener datos del formulario
        comentario = request.POST.get('comentario', '')
        imagen_data = request.POST.get('foto_data', '')
        
        if not comentario:
            return JsonResponse({'success': False, 'error': 'El comentario es requerido'}, status=400)
        
        # Actualizar foto
        foto.comentario = comentario
        foto.ultima_edicion = timezone.now()
        foto.editado_por = request.user
        
        # Si hay nueva imagen, procesarla
        if imagen_data and imagen_data.startswith('data:image/'):
            # Convertir base64 a imagen
            format, imgstr = imagen_data.split(';base64,')
            ext = format.split('/')[-1]
            
            # Crear nombre de archivo único
            filename = f"foto_editada_{foto_id}_{int(time.time())}.{ext}"
            
            # Decodificar imagen
            data = ContentFile(base64.b64decode(imgstr), name=filename)
            
            # Guardar nueva imagen (sobreescribir la anterior)
            foto.imagen.save(filename, data, save=True)
        else:
            foto.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Foto editada correctamente',
            'foto_id': foto.id
        })
        
    except Foto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Foto no encontrada'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
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

