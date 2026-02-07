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
        
        if request.user.is_authenticated and request.session.session_key:
            current_user_id = str(request.user.id)
            current_session_key = request.session.session_key
            
            print(f"🔍 [MIDDLEWARE] Usuario: {request.user.username} (ID: {current_user_id})")
            print(f"   Sesión actual: {current_session_key}")
            
            # Obtener TODAS las sesiones activas
            all_active_sessions = Session.objects.filter(
                expire_date__gte=timezone.now()
            )
            
            # Lista para almacenar sesiones del usuario actual
            user_sessions_ids = []
            
            # Recorrer todas las sesiones activas para encontrar las del usuario actual
            for session in all_active_sessions:
                try:
                    session_data = session.get_decoded()
                    
                    if '_auth_user_id' in session_data:
                        session_user_id = session_data['_auth_user_id']
                        
                        # Si esta sesión pertenece al usuario actual
                        if session_user_id == current_user_id:
                            user_sessions_ids.append(session.session_key)
                            
                            # Si no es la sesión actual, ELIMINARLA
                            if session.session_key != current_session_key:
                                print(f"🗑️ Eliminando sesión anterior: {session.session_key}")
                                session.delete()
                                
                except Exception as e:
                    logger.error(f"Error decodificando sesión {session.session_key}: {e}")
                    continue
            
            print(f"   Sesiones del usuario {request.user.username}: {len(user_sessions_ids)}")
            
            # Verificar si la sesión actual fue eliminada por otro dispositivo
            if (current_session_key and 
                current_session_key not in user_sessions_ids and
                not Session.objects.filter(session_key=current_session_key).exists()):
                
                print(f"🚨 Sesión actual {current_session_key} fue invalidada por otra sesión")
                
                # Forzar logout
                logout(request)
                
                # Redirigir a login con mensaje
                from django.contrib import messages
                messages.warning(request, 'Tu sesión fue cerrada porque iniciaste sesión en otro dispositivo.')
                return redirect('cda:login')
            
            print(f"✅ [MIDDLEWARE] Procesamiento completado para {request.user.username}")
        
        response = self.get_response(request)
        
        # Código que se ejecuta DESPUÉS de cada vista
        return response