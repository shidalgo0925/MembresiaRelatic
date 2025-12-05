#!/usr/bin/env python3
"""
Script de diagnóstico completo del sistema de email
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("="*70)
print("DIAGNÓSTICO DEL SISTEMA DE EMAIL")
print("="*70)

try:
    from app import app, db, EmailConfig, EmailLog, NotificationSettings
    from email_service import EmailService
    from flask_mail import Mail
    
    with app.app_context():
        # 1. Verificar tablas
        print("\n1. VERIFICANDO TABLAS...")
        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            required_tables = ['email_config', 'email_log', 'notification_settings']
            for table in required_tables:
                if table in tables:
                    print(f"   ✅ Tabla {table} existe")
                else:
                    print(f"   ❌ Tabla {table} NO existe")
                    print(f"      Creando tabla...")
                    db.create_all()
                    print(f"      ✅ Tabla {table} creada")
        except Exception as e:
            print(f"   ❌ Error verificando tablas: {e}")
        
        # 2. Verificar configuración
        print("\n2. VERIFICANDO CONFIGURACIÓN...")
        config = EmailConfig.get_active_config()
        if config:
            print(f"   ✅ Configuración encontrada:")
            print(f"      Servidor: {config.mail_server}")
            print(f"      Puerto: {config.mail_port}")
            print(f"      TLS: {config.mail_use_tls}")
            print(f"      SSL: {config.mail_use_ssl}")
            print(f"      Usuario: {config.mail_username or '(no configurado)'}")
            print(f"      Remitente: {config.mail_default_sender}")
            print(f"      Usa env vars: {config.use_environment_variables}")
            print(f"      Activa: {config.is_active}")
            
            # Aplicar configuración
            config.apply_to_app(app)
            print(f"\n   ✅ Configuración aplicada a Flask")
        else:
            print("   ❌ NO HAY CONFIGURACIÓN ACTIVA")
            print("   ⚠️  Necesitas configurar el email desde /admin/email")
        
        # 3. Verificar configuración de Flask
        print("\n3. CONFIGURACIÓN ACTUAL DE FLASK:")
        print(f"   MAIL_SERVER: {app.config.get('MAIL_SERVER', 'no configurado')}")
        print(f"   MAIL_PORT: {app.config.get('MAIL_PORT', 'no configurado')}")
        print(f"   MAIL_USE_TLS: {app.config.get('MAIL_USE_TLS', 'no configurado')}")
        print(f"   MAIL_USERNAME: {app.config.get('MAIL_USERNAME', 'no configurado')}")
        print(f"   MAIL_PASSWORD: {'***' if app.config.get('MAIL_PASSWORD') else 'no configurado'}")
        print(f"   MAIL_DEFAULT_SENDER: {app.config.get('MAIL_DEFAULT_SENDER', 'no configurado')}")
        
        # 4. Verificar email_service
        print("\n4. VERIFICANDO SERVICIO DE EMAIL...")
        try:
            mail = Mail(app)
            email_service = EmailService(mail)
            print("   ✅ EmailService inicializado correctamente")
        except Exception as e:
            print(f"   ❌ Error inicializando EmailService: {e}")
        
        # 5. Verificar notificaciones
        print("\n5. VERIFICANDO CONFIGURACIÓN DE NOTIFICACIONES...")
        welcome_setting = NotificationSettings.query.filter_by(notification_type='welcome').first()
        if welcome_setting:
            if welcome_setting.enabled:
                print("   ✅ Notificación 'welcome' está HABILITADA")
            else:
                print("   ❌ Notificación 'welcome' está DESHABILITADA")
        else:
            print("   ⚠️  No hay configuración para 'welcome' (se usará por defecto: HABILITADA)")
        
        # 6. Verificar logs recientes
        print("\n6. LOGS DE EMAIL RECIENTES:")
        recent_logs = EmailLog.query.order_by(EmailLog.created_at.desc()).limit(5).all()
        if recent_logs:
            for log in recent_logs:
                status_icon = "✅" if log.status == 'sent' else "❌"
                print(f"   {status_icon} [{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {log.recipient_email} - {log.status}")
                if log.error_message:
                    print(f"      Error: {log.error_message[:100]}")
        else:
            print("   ⚠️  No hay logs de email")
        
        print("\n" + "="*70)
        print("FIN DEL DIAGNÓSTICO")
        print("="*70)
        
except ImportError as e:
    print(f"\n❌ Error al importar módulos: {e}")
    print("   Asegúrate de tener todas las dependencias instaladas")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ Error durante el diagnóstico: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

