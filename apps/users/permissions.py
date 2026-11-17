from rest_framework.permissions import SAFE_METHODS, BasePermission


class RoleBasedPermission(BasePermission):
    """Permiso por rol.

    La vista declara ``read_roles`` (GET/HEAD/OPTIONS) y ``write_roles``
    (POST/PUT/PATCH/DELETE). Los administradores siempre tienen acceso.
    """

    message = "Tu rol no tiene permiso para realizar esta acción."

    def has_permission(self, request, view) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_admin:
            return True
        attr = "read_roles" if request.method in SAFE_METHODS else "write_roles"
        return user.role in getattr(view, attr, ())


class IsAdmin(BasePermission):
    message = "Solo los administradores pueden realizar esta acción."

    def has_permission(self, request, view) -> bool:
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)
