from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'cda'

urlpatterns = [
    # 🏠 Página principal
    path('', views.home, name='home'),

    # 🔐 Autenticación
    path('accounts/login/', auth_views.LoginView.as_view(template_name='cda/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='cda:login'), name='logout'),

    # 🚗 Gestión de placas
    path('placas/', views.lista_placas, name='lista_placas'),
    path('placas/crear/', views.crear_placa, name='crear_placa'),
    path('placas/<int:placa_id>/fotos/', views.agregar_fotos, name='agregar_fotos'),
    path('placas/<int:placa_id>/pdf/', views.generar_pdf, name='generar_pdf'),
    path('placas/<int:placa_id>/eliminar/', views.eliminar_placa, name='eliminar_placa'),

    # 🖼️ Nuevas rutas para gestión de fotos
    path('fotos/<int:foto_id>/eliminar/', views.eliminar_foto, name='eliminar_foto'),
    path('fotos/<int:foto_id>/detalles/', views.obtener_detalles_foto, name='detalles_foto'),
    path('placas/<int:placa_id>/fotos-lista/', views.obtener_fotos_placa, name='fotos_placa'),

    path('fotos/<int:foto_id>/editar/', views.editar_foto, name='editar_foto'),

    # 👤 Administración de usuarios (COMPLETO)
    path('admin/usuarios/', views.lista_usuarios_admin, name='lista_usuarios_admin'),
    path('admin/usuarios/crear/', views.crear_usuario, name='crear_usuario'),
    path('admin/usuarios/<int:user_id>/editar/', views.editar_usuario, name='editar_usuario'),
    path('admin/usuarios/<int:user_id>/eliminar/', views.eliminar_usuario, name='eliminar_usuario'),  # NUEVA
    path('admin/usuarios/<int:user_id>/toggle/', views.toggle_usuario, name='toggle_usuario'),
    path('admin/usuarios/cambiar-contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
    path('admin/usuarios/<int:user_id>/cambiar-password/', views.cambiar_password_admin, name='cambiar_password_admin'),  # NUEVA
    path('admin/usuarios/<int:user_id>/cambiar-password/', views.cambiar_password_admin, name='cambiar_password'),

    # 📊 Descargar PDF
    path('descargar-reporte/', views.descargar_pdf, name='descargar_pdf'),
    
    # 📋 Dashboard
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # 📋 Compatibilidad con URLs antiguas
    path('usuarios/', views.lista_usuarios, name='lista_usuarios'),
    
    #cerrar todas las secciones 
    path('cerrar-todas-sesiones/', views.cerrar_todas_las_sesiones, name='cerrar_todas_sesiones'),
]

