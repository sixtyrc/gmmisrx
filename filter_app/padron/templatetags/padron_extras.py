from django import template

from padron.services.convenios import nombre_convenio as _nombre_convenio

register = template.Library()


@register.filter(name="nombre_convenio")
def nombre_convenio(codigo):
    return _nombre_convenio(codigo)
