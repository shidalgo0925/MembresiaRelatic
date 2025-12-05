# Configuración de Gmail para Envío de Emails

## Opciones de Autenticación con Gmail

### Opción 1: Usar Variables de Entorno (Recomendado)

Si prefieres no usar App Passwords, puedes configurar las credenciales directamente en variables de entorno del sistema.

**Pasos:**

1. **Configurar variables de entorno:**
   ```bash
   export MAIL_USERNAME="tu_email@gmail.com"
   export MAIL_PASSWORD="tu_contraseña_normal_o_app_password"
   export MAIL_SERVER="smtp.gmail.com"
   export MAIL_PORT="587"
   export MAIL_USE_TLS="True"
   export MAIL_DEFAULT_SENDER="tu_email@gmail.com"
   ```

2. **En el panel de administración (`/admin/email`):**
   - Activar la opción "Usar Variables de Entorno"
   - Dejar los campos de usuario/contraseña vacíos
   - El sistema tomará las credenciales de las variables de entorno

3. **Para hacer permanente (en el servicio systemd):**
   Editar el archivo del servicio: `/etc/systemd/system/membresia-relatic.service`
   
   Agregar en la sección `[Service]`:
   ```ini
   Environment="MAIL_USERNAME=tu_email@gmail.com"
   Environment="MAIL_PASSWORD=tu_contraseña"
   Environment="MAIL_SERVER=smtp.gmail.com"
   Environment="MAIL_PORT=587"
   Environment="MAIL_USE_TLS=True"
   Environment="MAIL_DEFAULT_SENDER=tu_email@gmail.com"
   ```
   
   Luego reiniciar:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart membresia-relatic.service
   ```

### Opción 2: Usar Contraseña Normal (Solo si NO tienes 2FA)

Si tu cuenta de Gmail **NO tiene verificación en 2 pasos activada**, puedes usar tu contraseña normal:

1. **En el panel de administración (`/admin/email`):**
   - Desactivar "Usar Variables de Entorno"
   - Servidor: `smtp.gmail.com`
   - Puerto: `587`
   - Usar TLS: ✅ Activado
   - Usuario: `tu_email@gmail.com`
   - Contraseña: `tu_contraseña_normal`
   - Remitente: `tu_email@gmail.com`

**⚠️ IMPORTANTE:** Esta opción es menos segura. Gmail recomienda usar App Passwords.

### Opción 3: Usar App Password (Más Seguro)

Si tu cuenta tiene verificación en 2 pasos (recomendado), necesitas usar una App Password:

1. **Generar App Password:**
   - Ir a: https://myaccount.google.com/apppasswords
   - Seleccionar "Correo" y "Otro (nombre personalizado)"
   - Copiar la contraseña de 16 caracteres generada

2. **En el panel de administración (`/admin/email`):**
   - Servidor: `smtp.gmail.com`
   - Puerto: `587`
   - Usar TLS: ✅ Activado
   - Usuario: `tu_email@gmail.com`
   - Contraseña: `[la_app_password_de_16_caracteres]`
   - Remitente: `tu_email@gmail.com`

## Verificación de la Configuración

Después de configurar:

1. **Probar envío:**
   - Ir a `/admin/email`
   - Hacer clic en "Probar Envío"
   - Verificar que llegue el correo de prueba

2. **Revisar logs:**
   ```bash
   sudo journalctl -u membresia-relatic.service -f
   ```
   
   Buscar mensajes como:
   - ✅ `Email enviado exitosamente`
   - ❌ `Error enviando email` (si hay problemas)

3. **Verificar en EmailLog:**
   - Ir a `/admin/email/logs`
   - Verificar que los emails se registren correctamente

## Solución de Problemas

### Error: "Username and Password not accepted"

**Causas posibles:**
1. Contraseña incorrecta
2. Cuenta tiene 2FA activada pero no se está usando App Password
3. "Acceso de aplicaciones menos seguras" está desactivado (si usas contraseña normal)

**Soluciones:**
- Si tienes 2FA: Usar App Password (Opción 3)
- Si no tienes 2FA: Activar "Acceso de aplicaciones menos seguras" en tu cuenta de Google (no recomendado)
- Verificar que las credenciales sean correctas

### Error: "from_email NOT NULL constraint failed"

✅ **Ya corregido** - El sistema ahora incluye automáticamente el campo `from_email`

## Notas Importantes

- **Seguridad:** Siempre es mejor usar App Passwords o variables de entorno que guardar contraseñas en la base de datos
- **Variables de Entorno:** Son más seguras porque no se almacenan en la BD
- **App Passwords:** Son específicas para aplicaciones y se pueden revocar fácilmente
- **Contraseña Normal:** Solo funciona si NO tienes 2FA activado


