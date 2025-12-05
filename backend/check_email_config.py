#!/usr/bin/env python3
"""
Script para verificar la configuración de email y los logs
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, EmailConfig, EmailLog
from datetime import datetime, timedelta

with app.app_context():
    print("\n" + "="*70)
    print("VERIFICACIÓN DE CONFIGURACIÓN DE EMAIL")
    print("="*70)
    
    # Verificar configuración activa
    config = EmailConfig.get_active_config()
    if config:
        print("\n✅ CONFIGURACIÓN ACTIVA:")
        print(f"   Servidor: {config.mail_server}")
        print(f"   Puerto: {config.mail_port}")
        print(f"   TLS: {config.mail_use_tls}")
        print(f"   SSL: {config.mail_use_ssl}")
        print(f"   Usuario: {config.mail_username or '(no configurado)'}")
        print(f"   Remitente: {config.mail_default_sender}")
        print(f"   Usa variables de entorno: {config.use_environment_variables}")
        print(f"   Activa: {config.is_active}")
        print(f"   Última actualización: {config.updated_at}")
    else:
        print("\n❌ NO HAY CONFIGURACIÓN ACTIVA EN LA BASE DE DATOS")
    
    # Verificar configuración de Flask
    print("\n📧 CONFIGURACIÓN ACTUAL DE FLASK:")
    print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER', 'no configurado')}")
    print(f"   MAIL_PORT: {app.config.get('MAIL_PORT', 'no configurado')}")
    print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'no configurado')}")
    print(f"   MAIL_USE_SSL: {app.config.get('MAIL_USE_SSL', 'no configurado')}")
    print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'no configurado')}")
    print(f"   MAIL_PASSWORD: {'***' if app.config.get('MAIL_PASSWORD') else 'no configurado'}")
    print(f"   MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER', 'no configurado')}")
    
    # Verificar logs de email recientes
    print("\n" + "="*70)
    print("LOGS DE EMAIL (ÚLTIMOS 10)")
    print("="*70)
    
    recent_logs = EmailLog.query.order_by(EmailLog.created_at.desc()).limit(10).all()
    if recent_logs:
        for log in recent_logs:
            status_icon = "✅" if log.status == 'sent' else "❌"
            print(f"\n{status_icon} [{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}]")
            print(f"   Tipo: {log.email_type}")
            print(f"   Para: {log.recipient_email}")
            print(f"   Asunto: {log.subject[:60]}...")
            print(f"   Estado: {log.status}")
            if log.error_message:
                print(f"   Error: {log.error_message[:100]}...")
            if log.sent_at:
                print(f"   Enviado: {log.sent_at.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("\n⚠️ No hay logs de email en la base de datos")
    
    # Estadísticas
    print("\n" + "="*70)
    print("ESTADÍSTICAS")
    print("="*70)
    
    total = EmailLog.query.count()
    sent = EmailLog.query.filter_by(status='sent').count()
    failed = EmailLog.query.filter_by(status='failed').count()
    
    print(f"   Total de emails: {total}")
    print(f"   Enviados exitosamente: {sent}")
    print(f"   Fallidos: {failed}")
    
    # Verificar últimos 24 horas
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_total = EmailLog.query.filter(EmailLog.created_at >= yesterday).count()
    recent_sent = EmailLog.query.filter(EmailLog.created_at >= yesterday, EmailLog.status == 'sent').count()
    recent_failed = EmailLog.query.filter(EmailLog.created_at >= yesterday, EmailLog.status == 'failed').count()
    
    print(f"\n   Últimas 24 horas:")
    print(f"   Total: {recent_total}")
    print(f"   Enviados: {recent_sent}")
    print(f"   Fallidos: {recent_failed}")
    
    print("\n" + "="*70)
    print("FIN DE VERIFICACIÓN")
    print("="*70 + "\n")

