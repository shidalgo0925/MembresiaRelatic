#!/usr/bin/env python3
"""
Script para crear las nuevas tablas en la base de datos
"""
import sys
from pathlib import Path

# Agregar el directorio backend al path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

from app import app, db

with app.app_context():
    print("📦 Creando nuevas tablas en la base de datos...")
    try:
        db.create_all()
        print("✅ Tablas creadas exitosamente:")
        print("   - event_participant")
        print("   - event_speaker")
        print("   - event_certificate")
        print("   - event_workshop")
        print("   - event_topic")
        print("   - event_registration")
        print("\n✨ Proceso completado!")
    except Exception as e:
        print(f"❌ Error al crear las tablas: {e}")
        sys.exit(1)







