from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from cda.views import home

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # URLs de autenticación
    path('accounts/login/', 
        auth_views.LoginView.as_view(
            template_name='cda/login.html',  
            redirect_authenticated_user=True
        ), 
        name='login'),
    
    

    path('', home, name='home'),
    path('cda/', include('cda.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


