# Sistema de Membresía RelaticPanama

Sistema completo de gestión de membresías para RelaticPanama con integración de pagos y formularios de suscripción.

## 🚀 Características

### Sistema de Membresías
- **4 Planes de Membresía:**
  - **Básico**: Gratis - Recursos básicos, boletines RELATIC e invitaciones abiertas
  - **Pro**: $60/año - Todo lo de Básico + acceso a revistas/bases y certificaciones
  - **Premium**: $120/año - Todo lo de Pro + asesoría, soporte prioritario y webinars exclusivos
  - **DeLuxe**: $200/año - Todo lo de Premium + O365 completo, soporte 24/7 y consultoría estratégica

### Formulario de Suscripción Adicional
- **Precio**: $30 USD
- **Campos completos**: Email, país, cédula/DNI, pasaporte, afiliación, ORCID, datos personales, foto carnet
- **Métodos de pago**: Banco General, Yappy, PayPal, Interbank

### Tecnologías
- **Backend**: Flask (Python)
- **Base de datos**: SQLite (desarrollo) / PostgreSQL (producción)
- **Frontend**: Bootstrap 5 + HTML/CSS personalizado
- **Pagos**: Stripe API (modo demo incluido)
- **Autenticación**: Flask-Login
- **Email**: Flask-Mail

## 📁 Estructura del Proyecto

```
relaticpanama/
├── backend/
│   └── app.py                 # Aplicación Flask principal
├── templates/                 # Templates HTML
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── membership.html
│   ├── benefits.html
│   ├── checkout.html
│   ├── payment_success.html
│   ├── subscription_form.html
│   └── profile.html
├── static/
│   └── css/
│       └── custom.css         # Estilos personalizados
├── requirements.txt           # Dependencias Python
├── config.py                 # Configuración
├── STRIPE_SETUP.md          # Guía de configuración de Stripe
└── README.md                # Este archivo
```

## 🛠️ Instalación

### 1. Clonar el repositorio
```bash
git clone https://github.com/shidalgo0925/MembresiaRelatic.git
cd MembresiaRelatic
```

### 2. Crear entorno virtual
```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Configurar variables de entorno
Crear archivo `.env`:
```env
SECRET_KEY=tu_clave_secreta_aqui
STRIPE_SECRET_KEY=sk_test_tu_clave_stripe
STRIPE_PUBLISHABLE_KEY=pk_test_tu_clave_stripe
STRIPE_WEBHOOK_SECRET=whsec_tu_webhook_secret
MAIL_USERNAME=tu_email@gmail.com
MAIL_PASSWORD=tu_contraseña_de_aplicacion
```

### 5. Ejecutar la aplicación
```bash
cd backend
python app.py
```

La aplicación estará disponible en `http://localhost:8080`

## 🔧 Configuración

### Stripe
1. Crear cuenta en [Stripe](https://stripe.com)
2. Obtener claves de API (modo test)
3. Configurar webhook: `http://tu-dominio.com/stripe-webhook`
4. Ver `STRIPE_SETUP.md` para instrucciones detalladas

### Base de Datos
- **Desarrollo**: SQLite (automático)
- **Producción**: PostgreSQL (configurar `DATABASE_URL`)

### Email
- Configurar SMTP (Gmail recomendado)
- Usar contraseña de aplicación para Gmail

## 📱 Funcionalidades

### Para Usuarios
- ✅ Registro e inicio de sesión
- ✅ Dashboard personalizado
- ✅ Compra de membresías (3 planes)
- ✅ Formulario de suscripción adicional ($30)
- ✅ Visualización de beneficios
- ✅ Gestión de perfil

### Para Administradores
- ✅ Panel de administración (pendiente)
- ✅ Gestión de usuarios
- ✅ Reportes de pagos
- ✅ Configuración de beneficios

## 🎨 Diseño

- **Colores**: Paleta oficial de RelaticPanama
- **Responsive**: Compatible con móviles y tablets
- **Logo**: SVG personalizado integrado
- **Iconos**: Font Awesome

## 🔒 Seguridad

- Autenticación con Flask-Login
- Contraseñas hasheadas con Werkzeug
- Validación de formularios
- Protección CSRF
- Variables de entorno para claves sensibles

## 📊 Base de Datos

### Modelos
- **User**: Usuarios del sistema
- **Membership**: Membresías (sistema anterior)
- **Subscription**: Suscripciones activas
- **Payment**: Registro de pagos
- **Benefit**: Beneficios por tipo de membresía

## 🚀 Despliegue

### GCP (Google Cloud Platform)
1. Crear instancia Compute Engine
2. Configurar firewall (puerto 8080)
3. Instalar dependencias
4. Configurar variables de entorno
5. Ejecutar con Gunicorn

### Comando de producción
```bash
gunicorn -w 4 -b 0.0.0.0:8080 backend.app:app
```

## 📞 Soporte

- **Email**: administracion@relaticpanama.org
- **Desarrollador**: Sistema desarrollado para RelaticPanama

## 📄 Licencia

Este proyecto es propiedad de RelaticPanama. Todos los derechos reservados.

---

**RelaticPanama** - Red Latinoamericana de Investigaciones Cualitativas
