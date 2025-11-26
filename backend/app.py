#!/usr/bin/env python3
"""
Sistema de Membresía RelaticPanama
Backend Flask para gestión de usuarios y membresías
"""

import sys
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
import os
import secrets
import stripe
from flask_mail import Mail, Message

# Configuración de la aplicación
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Ensure module alias 'app' points to this instance even when running as __main__
sys.modules.setdefault('app', sys.modules[__name__])
app.config['SECRET_KEY'] = secrets.token_hex(16)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///relaticpanama.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configuración de Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_your_stripe_secret_key_here')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', 'pk_test_your_stripe_publishable_key_here')

# Configuración de Mail
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD', 'your_app_password')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@relaticpanama.org')

# Inicialización de extensiones
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
mail = Mail(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# Modelos de la base de datos
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    first_name = db.Column(db.String(50), nullable=False)
    last_name = db.Column(db.String(50), nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)  # Campo para administradores
    is_advisor = db.Column(db.Boolean, default=False)  # Campo para asesores que atienden citas
    
    # Relación con membresías
    memberships = db.relationship('Membership', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_active_membership(self):
        # Buscar suscripción activa primero
        active_subscription = Subscription.query.filter_by(
            user_id=self.id, 
            status='active'
        ).filter(Subscription.end_date > datetime.utcnow()).first()
        
        if active_subscription:
            return active_subscription
        
        # Fallback al sistema anterior si existe
        return Membership.query.filter_by(user_id=self.id, is_active=True).first()

class Membership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    membership_type = db.Column(db.String(50), nullable=False)  # 'basic', 'pro', 'premium', 'deluxe'
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    payment_status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'failed'
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_currently_active(self):
        """Verificar si la membresía está actualmente activa"""
        return self.is_active and datetime.utcnow() <= self.end_date

class Benefit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    membership_type = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    stripe_payment_intent_id = db.Column(db.String(100), unique=True, nullable=False)
    amount = db.Column(db.Integer, nullable=False)  # Amount in cents
    currency = db.Column(db.String(3), default='usd')
    status = db.Column(db.String(20), default='pending')  # pending, succeeded, failed
    membership_type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('payments', lazy=True))

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_id = db.Column(db.Integer, db.ForeignKey('payment.id'), nullable=False)
    membership_type = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, expired, cancelled
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    auto_renew = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = db.relationship('User', backref=db.backref('subscriptions', lazy=True))
    payment = db.relationship('Payment', backref=db.backref('subscription', uselist=False))
    
    def is_currently_active(self):
        """Verificar si la suscripción está actualmente activa"""
        return self.status == 'active' and datetime.utcnow() <= self.end_date
    
    @property
    def is_active(self):
        """Propiedad para compatibilidad con Membership"""
        return self.is_currently_active()

# Modelos de Eventos
class Event(db.Model):
    """Modelo para eventos/citas"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(200), unique=True, nullable=False)
    summary = db.Column(db.Text)
    description = db.Column(db.Text)
    category = db.Column(db.String(50), default='general')
    format = db.Column(db.String(50), default='virtual')  # virtual, presencial, híbrido
    tags = db.Column(db.String(500))
    base_price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='USD')
    registration_url = db.Column(db.String(500))
    contact_email = db.Column(db.String(120))
    contact_phone = db.Column(db.String(20))
    location = db.Column(db.String(200))
    country = db.Column(db.String(100))
    is_virtual = db.Column(db.Boolean, default=False)
    has_certificate = db.Column(db.Boolean, default=False)
    certificate_instructions = db.Column(db.Text)
    capacity = db.Column(db.Integer, default=0)
    visibility = db.Column(db.String(20), default='members')  # members, public
    publish_status = db.Column(db.String(20), default='draft')  # draft, published, archived
    featured = db.Column(db.Boolean, default=False)
    start_date = db.Column(db.DateTime, nullable=False)
    end_date = db.Column(db.DateTime, nullable=False)
    registration_deadline = db.Column(db.DateTime)
    cover_image = db.Column(db.String(500))
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relaciones
    images = db.relationship('EventImage', backref='event', lazy=True, cascade='all, delete-orphan')
    discounts = db.relationship('EventDiscount', backref='event', lazy=True, cascade='all, delete-orphan')
    creator = db.relationship('User', backref='created_events')
    
    def cover_url(self):
        """Retorna la URL de la imagen de portada"""
        if self.cover_image:
            return self.cover_image
        return '/static/images/default-event.jpg'
    
    def pricing_for_membership(self, membership_type=None):
        """Calcula el precio final según el tipo de membresía"""
        base_price = self.base_price or 0.0
        discount = None
        final_price = base_price
        
        if membership_type:
            # Buscar descuento aplicable para este tipo de membresía
            event_discount = EventDiscount.query.join(Discount).filter(
                EventDiscount.event_id == self.id,
                Discount.membership_tier == membership_type,
                Discount.is_active == True
            ).order_by(EventDiscount.priority.asc()).first()
            
            if event_discount:
                discount = event_discount.discount
                if discount.discount_type == 'percentage':
                    final_price = base_price * (1 - discount.value / 100)
                elif discount.discount_type == 'fixed':
                    final_price = max(0, base_price - discount.value)
        
        return {
            'base_price': base_price,
            'final_price': final_price,
            'discount': discount
        }

class EventImage(db.Model):
    """Imágenes de galería para eventos"""
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    sort_order = db.Column(db.Integer, default=0)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Discount(db.Model):
    """Descuentos reutilizables"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    code = db.Column(db.String(50), unique=True)
    description = db.Column(db.Text)
    discount_type = db.Column(db.String(20), default='percentage')  # percentage, fixed
    value = db.Column(db.Float, nullable=False)
    membership_tier = db.Column(db.String(50))  # basic, pro, premium, deluxe
    category = db.Column(db.String(50), default='event')
    applies_automatically = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    max_uses = db.Column(db.Integer)
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con eventos
    events = db.relationship('EventDiscount', backref='discount', lazy=True)

class EventDiscount(db.Model):
    """Relación muchos a muchos entre eventos y descuentos"""
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    discount_id = db.Column(db.Integer, db.ForeignKey('discount.id'), nullable=False)
    priority = db.Column(db.Integer, default=1)  # Orden de aplicación si hay múltiples
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Modelos de Citas / Appointments
# ---------------------------------------------------------------------------
class Advisor(db.Model):
    """Perfil de asesores internos que atienden citas."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, unique=True)
    headline = db.Column(db.String(120))
    bio = db.Column(db.Text)
    specializations = db.Column(db.Text)
    meeting_url = db.Column(db.String(255))
    photo_url = db.Column(db.String(255))
    average_response_time = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('advisor_profile', uselist=False))
    advisor_assignments = db.relationship('AppointmentAdvisor', backref='advisor', lazy=True, cascade='all, delete-orphan')
    availability = db.relationship('AdvisorAvailability', backref='advisor', lazy=True, cascade='all, delete-orphan')
    slots = db.relationship('AppointmentSlot', backref='advisor', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='advisor_profile', lazy=True)


class AppointmentType(db.Model):
    """Servicios configurables que pueden reservar los miembros."""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    service_category = db.Column(db.String(100))
    duration_minutes = db.Column(db.Integer, default=60)
    is_group_allowed = db.Column(db.Boolean, default=False)
    max_participants = db.Column(db.Integer, default=1)
    base_price = db.Column(db.Float, default=0.0)
    currency = db.Column(db.String(3), default='USD')
    is_virtual = db.Column(db.Boolean, default=True)
    requires_confirmation = db.Column(db.Boolean, default=True)
    color_tag = db.Column(db.String(20), default='#0d6efd')
    icon = db.Column(db.String(50), default='fa-calendar-check')
    display_order = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    advisor_assignments = db.relationship('AppointmentAdvisor', backref='appointment_type', lazy=True, cascade='all, delete-orphan')
    pricing_rules = db.relationship('AppointmentPricing', backref='appointment_type', lazy=True, cascade='all, delete-orphan')
    slots = db.relationship('AppointmentSlot', backref='appointment_type', lazy=True, cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='appointment_type', lazy=True)

    def duration(self):
        return timedelta(minutes=self.duration_minutes or 60)

    def pricing_for_membership(self, membership_type=None):
        """Calcula el precio final considerando reglas por membresía."""
        base_price = self.base_price or 0.0
        final_price = base_price
        discount_percentage = 0.0
        is_included = False
        rule = None

        if membership_type:
            rule = AppointmentPricing.query.filter_by(
                appointment_type_id=self.id,
                membership_type=membership_type,
                is_active=True
            ).first()

        if rule:
            if rule.is_included:
                final_price = 0.0
                is_included = True
            elif rule.price is not None:
                final_price = rule.price
            elif rule.discount_percentage:
                discount_percentage = rule.discount_percentage
                final_price = max(0.0, base_price * (1 - discount_percentage / 100))

        return {
            'base_price': base_price,
            'final_price': final_price,
            'discount_percentage': discount_percentage,
            'is_included': is_included,
            'rule': rule
        }


class AppointmentAdvisor(db.Model):
    """Asignación de asesores a tipos de cita."""
    id = db.Column(db.Integer, primary_key=True)
    appointment_type_id = db.Column(db.Integer, db.ForeignKey('appointment_type.id'), nullable=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    priority = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('appointment_type_id', 'advisor_id', name='uq_type_advisor'),
    )


class AdvisorAvailability(db.Model):
    """Bloques semanales de disponibilidad declarados por cada asesor."""
    id = db.Column(db.Integer, primary_key=True)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)  # 0 = lunes ... 6 = domingo
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    timezone = db.Column(db.String(50), default='America/Panama')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.CheckConstraint('end_time > start_time', name='ck_availability_time_window'),
    )


class AppointmentPricing(db.Model):
    """Reglas de precio/descuento por tipo de membresía."""
    id = db.Column(db.Integer, primary_key=True)
    appointment_type_id = db.Column(db.Integer, db.ForeignKey('appointment_type.id'), nullable=False)
    membership_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float)
    discount_percentage = db.Column(db.Float, default=0.0)
    is_included = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('appointment_type_id', 'membership_type', name='uq_pricing_membership'),
    )


class AppointmentSlot(db.Model):
    """Slots concretos de tiempo que pueden reservar los miembros."""
    id = db.Column(db.Integer, primary_key=True)
    appointment_type_id = db.Column(db.Integer, db.ForeignKey('appointment_type.id'), nullable=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, default=1)
    reserved_seats = db.Column(db.Integer, default=0)
    is_available = db.Column(db.Boolean, default=True)
    is_auto_generated = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user = db.relationship('User', backref='appointment_slots_created', foreign_keys=[created_by])
    appointment = db.relationship('Appointment', backref='slot', uselist=False)

    __table_args__ = (
        db.CheckConstraint('capacity >= 1', name='ck_slot_capacity_positive'),
        db.CheckConstraint('end_datetime > start_datetime', name='ck_slot_time_window'),
    )

    def remaining_seats(self):
        return max(0, (self.capacity or 1) - (self.reserved_seats or 0))


class Appointment(db.Model):
    """Reservas realizadas por miembros."""
    id = db.Column(db.Integer, primary_key=True)
    reference = db.Column(db.String(40), unique=True, default=lambda: secrets.token_hex(4).upper())
    appointment_type_id = db.Column(db.Integer, db.ForeignKey('appointment_type.id'), nullable=False)
    advisor_id = db.Column(db.Integer, db.ForeignKey('advisor.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('appointment_slot.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    membership_type = db.Column(db.String(50))
    is_group = db.Column(db.Boolean, default=False)
    start_datetime = db.Column(db.DateTime, nullable=False)
    end_datetime = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, completed
    advisor_confirmed = db.Column(db.Boolean, default=False)
    advisor_confirmed_at = db.Column(db.DateTime)
    cancellation_reason = db.Column(db.Text)
    base_price = db.Column(db.Float, default=0.0)
    final_price = db.Column(db.Float, default=0.0)
    discount_applied = db.Column(db.Float, default=0.0)
    payment_status = db.Column(db.String(20), default='pending')  # pending, paid, refunded
    user_notes = db.Column(db.Text)
    advisor_notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = db.relationship('User', backref='appointments')
    participants = db.relationship('AppointmentParticipant', backref='appointment', lazy=True, cascade='all, delete-orphan')

    def can_user_cancel(self):
        """Permite cancelar si faltan al menos 12 horas."""
        return self.start_datetime - datetime.utcnow() > timedelta(hours=12)


class AppointmentParticipant(db.Model):
    """Participantes adicionales (para citas grupales)."""
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointment.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='appointment_participations')
    invited_by = db.relationship('User', foreign_keys=[invited_by_id], backref='appointment_invitations', lazy=True)


class ActivityLog(db.Model):
    """Log de actividades administrativas"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # create_event, update_event, etc.
    entity_type = db.Column(db.String(50), nullable=False)  # event, discount, user, etc.
    entity_id = db.Column(db.Integer)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    user = db.relationship('User', backref='activity_logs')
    
    @classmethod
    def log_activity(cls, user_id, action, entity_type, entity_id, description, request=None):
        """Método helper para registrar actividades"""
        log = cls(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent') if request else None
        )
        db.session.add(log)
        return log

# Función helper para validar archivos
def allowed_file(filename):
    """Verifica si el archivo tiene una extensión permitida"""
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configuración del login manager
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rutas principales
@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevos usuarios"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form.get('phone', '')
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            flash('El correo electrónico ya está registrado.', 'error')
            return render_template('register.html')
        
        # Crear nuevo usuario
        user = User(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registro exitoso. Por favor, inicia sesión.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Inicio de sesión"""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        else:
            flash('Credenciales inválidas.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión exitosamente.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """Panel de control del usuario"""
    active_membership = current_user.get_active_membership()
    benefits = Benefit.query.filter_by(is_active=True).all()
    
    # Calcular días desde inicio y días restantes
    days_active = None
    days_remaining = None
    now = datetime.utcnow()
    
    if active_membership:
        if active_membership.start_date:
            days_active = (now - active_membership.start_date).days
        if active_membership.end_date:
            days_remaining = (active_membership.end_date - now).days
    
    return render_template('dashboard.html', 
                         membership=active_membership, 
                         benefits=benefits,
                         days_active=days_active,
                         days_remaining=days_remaining,
                         now=now)

@app.route('/membership')
@login_required
def membership():
    """Página de membresía"""
    active_membership = current_user.get_active_membership()
    return render_template('membership.html', membership=active_membership)

@app.route('/subscription')
@login_required
def subscription_form():
    """Formulario de suscripción adicional (membresía $30)"""
    return render_template('subscription_form.html')

@app.route('/benefits')
@login_required
def benefits():
    """Página de beneficios"""
    active_membership = current_user.get_active_membership()
    if not active_membership:
        flash('Necesitas una membresía activa para acceder a los beneficios.', 'warning')
        return redirect(url_for('membership'))
    
    benefits = Benefit.query.filter_by(
        membership_type=active_membership.membership_type,
        is_active=True
    ).all()
    
    return render_template('benefits.html', benefits=benefits)

@app.route('/profile')
@login_required
def profile():
    """Perfil del usuario"""
    return render_template('profile.html')

@app.route('/services')
@login_required
def services():
    """Módulo de Servicios"""
    active_membership = current_user.get_active_membership()
    return render_template('services.html', membership=active_membership)

@app.route('/office365')
@login_required
def office365():
    """Módulo de Office 365"""
    active_membership = current_user.get_active_membership()
    return render_template('office365.html', membership=active_membership)

@app.route('/foros')
@login_required
def foros():
    """Módulo de Foros para miembros"""
    active_membership = current_user.get_active_membership()
    if not active_membership:
        flash('Necesitas una membresía activa para acceder a los Foros.', 'warning')
        return redirect(url_for('membership'))
    return render_template('foros.html', membership=active_membership)

@app.route('/grupos')
@login_required
def grupos():
    """Módulo de Grupos para miembros"""
    active_membership = current_user.get_active_membership()
    if not active_membership:
        flash('Necesitas una membresía activa para acceder a los Grupos.', 'warning')
        return redirect(url_for('membership'))
    return render_template('grupos.html', membership=active_membership)

@app.route('/settings')
@login_required
def settings():
    """Módulo de Configuración"""
    return render_template('settings.html')

@app.route('/notifications')
@login_required
def notifications():
    """Módulo de Notificaciones"""
    return render_template('notifications.html')

@app.route('/help')
@login_required
def help():
    """Módulo de Ayuda"""
    return render_template('help.html')

# Rutas de pago
@app.route('/checkout/<membership_type>')
@login_required
def checkout(membership_type):
    """Página de checkout para pagos"""
    if membership_type not in ['basic', 'pro', 'premium', 'deluxe']:
        flash('Tipo de membresía inválido.', 'error')
        return redirect(url_for('membership'))
    
    # Precios en centavos
    prices = {
        'basic': 0,         # $0.00 - Plan gratuito
        'pro': 6000,        # $60.00
        'premium': 12000,   # $120.00
        'deluxe': 20000     # $200.00
    }
    
    amount = prices[membership_type]
    
    return render_template('checkout.html', 
                         membership_type=membership_type,
                         amount=amount,
                         stripe_publishable_key=STRIPE_PUBLISHABLE_KEY)

@app.route('/create-payment-intent', methods=['POST'])
@login_required
def create_payment_intent():
    """Crear Payment Intent de Stripe (Modo Demo)"""
    try:
        data = request.get_json()
        membership_type = data['membership_type']
        amount = data['amount']
        
        # Modo Demo - Simular pago exitoso
        demo_mode = True  # Cambiar a False cuando tengas Stripe configurado
        
        if demo_mode:
            # Simular Payment Intent
            fake_intent_id = f"pi_demo_{current_user.id}_{datetime.utcnow().timestamp()}"
            
            # Guardar en la base de datos
            payment = Payment(
                user_id=current_user.id,
                stripe_payment_intent_id=fake_intent_id,
                amount=amount,
                membership_type=membership_type,
                status='succeeded'  # Simular pago exitoso
            )
            db.session.add(payment)
            db.session.commit()
            
            # Crear suscripción automáticamente
            end_date = datetime.utcnow() + timedelta(days=365)
            subscription = Subscription(
                user_id=current_user.id,
                payment_id=payment.id,
                membership_type=membership_type,
                status='active',
                end_date=end_date
            )
            db.session.add(subscription)
            db.session.commit()
            
            return jsonify({
                'client_secret': 'demo_client_secret',
                'payment_id': payment.id,
                'demo_mode': True
            })
        else:
            # Modo real con Stripe
            intent = stripe.PaymentIntent.create(
                amount=amount,
                currency='usd',
                metadata={
                    'user_id': current_user.id,
                    'membership_type': membership_type
                }
            )
            
            # Guardar en la base de datos
            payment = Payment(
                user_id=current_user.id,
                stripe_payment_intent_id=intent.id,
                amount=amount,
                membership_type=membership_type,
                status='pending'
            )
            db.session.add(payment)
            db.session.commit()
            
            return jsonify({
                'client_secret': intent.client_secret,
                'payment_id': payment.id,
                'demo_mode': False
            })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/payment-success')
@login_required
def payment_success():
    """Página de éxito del pago"""
    payment_id = request.args.get('payment_id')
    if payment_id:
        payment = Payment.query.get(payment_id)
        if payment and payment.user_id == current_user.id:
            return render_template('payment_success.html', payment=payment)
    
    flash('Información de pago no encontrada.', 'error')
    return redirect(url_for('membership'))

@app.route('/payment-cancel')
@login_required
def payment_cancel():
    """Página de cancelación del pago"""
    flash('El pago fue cancelado. Puedes intentar nuevamente.', 'warning')
    return redirect(url_for('membership'))

@app.route('/stripe-webhook', methods=['POST'])
def stripe_webhook():
    """Webhook de Stripe para confirmar pagos"""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET', 'whsec_test')
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400
    
    # Manejar el evento
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        handle_successful_payment(payment_intent)
    
    return jsonify({'status': 'success'})

def handle_successful_payment(payment_intent):
    """Manejar pago exitoso"""
    try:
        # Buscar el pago en la base de datos
        payment = Payment.query.filter_by(
            stripe_payment_intent_id=payment_intent['id']
        ).first()
        
        if payment:
            # Actualizar estado del pago
            payment.status = 'succeeded'
            db.session.commit()
            
            # Crear suscripción
            end_date = datetime.utcnow() + timedelta(days=365)  # 1 año
            subscription = Subscription(
                user_id=payment.user_id,
                payment_id=payment.id,
                membership_type=payment.membership_type,
                status='active',
                end_date=end_date
            )
            db.session.add(subscription)
            db.session.commit()
            
            # Enviar email de confirmación
            send_payment_confirmation_email(payment.user, payment, subscription)
            
    except Exception as e:
        print(f"Error handling payment: {e}")

def send_payment_confirmation_email(user, payment, subscription):
    """Enviar email de confirmación de pago"""
    try:
        msg = Message(
            subject='Confirmación de Pago - RelaticPanama',
            recipients=[user.email],
            html=f"""
            <h2>¡Pago Confirmado!</h2>
            <p>Hola {user.first_name},</p>
            <p>Tu pago por la membresía {payment.membership_type.title()} ha sido procesado exitosamente.</p>
            <p><strong>Detalles del pago:</strong></p>
            <ul>
                <li>Membresía: {payment.membership_type.title()}</li>
                <li>Monto: ${payment.amount / 100:.2f}</li>
                <li>Fecha: {payment.created_at.strftime('%d/%m/%Y')}</li>
                <li>Válida hasta: {subscription.end_date.strftime('%d/%m/%Y')}</li>
            </ul>
            <p>Ya puedes acceder a todos los beneficios de tu membresía.</p>
            <p>¡Gracias por ser parte de RelaticPanama!</p>
            """
        )
        mail.send(msg)
    except Exception as e:
        print(f"Error sending email: {e}")

@app.route('/api/user/membership')
@login_required
def api_user_membership():
    """API para obtener información de membresía del usuario"""
    membership = current_user.get_active_membership()
    if membership:
        return jsonify({
            'type': membership.membership_type,
            'start_date': membership.start_date.isoformat(),
            'end_date': membership.end_date.isoformat(),
            'is_active': membership.is_active,
            'payment_status': membership.payment_status
        })
    return jsonify({'error': 'No active membership found'}), 404

# Rutas de administración
def admin_required(f):
    """Decorador para requerir permisos de administrador"""
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Panel de administración principal"""
    total_users = User.query.count()
    total_memberships = Membership.query.count()
    active_memberships = Membership.query.filter_by(is_active=True).count()
    total_payments = Payment.query.filter_by(status='succeeded').count()
    total_revenue = sum([p.amount for p in Payment.query.filter_by(status='succeeded').all()]) / 100
    
    # Usuarios recientes
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Membresías recientes
    recent_memberships = Membership.query.order_by(Membership.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         total_users=total_users,
                         total_memberships=total_memberships,
                         active_memberships=active_memberships,
                         total_payments=total_payments,
                         total_revenue=total_revenue,
                         recent_users=recent_users,
                         recent_memberships=recent_memberships)

@app.route('/admin/users')
@admin_required
def admin_users():
    """Gestión de usuarios"""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@app.route('/admin/users/<int:user_id>/update', methods=['POST'])
@admin_required
def admin_update_user(user_id):
    """Actualizar atributos básicos del usuario (admin, asesor, estado)."""
    user = User.query.get_or_404(user_id)
    first_name = request.form.get('first_name', '').strip()
    last_name = request.form.get('last_name', '').strip()
    phone = request.form.get('phone', '').strip()

    if first_name:
        user.first_name = first_name
    if last_name:
        user.last_name = last_name
    user.phone = phone or None

    user.is_active = bool(request.form.get('is_active'))
    user.is_admin = bool(request.form.get('is_admin'))
    wants_advisor = bool(request.form.get('is_advisor'))

    if wants_advisor and not user.is_advisor:
        user.is_advisor = True
        if not user.advisor_profile:
            new_profile = Advisor(
                user_id=user.id,
                headline=request.form.get('advisor_headline', '').strip() or 'Asesor RELATIC',
                specializations=request.form.get('advisor_specializations', '').strip(),
                meeting_url=request.form.get('advisor_meeting_url', '').strip(),
            )
            db.session.add(new_profile)
    elif not wants_advisor and user.is_advisor:
        user.is_advisor = False
        if user.advisor_profile:
            db.session.delete(user.advisor_profile)

    db.session.commit()
    flash('Usuario actualizado correctamente.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/memberships')
@admin_required
def admin_memberships():
    """Gestión de membresías"""
    memberships = Membership.query.order_by(Membership.created_at.desc()).all()
    return render_template('admin/memberships.html', memberships=memberships)

# Registrar blueprints de eventos
try:
    from event_routes import events_bp, admin_events_bp, events_api_bp
    app.register_blueprint(events_bp)
    app.register_blueprint(admin_events_bp)
    app.register_blueprint(events_api_bp)
except ImportError as e:
    print(f"Warning: No se pudieron registrar los blueprints de eventos: {e}")

# Registrar blueprints de citas/appointments
try:
    from appointment_routes import appointments_bp, admin_appointments_bp, appointments_api_bp
    app.register_blueprint(appointments_bp)
    app.register_blueprint(admin_appointments_bp)
    app.register_blueprint(appointments_api_bp)
except ImportError as e:
    print(f"Warning: No se pudieron registrar los blueprints de citas: {e}")

# Funciones de utilidad
def create_sample_data():
    """Crear datos de ejemplo"""
    # Crear beneficios de ejemplo
    benefits = [
        Benefit(name='Acceso a Revistas', description='Acceso completo a la biblioteca de revistas especializadas', membership_type='basic'),
        Benefit(name='Base de Datos', description='Acceso a bases de datos de investigación', membership_type='basic'),
        Benefit(name='Asesoría de Publicación', description='Sesiones de asesoría para publicaciones académicas', membership_type='premium'),
        Benefit(name='Soporte Prioritario', description='Soporte técnico prioritario', membership_type='premium'),
    ]
    
    for benefit in benefits:
        if not Benefit.query.filter_by(name=benefit.name).first():
            db.session.add(benefit)
    
    db.session.commit()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        create_sample_data()
    
    app.run(host='0.0.0.0', port=9000, debug=True)
