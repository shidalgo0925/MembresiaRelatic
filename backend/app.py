#!/usr/bin/env python3
"""
Sistema de Membresía RelaticPanama
Backend Flask para gestión de usuarios y membresías
"""

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
    membership_type = db.Column(db.String(50), nullable=False)  # 'basic', 'premium', 'enterprise'
    start_date = db.Column(db.DateTime, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    payment_status = db.Column(db.String(20), default='pending')  # 'pending', 'paid', 'failed'
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    
    return render_template('dashboard.html', 
                         membership=active_membership, 
                         benefits=benefits)

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

# Rutas de pago
@app.route('/checkout/<membership_type>')
@login_required
def checkout(membership_type):
    """Página de checkout para pagos"""
    if membership_type not in ['basic', 'premium', 'enterprise']:
        flash('Tipo de membresía inválido.', 'error')
        return redirect(url_for('membership'))
    
    # Precios en centavos
    prices = {
        'basic': 7500,      # $75.00
        'premium': 15000,   # $150.00
        'enterprise': 30000 # $300.00
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
