from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import logout
from django.shortcuts import redirect
import logging

logger = logging.getLogger(__name__)

class OneSessionPerUserMiddleware:
    """
    Middleware que garantiza que cada usuario tenga solo UNA sesión activa.
    Si se detecta una nueva sesión, se eliminan TODAS las anteriores.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Código que se ejecuta ANTES de cada vista
        
        if request.user.is_authenticated:
            current_session_key = request.session.session_key
            
            # Obtener TODAS las sesiones activas de este usuario
            user_sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            ).filter(
                session_data__contains=str(request.user.id)
            )
            
            # Si hay más de una sesión activa
            if user_sessions.count() > 1:
                print(f"⚠️ Usuario {request.user.username} tiene {user_sessions.count()} sesiones activas")
                
                # Mantener solo la sesión ACTUAL, eliminar las demás
                for session in user_sessions:
                    if session.session_key != current_session_key:
                        try:
                            print(f"🗑️ Eliminando sesión antigua: {session.session_key}")
                            session.delete()
                        except Exception as e:
                            logger.error(f"Error eliminando sesión {session.session_key}: {e}")
            
            # Si el usuario está autenticado pero la sesión actual NO está en las activas
            # (puede pasar si otra sesión la eliminó)
            elif current_session_key and not user_sessions.filter(session_key=current_session_key).exists():
                print(f"🚨 Sesión actual {current_session_key} fue invalidada por otra sesión")
                
                # Forzar logout
                logout(request)
                
                # Redirigir a login con mensaje
                from django.contrib import messages
                messages.warning(request, 'Tu sesión fue cerrada porque iniciaste sesión en otro dispositivo.')
                return redirect('cda:login')
        
        response = self.get_response(request)
        
        # Código que se ejecuta DESPUÉS de cada vista
        return response