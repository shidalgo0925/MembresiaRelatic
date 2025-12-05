# 📧 Plan de Gestión de Emails - Sistema RelaticPanama

## 🎯 Resumen Ejecutivo

El sistema de gestión de emails de RelaticPanama es un sistema completo y automatizado que:
- **Envía emails transaccionales** para notificar eventos importantes
- **Registra todos los emails** en la base de datos para auditoría
- **Maneja errores** con reintentos automáticos
- **Usa plantillas HTML profesionales** para todos los correos
- **Proporciona un panel administrativo** para ver y gestionar todos los emails enviados

---

## 🏗️ Arquitectura del Sistema

### Componentes Principales

```
┌─────────────────────────────────────────────────────────┐
│                    FLUJO DE EMAILS                       │
└─────────────────────────────────────────────────────────┘

1. EVENTO DEL SISTEMA
   ↓
2. NotificationEngine (Motor de Notificaciones)
   ↓
3. EmailService (Servicio de Envío)
   ├── Reintentos automáticos (3 intentos)
   ├── Manejo de errores
   └── Registro en EmailLog
   ↓
4. email_templates.py (Plantillas HTML)
   ↓
5. Flask-Mail (Envío SMTP)
   ↓
6. EmailLog (Registro en BD)
   ↓
7. Panel Admin (/admin/messaging)
```

---

## 📋 Componentes Detallados

### 1. **EmailService** (`backend/email_service.py`)

**Responsabilidades:**
- Envío centralizado de correos electrónicos
- Reintentos automáticos (3 intentos con backoff exponencial)
- Registro automático en `EmailLog`
- Manejo de errores y logging

**Características:**
```python
class EmailService:
    - send_email()           # Envío individual con reintentos
    - send_bulk_email()      # Envío masivo
    - send_template_email()  # Envío usando plantillas
```

**Flujo de Envío:**
1. Intenta enviar el email
2. Si falla, espera 2 segundos y reintenta (hasta 3 veces)
3. Registra éxito o fallo en `EmailLog`
4. Retorna `True` si se envió, `False` si falló

---

### 2. **EmailTemplates** (`backend/email_templates.py`)

**Responsabilidades:**
- Plantillas HTML profesionales y responsive
- Diseño consistente con branding de RelaticPanama
- Templates específicos para cada tipo de notificación

**Plantillas Disponibles:**
- ✅ `get_membership_payment_confirmation_email()` - Confirmación de pago
- ✅ `get_membership_expiring_email()` - Membresía por expirar
- ✅ `get_membership_expired_email()` - Membresía expirada
- ✅ `get_membership_renewed_email()` - Membresía renovada
- ✅ `get_event_registration_email()` - Registro a evento
- ✅ `get_event_cancellation_email()` - Cancelación de evento
- ✅ `get_event_update_email()` - Actualización de evento
- ✅ `get_appointment_confirmation_email()` - Confirmación de cita
- ✅ `get_appointment_reminder_email()` - Recordatorio de cita
- ✅ `get_welcome_email()` - Email de bienvenida
- ✅ `get_password_reset_email()` - Restablecimiento de contraseña

**Características del Template Base:**
- Diseño responsive (móvil y desktop)
- CSS inline para compatibilidad
- Logo y branding de RelaticPanama
- Botones de acción con enlaces
- Footer con información de contacto

---

### 3. **NotificationEngine** (`backend/app.py`)

**Responsabilidades:**
- Motor centralizado de notificaciones
- Coordina envío de emails y creación de notificaciones en panel
- Métodos estáticos para cada tipo de evento

**Métodos Principales:**
```python
class NotificationEngine:
    @staticmethod
    def notify_welcome(user)
    @staticmethod
    def notify_membership_payment(user, payment, subscription)
    @staticmethod
    def notify_membership_expiring(user, subscription, days_left)
    @staticmethod
    def notify_membership_expired(user, subscription)
    @staticmethod
    def notify_membership_renewed(user, subscription)
    @staticmethod
    def notify_event_registration(event, user, registration)
    @staticmethod
    def notify_event_cancellation(event, user, registration)
    @staticmethod
    def notify_event_confirmation(event, user, registration)
    @staticmethod
    def notify_event_update(event, changes)
    @staticmethod
    def notify_appointment_confirmation(appointment)
    @staticmethod
    def notify_appointment_reminder(appointment)
```

**Flujo de Notificación:**
1. Crea `Notification` en la base de datos (para el panel)
2. Genera HTML usando `email_templates`
3. Envía email usando `EmailService`
4. Registra en `EmailLog` automáticamente
5. Marca `email_sent=True` en la notificación

---

### 4. **EmailLog** (Modelo de Base de Datos)

**Responsabilidades:**
- Registro completo de todos los emails enviados
- Auditoría y trazabilidad
- Permite reenvío de emails fallidos

**Estructura:**
```python
class EmailLog:
    id                      # ID único
    recipient_id           # ID del usuario (NULL si es externo)
    recipient_email        # Email del destinatario
    recipient_name         # Nombre del destinatario
    subject                # Asunto del email
    html_content           # Contenido HTML (limitado a 5000 chars)
    text_content           # Contenido texto plano
    email_type             # Tipo: membership_payment, event_registration, etc.
    related_entity_type    # Tipo de entidad: membership, event, appointment
    related_entity_id     # ID de la entidad relacionada
    status                 # sent, failed, pending
    error_message          # Mensaje de error si falló
    retry_count            # Número de reintentos
    sent_at                # Fecha/hora de envío
    created_at             # Fecha/hora de creación
```

**Uso:**
- Panel administrativo: `/admin/messaging`
- Ver todos los emails enviados
- Filtrar por tipo, estado, fecha
- Reenviar emails fallidos
- Ver detalles completos de cada email

---

### 5. **Panel Administrativo** (`/admin/messaging`)

**Funcionalidades:**
- ✅ Lista paginada de todos los emails
- ✅ Filtros por tipo de email y estado
- ✅ Búsqueda por destinatario o asunto
- ✅ Ver detalles completos de cada email
- ✅ Reenviar emails fallidos
- ✅ Eliminar registros antiguos
- ✅ Estadísticas (total, enviados, fallidos)

**Rutas:**
- `GET /admin/messaging` - Lista de emails
- `GET /admin/messaging/<id>` - Detalle de email
- `POST /admin/messaging/<id>/resend` - Reenviar email
- `POST /admin/messaging/<id>/delete` - Eliminar registro
- `GET /api/admin/messaging/stats` - Estadísticas JSON

---

## 🔄 Flujos de Trabajo

### Flujo 1: Pago de Membresía

```
1. Usuario completa pago en Stripe
   ↓
2. Webhook de Stripe recibe confirmación
   ↓
3. Se crea Payment y Subscription
   ↓
4. NotificationEngine.notify_membership_payment()
   ↓
5. EmailService.send_email() con plantilla de confirmación
   ↓
6. Email enviado y registrado en EmailLog
   ↓
7. Notificación creada en panel del usuario
```

### Flujo 2: Registro a Evento

```
1. Usuario se registra a un evento
   ↓
2. Se crea EventRegistration
   ↓
3. NotificationEngine.notify_event_registration()
   ↓
4. Obtiene responsables del evento (moderador, admin, expositor)
   ↓
5. Para cada responsable:
   ├── Crea Notification en BD
   ├── Genera email con plantilla
   ├── Envía email usando EmailService
   └── Registra en EmailLog
   ↓
6. También notifica al usuario que se registró
```

### Flujo 3: Membresía por Expirar

```
1. notification_scheduler.py se ejecuta (cron job diario)
   ↓
2. Busca membresías que expiran en 30, 15, 7, 1 días
   ↓
3. Para cada membresía:
   ├── NotificationEngine.notify_membership_expiring()
   ├── Genera email con días restantes
   ├── Envía email
   └── Registra en EmailLog
```

---

## 📊 Tipos de Emails por Categoría

### Membresías
| Tipo | Cuándo se envía | Plantilla |
|------|----------------|-----------|
| `membership_payment` | Pago confirmado | `get_membership_payment_confirmation_email()` |
| `membership_expiring` | 30, 15, 7, 1 días antes | `get_membership_expiring_email()` |
| `membership_expired` | Cuando expira | `get_membership_expired_email()` |
| `membership_renewed` | Renovación exitosa | `get_membership_renewed_email()` |

### Eventos
| Tipo | Cuándo se envía | Plantilla |
|------|----------------|-----------|
| `event_registration` | Usuario se registra | `get_event_registration_email()` |
| `event_registration_notification` | Notifica a responsables | `get_event_registration_email()` |
| `event_cancellation` | Usuario cancela | `get_event_cancellation_email()` |
| `event_cancellation_notification` | Notifica a responsables | `get_event_cancellation_email()` |
| `event_confirmation` | Registro confirmado | `get_event_confirmation_email()` |
| `event_update` | Evento actualizado | `get_event_update_email()` |

### Citas (Appointments)
| Tipo | Cuándo se envía | Plantilla |
|------|----------------|-----------|
| `appointment_confirmation` | Cita confirmada | `get_appointment_confirmation_email()` |
| `appointment_reminder` | 24-48h antes | `get_appointment_reminder_email()` |

### Sistema
| Tipo | Cuándo se envía | Plantilla |
|------|----------------|-----------|
| `welcome` | Nuevo usuario | `get_welcome_email()` |
| `password_reset` | Solicitud de reset | `get_password_reset_email()` |

---

## 🔧 Configuración

### Variables de Entorno

```env
# SMTP Configuration
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=True
MAIL_USERNAME=tu_email@gmail.com
MAIL_PASSWORD=tu_app_password
MAIL_DEFAULT_SENDER=noreply@relaticpanama.org
```

### Configurar Gmail

1. Habilitar autenticación de 2 factores
2. Generar contraseña de aplicación
3. Usar la contraseña como `MAIL_PASSWORD`

---

## 🚀 Uso en el Código

### Ejemplo 1: Enviar Email Simple

```python
from backend.app import email_service, log_email_sent

# Enviar email directamente
success = email_service.send_email(
    subject="Asunto del correo",
    recipients=["usuario@example.com"],
    html_content="<h1>Contenido HTML</h1>",
    email_type="general",
    recipient_name="Nombre Usuario"
)
```

### Ejemplo 2: Usar NotificationEngine

```python
from backend.app import NotificationEngine, User, Payment, Subscription

# Notificar pago de membresía
NotificationEngine.notify_membership_payment(user, payment, subscription)

# Notificar bienvenida
NotificationEngine.notify_welcome(user)

# Notificar membresía por expirar
NotificationEngine.notify_membership_expiring(user, subscription, days_left=7)
```

### Ejemplo 3: Usar Plantillas

```python
from backend.email_templates import get_membership_payment_confirmation_email
from backend.app import email_service

# Generar HTML de la plantilla
html = get_membership_payment_confirmation_email(user, payment, subscription)

# Enviar usando EmailService
email_service.send_email(
    subject="Confirmación de Pago",
    recipients=[user.email],
    html_content=html,
    email_type="membership_payment",
    related_entity_type="membership",
    related_entity_id=subscription.id,
    recipient_id=user.id,
    recipient_name=f"{user.first_name} {user.last_name}"
)
```

---

## 📈 Estadísticas y Monitoreo

### Panel Administrativo

Acceder a `/admin/messaging` para ver:
- Total de emails enviados
- Emails exitosos vs fallidos
- Filtros por tipo y estado
- Búsqueda por destinatario/asunto

### API de Estadísticas

```bash
GET /api/admin/messaging/stats
```

Retorna:
```json
{
  "total": 1250,
  "sent": 1200,
  "failed": 50,
  "by_type": {
    "membership_payment": 300,
    "event_registration": 500,
    "welcome": 200
  }
}
```

---

## 🔄 Tareas Programadas

### notification_scheduler.py

Script que se ejecuta diariamente (cron job) para:
- Verificar membresías por expirar
- Enviar recordatorios automáticos
- Verificar citas próximas y enviar recordatorios

**Configurar Cron:**
```bash
# Ejecutar diariamente a las 9:00 AM
0 9 * * * cd /ruta/al/proyecto/backend && python notification_scheduler.py
```

---

## 🛡️ Manejo de Errores

### Reintentos Automáticos

- **3 intentos** por defecto
- **Backoff exponencial**: 2s, 4s, 8s
- Si falla después de 3 intentos, se registra como `failed` en `EmailLog`

### Registro de Errores

Todos los errores se registran en:
- `EmailLog.error_message` - Mensaje de error
- `EmailLog.retry_count` - Número de reintentos
- `EmailLog.status` - `sent` o `failed`

### Logging

El sistema registra en consola:
- ✅ Envíos exitosos
- ❌ Errores de envío
- ⚠️ Advertencias

---

## 🔍 Auditoría y Trazabilidad

### ¿Qué se registra?

- ✅ Todos los emails enviados (exitosos y fallidos)
- ✅ Destinatario, asunto, contenido
- ✅ Tipo de email y entidad relacionada
- ✅ Fecha/hora de envío
- ✅ Errores y reintentos

### ¿Para qué sirve?

- **Auditoría**: Ver qué emails se enviaron y cuándo
- **Debugging**: Identificar problemas de envío
- **Reenvío**: Reenviar emails fallidos desde el panel
- **Estadísticas**: Analizar patrones de envío
- **Cumplimiento**: Probar que se notificó a usuarios

---

## 🎨 Personalización

### Modificar Plantillas

Editar `backend/email_templates.py`:
```python
def get_custom_email(user, data):
    content = f"""
        <h2>Título Personalizado</h2>
        <p>Contenido: {data}</p>
    """
    return get_email_template_base().format(
        subject="Asunto Personalizado",
        content=content,
        year=datetime.now().year
    )
```

### Agregar Nuevo Tipo de Email

1. Crear plantilla en `email_templates.py`
2. Agregar método en `NotificationEngine`
3. Llamar desde el lugar apropiado en el código

---

## 📝 Mejores Prácticas

1. **Siempre usar EmailService** - No enviar emails directamente con Flask-Mail
2. **Usar plantillas** - Mantener consistencia visual
3. **Registrar en EmailLog** - EmailService lo hace automáticamente
4. **Manejar errores** - El sistema tiene reintentos, pero verificar logs
5. **Probar plantillas** - Verificar que se vean bien en diferentes clientes
6. **Limpiar logs antiguos** - Eliminar registros de más de 90 días periódicamente

---

## 🚧 Mejoras Futuras

- [ ] Sistema de preferencias de notificaciones por usuario
- [ ] Notificaciones push en tiempo real
- [ ] Dashboard de estadísticas avanzadas
- [ ] Plantillas personalizables por administrador
- [ ] Integración con SendGrid/Mailgun para mejor deliverability
- [ ] Sistema de colas (Celery) para envíos masivos
- [ ] Preview de emails antes de enviar
- [ ] A/B testing de plantillas

---

## 📞 Soporte

Para problemas o preguntas:
- Revisar logs en la consola
- Verificar configuración SMTP en variables de entorno
- Consultar registros en `/admin/messaging`
- Revisar `EmailLog` en la base de datos

---

**RelaticPanama** - Sistema de Gestión de Emails v1.0  
**Última actualización:** Diciembre 2025


