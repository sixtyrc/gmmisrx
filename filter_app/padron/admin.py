from django.contrib import admin

from .models import AfiliadoExcepcion, AuditLogEntry, PadronRun


@admin.register(PadronRun)
class PadronRunAdmin(admin.ModelAdmin):
    list_display = [
        "id", "iniciado_en", "disparado_por", "estado",
        "total_consulta_gx", "total_enviado_misrx",
        "altas_count", "bajas_count", "misrx_estado_descripcion",
    ]
    list_filter = ["estado", "disparado_por"]
    readonly_fields = [f.name for f in PadronRun._meta.fields]

    def has_add_permission(self, request):
        return False


@admin.register(AfiliadoExcepcion)
class AfiliadoExcepcionAdmin(admin.ModelAdmin):
    list_display = ["dni", "nombre_completo", "motivo", "estado", "fecha_deteccion"]
    list_filter = ["estado"]
    search_fields = ["dni", "nombre_completo"]


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ["timestamp", "accion", "usuario", "username_intentado", "ip_address"]
    list_filter = ["accion"]

    def has_add_permission(self, request):
        return False
