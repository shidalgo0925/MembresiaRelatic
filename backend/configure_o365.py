#!/usr/bin/env python3
"""
Script para configurar Office 365 en la base de datos
"""

import sys
import os

# Agregar el directorio backend al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, EmailConfig
from datetime import datetime

def configure_o365():
    """Configurar Office 365 en la base de datos"""
    with app.app_context():
        # Desactivar todas las configuraciones anteriores
        EmailConfig.query.update({'is_active': False})
        
        # Buscar si existe una configuración
        config = EmailConfig.query.first()
        
        if not config:
            # Crear nueva configuración
            config = EmailConfig(
                mail_server='smtp.office365.com',
                mail_port=587,
                mail_use_tls=True,
                mail_use_ssl=False,
                mail_username='info@relaticpanama.org',
                mail_password='Mariachi@0925',
                mail_default_sender='info@relaticpanama.org',
                use_environment_variables=False,
                is_active=True
            )
            db.session.add(config)
            print("✅ Nueva configuración de Office 365 creada")
        else:
            # Actualizar configuración existente
            config.mail_server = 'smtp.office365.com'
            config.mail_port = 587
            config.mail_use_tls = True
            config.mail_use_ssl = False
            config.mail_username = 'info@relaticpanama.org'
            config.mail_password = 'Mariachi@0925'
            config.mail_default_sender = 'info@relaticpanama.org'
            config.use_environment_variables = False
            config.is_active = True
            config.updated_at = datetime.utcnow()
            print("✅ Configuración de Office 365 actualizada")
        
        try:
            db.session.commit()
            print("\n📧 Configuración de Office 365:")
            print(f"   Servidor: {config.mail_server}")
            print(f"   Puerto: {config.mail_port}")
            print(f"   TLS: {config.mail_use_tls}")
            print(f"   Usuario: {config.mail_username}")
            print(f"   Remitente: {config.mail_default_sender}")
            print("\n✅ Configuración guardada exitosamente")
            print("\n⚠️  IMPORTANTE: Reinicia el servidor para aplicar los cambios:")
            print("   sudo systemctl restart membresia-relatic.service")
            return True
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error al guardar configuración: {e}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    configure_o365()


