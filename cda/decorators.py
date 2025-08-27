# decorators.py (nuevo archivo)
from django.core.exceptions import PermissionDenied

def role_required(*roles):
    def decorator(view_func):
        def wrapped_view(request, *args, **kwargs):
            if request.user.role not in roles and not request.user.is_superuser:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapped_view
    return decorator