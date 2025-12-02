#!/usr/bin/env python3
"""
Sistema de tareas programadas para notificaciones
Verifica membresías expirando, citas próximas, etc.
"""

from datetime import datetime, timedelta
from app import app, db, User, Subscription, Appointment, NotificationEngine, Notification


def check_expiring_memberships():
    """Verificar membresías que están por expirar y enviar notificaciones"""
    with app.app_context():
        try:
            # Buscar membresías que expiran en 30, 15, 7 y 1 día
            today = datetime.utcnow().date()
            check_dates = [
                (today + timedelta(days=30), 30),
                (today + timedelta(days=15), 15),
                (today + timedelta(days=7), 7),
                (today + timedelta(days=1), 1)
            ]
            
            for check_date, days_left in check_dates:
                # Buscar suscripciones activas que expiran en la fecha específica
                subscriptions = Subscription.query.filter(
                    Subscription.status == 'active',
                    db.func.date(Subscription.end_date) == check_date
                ).all()
                
                for subscription in subscriptions:
                    user = User.query.get(subscription.user_id)
                    if user:
                        # Verificar si ya se envió notificación para este día
                        existing_notification = Notification.query.filter(
                            Notification.user_id == user.id,
                            Notification.notification_type == 'membership_expiring',
                            Notification.created_at >= datetime.utcnow() - timedelta(days=1)
                        ).first()
                        
                        if not existing_notification:
                            NotificationEngine.notify_membership_expiring(user, subscription, days_left)
                            print(f"✅ Notificación enviada a {user.email}: membresía expira en {days_left} días")
            
            # Verificar membresías expiradas
            expired_subscriptions = Subscription.query.filter(
                Subscription.status == 'active',
                db.func.date(Subscription.end_date) < today
            ).all()
            
            for subscription in expired_subscriptions:
                user = User.query.get(subscription.user_id)
                if user:
                    # Marcar suscripción como expirada
                    subscription.status = 'expired'
                    
                    # Verificar si ya se envió notificación
                    existing_notification = Notification.query.filter(
                        Notification.user_id == user.id,
                        Notification.notification_type == 'membership_expired',
                        Notification.created_at >= datetime.utcnow() - timedelta(days=1)
                    ).first()
                    
                    if not existing_notification:
                        NotificationEngine.notify_membership_expired(user, subscription)
                        print(f"✅ Notificación enviada a {user.email}: membresía expirada")
            
            db.session.commit()
            print(f"✅ Verificación de membresías completada: {datetime.utcnow()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error verificando membresías: {e}")


def check_appointment_reminders():
    """Verificar citas próximas y enviar recordatorios"""
    with app.app_context():
        try:
            from app import Appointment, User, AdvisorProfile
            
            # Buscar citas confirmadas en las próximas 24 y 48 horas
            now = datetime.utcnow()
            reminder_times = [
                (now + timedelta(hours=24), 24),
                (now + timedelta(hours=48), 48)
            ]
            
            for reminder_time, hours_before in reminder_times:
                # Buscar citas en el rango de tiempo (ventana de 1 hora)
                start_window = reminder_time - timedelta(minutes=30)
                end_window = reminder_time + timedelta(minutes=30)
                
                appointments = Appointment.query.filter(
                    Appointment.status == 'confirmed',
                    Appointment.start_datetime >= start_window,
                    Appointment.start_datetime <= end_window
                ).all()
                
                for appointment in appointments:
                    user = User.query.get(appointment.user_id)
                    advisor = User.query.get(appointment.advisor_id) if appointment.advisor_id else None
                    
                    if user and advisor:
                        # Verificar si ya se envió recordatorio para esta hora
                        existing_notification = Notification.query.filter(
                            Notification.user_id == user.id,
                            Notification.notification_type == 'appointment_reminder',
                            Notification.created_at >= datetime.utcnow() - timedelta(hours=2)
                        ).first()
                        
                        if not existing_notification:
                            NotificationEngine.notify_appointment_reminder(appointment, user, advisor, hours_before)
                            print(f"✅ Recordatorio enviado a {user.email}: cita en {hours_before} horas")
            
            db.session.commit()
            print(f"✅ Verificación de recordatorios de citas completada: {datetime.utcnow()}")
            
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error verificando recordatorios de citas: {e}")


def run_scheduled_tasks():
    """Ejecutar todas las tareas programadas"""
    print(f"\n{'='*60}")
    print(f"Ejecutando tareas programadas: {datetime.utcnow()}")
    print(f"{'='*60}\n")
    
    check_expiring_memberships()
    check_appointment_reminders()
    
    print(f"\n{'='*60}")
    print(f"Tareas programadas completadas: {datetime.utcnow()}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    run_scheduled_tasks()

