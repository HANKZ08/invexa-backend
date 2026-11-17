from django.contrib.auth.models import AbstractUser
from django.db import models


# Usuario del sistema: extiende el usuario de Django con un correo único y un rol de negocio.
class User(AbstractUser):
    # Roles disponibles: definen qué puede hacer cada usuario en la API.
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrador"
        CASHIER = "cashier", "Cajero"
        WAREHOUSE = "warehouse", "Bodeguero"

    email = models.EmailField(
        "correo",
        unique=True,
        help_text="Correo electrónico del usuario. Debe ser único.",
    )
    role = models.CharField(
        "rol",
        max_length=20,
        choices=Role.choices,
        default=Role.CASHIER,
        help_text="Rol del usuario: admin (todo), cashier (ventas) o warehouse (inventario).",
    )
    avatar = models.ImageField(
        "foto de perfil",
        upload_to="avatars/",
        null=True,
        blank=True,
        help_text="Foto de perfil (PNG, JPG o GIF, máximo 10 MB).",
    )
    email_verified_at = models.DateTimeField(
        "correo verificado el",
        null=True,
        blank=True,
        help_text="Fecha en que el usuario confirmó su correo con el código. Vacío = sin verificar.",
    )

    # Configuración: nombres en el admin y orden por nombre de usuario.
    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ("username",)

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.is_superuser or self.role == self.Role.ADMIN

    def __str__(self) -> str:
        return self.get_full_name() or self.username


# Código de verificación de correo: 6 dígitos de un solo uso, guardado como hash y con vencimiento.
class EmailVerification(models.Model):
    user = models.ForeignKey(
        User,
        verbose_name="usuario",
        on_delete=models.CASCADE,
        related_name="email_verifications",
        help_text="Usuario que debe confirmar su correo.",
    )
    code_hash = models.CharField(
        "hash del código",
        max_length=128,
        help_text="HMAC del código de 6 dígitos. El código en texto plano nunca se guarda.",
    )
    expires_at = models.DateTimeField(
        "vence el",
        help_text="Después de esta fecha el código ya no es válido.",
    )
    attempts = models.PositiveSmallIntegerField(
        "intentos",
        default=0,
        help_text="Intentos fallidos. Al llegar al máximo, el código se invalida.",
    )
    used_at = models.DateTimeField(
        "usado el",
        null=True,
        blank=True,
        help_text="Fecha en que se usó o invalidó el código. Vacío = código vigente.",
    )
    created_at = models.DateTimeField(
        "creado",
        auto_now_add=True,
        help_text="Fecha en que se envió el código (automático).",
    )

    # Configuración: los códigos más recientes primero.
    class Meta:
        verbose_name = "verificación de correo"
        verbose_name_plural = "verificaciones de correo"
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"Verificación de {self.user} ({self.created_at:%Y-%m-%d %H:%M})"
