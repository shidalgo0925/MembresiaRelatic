#!/usr/bin/env python3
"""
Script para probar el envío de email directamente
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, EmailConfig
from email_service import EmailService
from flask_mail import Mail

with app.app_context():
    print("="*70)
    print("PRUEBA DE ENVÍO DE EMAIL")
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
    
    # Probar envío
    print("\n📧 Intentando enviar email de prueba...")
    print("   Destinatario: info@relaticpanama.org")
    
    try:
        success = email_service.send_email(
            subject='[PRUEBA] Test de Email - RelaticPanama',
            recipients=['info@relaticpanama.org'],
            html_content='<h1>Email de Prueba</h1><p>Este es un email de prueba para verificar la configuración SMTP.</p>',
            email_type='test',
            recipient_name='Prueba'
        )
        
        if success:
            print("\n✅ Email enviado exitosamente")
        else:
            print("\n❌ Error al enviar email (ver logs)")
    except Exception as e:
        print(f"\n❌ Excepción al enviar email: {e}")
        import traceback
        traceback.print_exc()
    
    # Verificar logs
    print("\n📋 Verificando logs de email...")
    from app import EmailLog
    recent_logs = EmailLog.query.order_by(EmailLog.created_at.desc()).limit(3).all()
    if recent_logs:
        for log in recent_logs:
            status_icon = "✅" if log.status == 'sent' else "❌"
            print(f"   {status_icon} [{log.created_at.strftime('%H:%M:%S')}] {log.recipient_email} - {log.status}")
            if log.error_message:
                print(f"      Error: {log.error_message}")
    else:
        print("   ⚠️  No hay logs recientes")
    
    print("\n" + "="*70)

