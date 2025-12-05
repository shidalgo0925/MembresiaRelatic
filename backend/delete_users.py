#!/usr/bin/env python3
"""
Script para eliminar usuarios y todas sus transacciones relacionadas
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app, db, User, Membership, Subscription, Payment, EventRegistration, EventParticipant, Appointment, Advisor, Notification, EmailLog, ActivityLog, Event

# Emails de usuarios a eliminar
USERS_TO_DELETE = [
    'shidalgo0925@gmail.com',
    'shidalgo@relatic.org',
    'shidalgo0925@outlook.com'
]

def delete_user_and_transactions(email):
    """Eliminar un usuario y todas sus transacciones"""
    user = User.query.filter_by(email=email).first()
    
    if not user:
        print(f"⚠️  Usuario no encontrado: {email}")
        return False
    
    user_name = f"{user.first_name} {user.last_name}"
    user_id = user.id
    
    print(f"\n📋 Eliminando usuario: {user_name} ({email})")
    print(f"   ID: {user_id}")
    
    try:
        # 1. Eliminar membresías
        memberships = Membership.query.filter_by(user_id=user_id).all()
        if memberships:
            print(f"   🗑️  Eliminando {len(memberships)} membresía(s)...")
            for membership in memberships:
                db.session.delete(membership)
        
        # 2. Eliminar suscripciones
        subscriptions = Subscription.query.filter_by(user_id=user_id).all()
        if subscriptions:
            print(f"   🗑️  Eliminando {len(subscriptions)} suscripción(es)...")
            for subscription in subscriptions:
                db.session.delete(subscription)
        
        # 3. Eliminar pagos
        payments = Payment.query.filter_by(user_id=user_id).all()
        if payments:
            print(f"   🗑️  Eliminando {len(payments)} pago(s)...")
            for payment in payments:
                db.session.delete(payment)
        
        # 4. Eliminar registros de eventos
        event_registrations = EventRegistration.query.filter_by(user_id=user_id).all()
        if event_registrations:
            print(f"   🗑️  Eliminando {len(event_registrations)} registro(s) de evento(s)...")
            for registration in event_registrations:
                # Actualizar contador del evento si estaba confirmado
                if registration.registration_status == 'confirmed':
                    event = Event.query.get(registration.event_id)
                    if event and event.registered_count and event.registered_count > 0:
                        event.registered_count -= 1
                db.session.delete(registration)
        
        # 5. Eliminar participantes de eventos
        event_participants = EventParticipant.query.filter_by(user_id=user_id).all()
        if event_participants:
            print(f"   🗑️  Eliminando {len(event_participants)} participante(s) de evento(s)...")
            for participant in event_participants:
                db.session.delete(participant)
        
        # 6. Eliminar citas
        appointments = Appointment.query.filter_by(user_id=user_id).all()
        if appointments:
            print(f"   🗑️  Eliminando {len(appointments)} cita(s)...")
            for appointment in appointments:
                db.session.delete(appointment)
        
        # 7. Eliminar perfil de asesor
        if user.advisor_profile:
            print(f"   🗑️  Eliminando perfil de asesor...")
            db.session.delete(user.advisor_profile)
        
        # 8. Eliminar notificaciones
        notifications = Notification.query.filter_by(user_id=user_id).all()
        if notifications:
            print(f"   🗑️  Eliminando {len(notifications)} notificación(es)...")
            for notification in notifications:
                db.session.delete(notification)
        
        # 9. Eliminar logs de email (solo los relacionados con el usuario)
        email_logs = EmailLog.query.filter_by(recipient_id=user_id).all()
        if email_logs:
            print(f"   🗑️  Eliminando {len(email_logs)} log(s) de email...")
            for email_log in email_logs:
                db.session.delete(email_log)
        
        # 10. Eliminar logs de actividad
        activity_logs = ActivityLog.query.filter_by(user_id=user_id).all()
        if activity_logs:
            print(f"   🗑️  Eliminando {len(activity_logs)} log(s) de actividad...")
            for activity_log in activity_logs:
                db.session.delete(activity_log)
        
        # 11. Limpiar referencias en eventos (no eliminar eventos, solo limpiar referencias)
        events_created = Event.query.filter_by(created_by=user_id).all()
        if events_created:
            print(f"   🔧 Limpiando referencias en {len(events_created)} evento(s) creado(s)...")
            for event in events_created:
                event.created_by = None
        
        events_moderated = Event.query.filter_by(moderator_id=user_id).all()
        if events_moderated:
            print(f"   🔧 Limpiando referencias en {len(events_moderated)} evento(s) moderado(s)...")
            for event in events_moderated:
                event.moderator_id = None
        
        events_administered = Event.query.filter_by(administrator_id=user_id).all()
        if events_administered:
            print(f"   🔧 Limpiando referencias en {len(events_administered)} evento(s) administrado(s)...")
            for event in events_administered:
                event.administrator_id = None
        
        events_speaker = Event.query.filter_by(speaker_id=user_id).all()
        if events_speaker:
            print(f"   🔧 Limpiando referencias en {len(events_speaker)} evento(s) como expositor...")
            for event in events_speaker:
                event.speaker_id = None
        
        # 12. Eliminar el usuario
        print(f"   🗑️  Eliminando usuario...")
        db.session.delete(user)
        
        # Confirmar cambios
        db.session.commit()
        print(f"   ✅ Usuario {user_name} eliminado exitosamente")
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"   ❌ Error al eliminar usuario: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Función principal"""
    import sys
    
    print("="*70)
    print("ELIMINACIÓN DE USUARIOS Y TRANSACCIONES")
    print("="*70)
    print(f"\n📋 Usuarios a eliminar: {len(USERS_TO_DELETE)}")
    for email in USERS_TO_DELETE:
        print(f"   - {email}")
    
    print("\n⚠️  ADVERTENCIA: Esta acción eliminará permanentemente:")
    print("   - Los usuarios")
    print("   - Todas sus membresías")
    print("   - Todas sus suscripciones")
    print("   - Todos sus pagos")
    print("   - Todos sus registros de eventos")
    print("   - Todas sus citas")
    print("   - Todos sus logs y notificaciones")
    print("\n⚠️  Esta acción NO se puede deshacer!")
    
    # Verificar si se pasó el parámetro --confirm
    if '--confirm' not in sys.argv:
        print("\n⚠️  Para ejecutar esta eliminación, usa: python3 delete_users.py --confirm")
        print("   O modifica el script para confirmar manualmente")
        return
    
    print("\n✅ Confirmación recibida. Procediendo con la eliminación...")
    
    print("\n" + "="*70)
    print("INICIANDO ELIMINACIÓN")
    print("="*70)
    
    with app.app_context():
        deleted_count = 0
        failed_count = 0
        
        for email in USERS_TO_DELETE:
            if delete_user_and_transactions(email):
                deleted_count += 1
            else:
                failed_count += 1
        
        print("\n" + "="*70)
        print("RESUMEN")
        print("="*70)
        print(f"✅ Usuarios eliminados exitosamente: {deleted_count}")
        if failed_count > 0:
            print(f"❌ Usuarios con errores: {failed_count}")
        print("\n✨ Proceso completado")

if __name__ == '__main__':
    main()

