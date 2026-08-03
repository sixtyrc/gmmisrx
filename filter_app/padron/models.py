from django.conf import settings
from django.db import models


class PadronRun(models.Model):
    TRIGGER_AUTOMATICO = "automatico"
    TRIGGER_MANUAL = "manual"
    TRIGGER_CHOICES = [
        (TRIGGER_AUTOMATICO, "Automatico"),
        (TRIGGER_MANUAL, "Manual"),
    ]

    ESTADO_EN_PROGRESO = "en_progreso"
    ESTADO_OK = "ok"
    ESTADO_ERROR = "error"
    ESTADO_CHOICES = [
        (ESTADO_EN_PROGRESO, "En progreso"),
        (ESTADO_OK, "OK"),
        (ESTADO_ERROR, "Error"),
    ]

    iniciado_en = models.DateTimeField(auto_now_add=True)
    finalizado_en = models.DateTimeField(null=True, blank=True)
    disparado_por = models.CharField(max_length=20, choices=TRIGGER_CHOICES)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_EN_PROGRESO
    )

    total_consulta_gx = models.IntegerField(null=True, blank=True)
    total_enviado_misrx = models.IntegerField(null=True, blank=True)
    archivo_generado = models.CharField(max_length=255, blank=True)

    misrx_padrones_registros_id = models.BigIntegerField(null=True, blank=True)
    misrx_estado_descripcion = models.CharField(max_length=255, blank=True)
    misrx_info = models.TextField(blank=True)

    # DNIs incluidos en esta corrida, para poder diffear altas/bajas contra la corrida anterior
    dnis_incluidos = models.JSONField(default=list, blank=True)
    altas_count = models.IntegerField(null=True, blank=True)
    bajas_count = models.IntegerField(null=True, blank=True)

    error_mensaje = models.TextField(blank=True)

    class Meta:
        ordering = ["-iniciado_en"]
        permissions = [
            ("can_run_padron", "Puede ejecutar la actualizacion del padron manualmente"),
        ]

    def __str__(self):
        return f"Corrida {self.pk} ({self.disparado_por}, {self.estado})"


class AfiliadoExcepcion(models.Model):
    ESTADO_PENDIENTE = "pendiente"
    ESTADO_TRATADO = "tratado"
    ESTADO_CHOICES = [
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_TRATADO, "Tratado"),
    ]

    dni = models.CharField(max_length=20)
    nombre_completo = models.CharField(max_length=255, blank=True)
    motivo = models.TextField()
    run_deteccion = models.ForeignKey(
        PadronRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="excepciones_detectadas",
    )
    fecha_deteccion = models.DateTimeField(auto_now_add=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)
    estado = models.CharField(
        max_length=20, choices=ESTADO_CHOICES, default=ESTADO_PENDIENTE
    )

    class Meta:
        ordering = ["-fecha_deteccion"]
        constraints = [
            models.UniqueConstraint(
                fields=["dni", "motivo"], name="unico_dni_motivo_excepcion"
            )
        ]

    def __str__(self):
        return f"{self.dni} - {self.estado}"


class AuditLogEntry(models.Model):
    ACCION_LOGIN_OK = "login_ok"
    ACCION_LOGIN_FAIL = "login_fail"
    ACCION_RUN_MANUAL = "run_manual"
    ACCION_CHOICES = [
        (ACCION_LOGIN_OK, "Login exitoso"),
        (ACCION_LOGIN_FAIL, "Login fallido"),
        (ACCION_RUN_MANUAL, "Ejecucion manual disparada"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    username_intentado = models.CharField(max_length=150, blank=True)
    accion = models.CharField(max_length=20, choices=ACCION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    detalle = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.timestamp} - {self.accion}"
