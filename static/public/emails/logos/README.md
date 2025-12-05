# 🖼️ Logos para Emails

Esta carpeta contiene los logos que se usarán en los templates de email.

## 📋 Archivos Requeridos

### Logo Principal
**Archivo**: `logo-relatic.png`

**Requisitos**:
- Formato: PNG (mejor compatibilidad con clientes de email)
- Tamaño recomendado: 90-150px de ancho
- Resolución: 72-150 DPI (suficiente para pantalla)
- Peso máximo: 50KB (optimizado para carga rápida)
- Fondo: Transparente o blanco

**Cómo crear/optimizar**:
1. Exportar desde diseño original en PNG
2. Redimensionar a 90-150px de ancho
3. Optimizar con herramienta como TinyPNG o ImageOptim
4. Verificar que el peso sea < 50KB

### Logo Blanco (Opcional)
**Archivo**: `logo-relatic-white.png`

**Cuándo usar**: Para fondos oscuros en headers de email

**Requisitos**: Mismos que el logo principal, pero en color blanco

## 📤 Cómo Subir el Logo

1. **Preparar el archivo**:
   - Asegúrate de que el logo esté en formato PNG
   - Optimiza el tamaño y peso del archivo
   - Verifica que se vea bien en tamaño pequeño (90px)

2. **Subir a la carpeta**:
   ```bash
   # Coloca tu archivo aquí:
   static/public/emails/logos/logo-relatic.png
   ```

3. **Verificar**:
   - El archivo debe estar accesible en: `/static/public/emails/logos/logo-relatic.png`
   - Puedes probarlo accediendo a: `https://miembros.relatic.org/static/public/emails/logos/logo-relatic.png`

## 🔗 Uso en Templates

Los templates usan automáticamente el logo mediante la función `get_public_image_url()`:

```python
logo_url = get_public_image_url('emails/logos/logo-relatic.png', absolute=True)
```

Esto genera una URL absoluta como:
```
https://miembros.relatic.org/static/public/emails/logos/logo-relatic.png
```

## ✅ Checklist

- [ ] Logo en formato PNG
- [ ] Tamaño: 90-150px de ancho
- [ ] Peso: < 50KB
- [ ] Fondo transparente o blanco
- [ ] Se ve bien en tamaño pequeño
- [ ] Archivo colocado en `static/public/emails/logos/`
- [ ] URL accesible desde el navegador

## 📞 Soporte

Si tienes problemas con el logo:
1. Verifica que el archivo esté en la ubicación correcta
2. Verifica los permisos del archivo
3. Prueba accediendo directamente a la URL
4. Revisa `GUIA_IMAGENES_PUBLICAS.md` para más información


