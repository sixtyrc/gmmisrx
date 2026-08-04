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
    ACCION_VADEMECUM_ACTUALIZADO = "vademecum_upd"
    ACCION_CHOICES = [
        (ACCION_LOGIN_OK, "Login exitoso"),
        (ACCION_LOGIN_FAIL, "Login fallido"),
        (ACCION_RUN_MANUAL, "Ejecucion manual disparada"),
        (ACCION_VADEMECUM_ACTUALIZADO, "Vademecum actualizado"),
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


class CronicoLog(models.Model):
    """Auditoria de operaciones sobre prescripciones cronicas en MisRx (feature
    experimental: el comportamiento real de 'baja' via API todavia no esta
    confirmado, por eso se guarda el payload y la respuesta cruda completa)."""

    ACCION_ALTA = "alta"
    ACCION_BAJA = "baja"
    ACCION_ROLLBACK = "rollback"
    ACCION_CHOICES = [
        (ACCION_ALTA, "Alta/Modificacion"),
        (ACCION_BAJA, "Baja"),
        (ACCION_ROLLBACK, "Rollback (admin)"),
    ]

    timestamp = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    accion = models.CharField(max_length=10, choices=ACCION_CHOICES)
    dni = models.CharField(max_length=20, blank=True)
    nro_afiliado = models.CharField(max_length=20, blank=True)
    # Snapshot de como estaba el registro en MisRx ANTES de esta operacion
    # (null en un alta nueva, ya que ahi no habia nada antes). Es lo que permite
    # reconstruir a mano un rollback si una baja/edicion fue un error.
    estado_anterior = models.JSONField(null=True, blank=True)
    payload_enviado = models.JSONField(null=True, blank=True)
    status_code_misrx = models.IntegerField(null=True, blank=True)
    respuesta_misrx = models.TextField(blank=True)
    exitoso = models.BooleanField(default=False)

    class Meta:
        ordering = ["-timestamp"]
        permissions = [
            ("can_manage_cronicos", "Puede cargar/dar de baja prescripciones cronicas en MisRx"),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.accion} - {self.dni}"


class ConsumoConsultaLog(models.Model):
    """Auditoria de consultas de recetas/consumo por DNI (GET /consultas/consultar/14).

    A diferencia de CronicoLog no hay nada que revertir (es de solo lectura),
    por eso no tiene estado_anterior/payload_enviado - solo registra quien
    consulto que DNI y cuando, para trazabilidad de acceso a datos de recetas."""

    timestamp = models.DateTimeField(auto_now_add=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL
    )
    dni = models.CharField(max_length=20, blank=True)
    total_recetas = models.IntegerField(null=True, blank=True)
    exitoso = models.BooleanField(default=False)
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["-timestamp"]
        permissions = [
            ("can_view_consumos", "Puede consultar recetas y consumos por DNI en MisRx"),
        ]

    def __str__(self):
        return f"{self.timestamp} - {self.dni}"


class VademecumItem(models.Model):
    """Catalogo Alfabeta (producto/monodroga) para buscar por nombre en vez de
    tener que conocer de memoria monodroga_id/producto_id. Se carga con
    `manage.py cargar_vademecum` desde una planilla externa, no se edita a mano."""

    producto_id = models.BigIntegerField(unique=True)
    nombre_producto = models.CharField(max_length=255)
    presentacion = models.CharField(max_length=255, blank=True)
    laboratorio = models.CharField(max_length=255, blank=True)
    troquel = models.CharField(max_length=50, blank=True)
    codigobarra = models.CharField(max_length=50, blank=True)
    monodroga_id = models.BigIntegerField()
    monodroga_nombre = models.CharField(max_length=255)
    potencia = models.CharField(max_length=100, blank=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["monodroga_nombre"]),
            models.Index(fields=["nombre_producto"]),
            models.Index(fields=["monodroga_id"]),
        ]

    def __str__(self):
        return f"{self.nombre_producto} ({self.monodroga_nombre})"
