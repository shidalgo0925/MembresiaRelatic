#!/usr/bin/env python3
"""
Script para enviar un correo de bienvenida de prueba
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, EmailConfig, get_welcome_email
from email_service import EmailService
from flask_mail import Mail

class MockUser:
    """Usuario de prueba para el email de bienvenida"""
    def __init__(self, email, first_name="Usuario", last_name="Prueba"):
        self.id = 1
        self.first_name = first_name
        self.last_name = last_name
        self.email = email

with app.app_context():
    print("="*70)
    print("ENVÍO DE CORREO DE BIENVENIDA DE PRUEBA")
    print("="*70)
    
    # Aplicar configuración
    config = EmailConfig.get_active_config()
    if config:
        config.apply_to_app(app)
        print("\n✅ Configuración aplicada")
        print(f"   Servidor: {app.config.get('MAIL_SERVER')}")
        print(f"   Usuario: {app.config.get('MAIL_USERNAME')}")
        print(f"   Remitente: {app.config.get('MAIL_DEFAULT_SENDER')}")
    else:
        print("\n❌ No hay configuración")
        sys.exit(1)
    
    # Inicializar servicio
    mail = Mail(app)
    email_service = EmailService(mail)
    
    # Crear usuario de prueba
    test_email = "shidalgo0925@gmail.com"
    user = MockUser(test_email, "Usuario", "Prueba")
    
    print(f"\n📧 Generando email de bienvenida para: {test_email}")
    
    try:
        # Generar HTML del email de bienvenida
        html_content = get_welcome_email(user)
        print("✅ Template de bienvenida generado correctamente")
        
        # Enviar email
        print(f"\n📤 Enviando email de bienvenida...")
        success = email_service.send_email(
            subject='Bienvenido a RelaticPanama',
            recipients=[test_email],
            html_content=html_content,
            email_type='welcome',
            related_entity_type='user',
            related_entity_id=user.id,
            recipient_id=user.id,
            recipient_name=f"{user.first_name} {user.last_name}"
        )
        
        if success:
            print(f"\n✅ Email de bienvenida enviado exitosamente a {test_email}")
            print("\n📬 Revisa tu bandeja de entrada (y spam si no lo ves)")
        else:
            print(f"\n❌ Error al enviar email de bienvenida")
    except Exception as e:
        print(f"\n❌ Excepción al enviar email: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*70)

