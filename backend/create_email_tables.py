#!/usr/bin/env python3
"""
Script para crear las tablas de email en la base de datos
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importar después de agregar al path
from app import app, db, EmailConfig, EmailLog, EmailTemplate, NotificationSettings

with app.app_context():
    print("📦 Creando tablas de email en la base de datos...")
    try:
        # Crear todas las tablas
        db.create_all()
        print("✅ Tablas creadas exitosamente")
        
        # Verificar que las tablas existen
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        email_tables = [t for t in tables if 'email' in t.lower() or 'notification' in t.lower()]
        print(f"\n📋 Tablas de email encontradas: {', '.join(email_tables)}")
        
        # Verificar si hay configuración
        config = EmailConfig.query.first()
        if config:
            print(f"\n✅ Configuración encontrada:")
            print(f"   Servidor: {config.mail_server}")
            print(f"   Puerto: {config.mail_port}")
            print(f"   Usuario: {config.mail_username or '(no configurado)'}")
            print(f"   Remitente: {config.mail_default_sender}")
            print(f"   Activa: {config.is_active}")
        else:
            print("\n⚠️ No hay configuración de email en la base de datos")
            print("   Necesitas configurar el email desde /admin/email")
        
        print("\n✨ Proceso completado!")
        
    except Exception as e:
        print(f"❌ Error al crear las tablas: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

