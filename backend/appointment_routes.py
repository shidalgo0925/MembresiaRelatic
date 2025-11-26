#!/usr/bin/env python3
"""
Rutas y vistas para la gestión de citas (appointments) tanto para miembros
como para administradores, inspiradas en el flujo de Odoo.
"""

from datetime import datetime, timedelta
from functools import wraps

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

# Blueprints
appointments_bp = Blueprint('appointments', __name__, url_prefix='/appointments')
admin_appointments_bp = Blueprint('admin_appointments', __name__, url_prefix='/admin/appointments')
appointments_api_bp = Blueprint('appointments_api', __name__, url_prefix='/api/appointments')

# Model references (se inicializan perezosamente para evitar import circular)
db = None
User = None
Advisor = None
AppointmentType = None
AppointmentAdvisor = None
AppointmentSlot = None
Appointment = None
AppointmentParticipant = None
AppointmentPricing = None
AdvisorAvailability = None
ActivityLog = None


def init_models():
    """Importa modelos desde app.py cuando sea necesario."""
    global db
    global User
    global Advisor
    global AppointmentType
    global AppointmentAdvisor
    global AppointmentSlot
    global Appointment
    global AppointmentParticipant
    global AppointmentPricing
    global AdvisorAvailability
    global ActivityLog

    if db is not None:
        return

    from app import (
        db as _db,
        User as _User,
        Advisor as _Advisor,
        AppointmentType as _AppointmentType,
        AppointmentAdvisor as _AppointmentAdvisor,
        AppointmentSlot as _AppointmentSlot,
        Appointment as _Appointment,
        AppointmentParticipant as _AppointmentParticipant,
        AppointmentPricing as _AppointmentPricing,
        AdvisorAvailability as _AdvisorAvailability,
        ActivityLog as _ActivityLog,
    )

    db = _db
    User = _User
    Advisor = _Advisor
    AppointmentType = _AppointmentType
    AppointmentAdvisor = _AppointmentAdvisor
    AppointmentSlot = _AppointmentSlot
    Appointment = _Appointment
    AppointmentParticipant = _AppointmentParticipant
    AppointmentPricing = _AppointmentPricing
    AdvisorAvailability = _AdvisorAvailability
    ActivityLog = _ActivityLog


def ensure_models():
    if db is None:
        init_models()


def admin_required(f):
    """Decorator para vistas administrativas."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            flash('No tienes permisos para acceder a esta sección.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)

    return decorated_function


def _active_membership_or_warning():
    """Devuelve la membresía activa del usuario o None, mostrando advertencia."""
    membership = current_user.get_active_membership()
    if not membership:
        flash('Necesitas una membresía activa para reservar citas. Revisa tus planes disponibles.', 'warning')
    return membership


def _slot_queryset():
    ensure_models()
    return AppointmentSlot.query.filter(AppointmentSlot.start_datetime >= datetime.utcnow()).order_by(AppointmentSlot.start_datetime.asc())


@appointments_bp.route('/')
@login_required
def appointments_home():
    ensure_models()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None

    appointment_types = AppointmentType.query.filter_by(is_active=True).order_by(AppointmentType.display_order.asc()).all()
    types_with_pricing = [
        (appt_type, appt_type.pricing_for_membership(membership_type))
        for appt_type in appointment_types
    ]

    upcoming = Appointment.query.filter(
        Appointment.user_id == current_user.id,
        Appointment.start_datetime >= datetime.utcnow()
    ).order_by(Appointment.start_datetime.asc()).all()

    past = Appointment.query.filter(
        Appointment.user_id == current_user.id,
        Appointment.start_datetime < datetime.utcnow()
    ).order_by(Appointment.start_datetime.desc()).limit(5).all()

    return render_template(
        'appointments/index.html',
        membership=membership,
        types_with_pricing=types_with_pricing,
        upcoming_appointments=upcoming,
        past_appointments=past,
    )


@appointments_bp.route('/type/<int:type_id>')
@login_required
def appointment_type_detail(type_id):
    ensure_models()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None

    appointment_type = AppointmentType.query.get_or_404(type_id)
    pricing = appointment_type.pricing_for_membership(membership_type)
    advisors = [
        assignment.advisor for assignment in appointment_type.advisor_assignments
        if assignment.is_active and assignment.advisor.is_active
    ]

    available_slots = _slot_queryset().filter(
        AppointmentSlot.appointment_type_id == appointment_type.id,
        AppointmentSlot.is_available == True  # noqa
    ).limit(20).all()

    return render_template(
        'appointments/type_detail.html',
        appointment_type=appointment_type,
        advisors=advisors,
        pricing=pricing,
        slots=available_slots,
        membership=membership,
    )


@appointments_bp.route('/book/<int:slot_id>', methods=['POST'])
@login_required
def book_appointment(slot_id):
    ensure_models()
    membership = _active_membership_or_warning()
    if membership is None:
        return redirect(request.referrer or url_for('appointments.appointments_home'))

    slot = AppointmentSlot.query.get_or_404(slot_id)
    if not slot.is_available or slot.remaining_seats() <= 0:
        flash('Este horario ya no está disponible. Intenta con otro slot.', 'warning')
        return redirect(url_for('appointments.appointment_type_detail', type_id=slot.appointment_type_id))

    notes = request.form.get('notes', '').strip()
    membership_type = membership.membership_type if membership else None
    pricing = slot.appointment_type.pricing_for_membership(membership_type)
    base_price = pricing['base_price']
    final_price = pricing['final_price']
    discount = max(0.0, base_price - final_price)

    appointment = Appointment(
        appointment_type_id=slot.appointment_type_id,
        advisor_id=slot.advisor_id,
        slot_id=slot.id,
        user_id=current_user.id,
        membership_type=membership_type,
        is_group=slot.capacity > 1,
        start_datetime=slot.start_datetime,
        end_datetime=slot.end_datetime,
        status='pending',
        base_price=base_price,
        final_price=final_price,
        discount_applied=discount,
        user_notes=notes,
    )

    slot.reserved_seats = (slot.reserved_seats or 0) + 1
    if slot.remaining_seats() == 0:
        slot.is_available = False

    db.session.add(appointment)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'book_appointment',
        'appointment',
        appointment.id,
        f'Reservó la cita {appointment.reference}',
        request
    )

    flash('Tu cita fue registrada y está pendiente de confirmación del asesor.', 'success')
    return redirect(url_for('appointments.appointments_home'))


@appointments_bp.route('/cancel/<int:appointment_id>', methods=['POST'])
@login_required
def cancel_appointment(appointment_id):
    ensure_models()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.user_id != current_user.id and not current_user.is_admin:
        flash('No puedes cancelar esta cita.', 'error')
        return redirect(url_for('appointments.appointments_home'))

    if appointment.status == 'cancelled':
        flash('La cita ya estaba cancelada.', 'info')
        return redirect(url_for('appointments.appointments_home'))

    if appointment.start_datetime <= datetime.utcnow():
        flash('No puedes cancelar citas que ya iniciaron.', 'warning')
        return redirect(url_for('appointments.appointments_home'))

    appointment.status = 'cancelled'
    appointment.cancellation_reason = request.form.get('reason', 'Cancelada por el miembro.')

    if appointment.slot:
        appointment.slot.reserved_seats = max(0, (appointment.slot.reserved_seats or 1) - 1)
        appointment.slot.is_available = True

    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'cancel_appointment',
        'appointment',
        appointment.id,
        f'Canceló la cita {appointment.reference}',
        request
    )

    flash('Tu cita fue cancelada.', 'info')
    return redirect(url_for('appointments.appointments_home'))


# ---------------------------------------------------------------------------
# Vistas Administrativas
# ---------------------------------------------------------------------------
@admin_appointments_bp.route('/')
@admin_required
def admin_appointments_dashboard():
    ensure_models()
    types = AppointmentType.query.order_by(AppointmentType.display_order.asc()).all()
    advisors = Advisor.query.order_by(Advisor.created_at.desc()).all()
    upcoming = _slot_queryset().limit(15).all()
    waiting_confirmation = Appointment.query.filter_by(status='pending').order_by(Appointment.start_datetime.asc()).limit(10).all()

    stats = {
        'active_types': len(types),
        'active_advisors': sum(1 for advisor in advisors if advisor.is_active),
        'pending_appointments': len(waiting_confirmation),
        'next_slots': len(upcoming),
    }

    return render_template(
        'admin/appointments/list.html',
        types=types,
        advisors=advisors,
        stats=stats,
        slots=upcoming,
        pending_appointments=waiting_confirmation,
    )


@admin_appointments_bp.route('/<int:appointment_id>/confirm', methods=['POST'])
@admin_required
def admin_confirm_appointment(appointment_id):
    ensure_models()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.status == 'confirmed':
        flash('La cita ya estaba confirmada.', 'info')
        return redirect(url_for('admin_appointments.admin_appointments_dashboard'))

    appointment.status = 'confirmed'
    appointment.advisor_confirmed = True
    appointment.advisor_confirmed_at = datetime.utcnow()
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'confirm_appointment',
        'appointment',
        appointment.id,
        f'Confirmó la cita {appointment.reference}',
        request
    )

    flash('La cita fue confirmada y se notificará al miembro.', 'success')
    return redirect(url_for('admin_appointments.admin_appointments_dashboard'))


@admin_appointments_bp.route('/<int:appointment_id>/cancel', methods=['POST'])
@admin_required
def admin_cancel_appointment(appointment_id):
    ensure_models()
    appointment = Appointment.query.get_or_404(appointment_id)
    if appointment.status == 'cancelled':
        flash('La cita ya estaba cancelada.', 'info')
        return redirect(url_for('admin_appointments.admin_appointments_dashboard'))

    appointment.status = 'cancelled'
    appointment.cancellation_reason = request.form.get('reason', 'Cancelada por el administrador.')

    if appointment.slot:
        appointment.slot.reserved_seats = max(0, (appointment.slot.reserved_seats or 1) - 1)
        appointment.slot.is_available = True

    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'cancel_appointment_admin',
        'appointment',
        appointment.id,
        f'Canceló la cita {appointment.reference}',
        request
    )

    flash('La cita fue cancelada y los participantes serán notificados.', 'info')
    return redirect(url_for('admin_appointments.admin_appointments_dashboard'))


@admin_appointments_bp.route('/types/create', methods=['GET', 'POST'])
@admin_required
def create_appointment_type():
    ensure_models()
    advisors = Advisor.query.filter_by(is_active=True).order_by(Advisor.created_at.asc()).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        duration = request.form.get('duration_minutes', type=int) or 60
        base_price = request.form.get('base_price', type=float) or 0.0

        if not name:
            flash('El nombre del servicio es obligatorio.', 'error')
            return redirect(request.url)

        appointment_type = AppointmentType(
            name=name,
            description=request.form.get('description', '').strip(),
            service_category=request.form.get('service_category', '').strip() or 'general',
            duration_minutes=duration,
            is_group_allowed=bool(request.form.get('is_group_allowed')),
            max_participants=request.form.get('max_participants', type=int) or 1,
            base_price=base_price,
            currency=request.form.get('currency', 'USD'),
            is_virtual=bool(request.form.get('is_virtual', True)),
            requires_confirmation=bool(request.form.get('requires_confirmation', True)),
            color_tag=request.form.get('color_tag', '#0d6efd'),
            icon=request.form.get('icon', 'fa-calendar-check'),
            display_order=request.form.get('display_order', type=int) or 1,
        )

        db.session.add(appointment_type)
        db.session.flush()

        advisor_ids = request.form.getlist('advisor_ids')
        for idx, advisor_id in enumerate(advisor_ids, start=1):
            advisor = Advisor.query.get(int(advisor_id))
            if advisor:
                db.session.add(AppointmentAdvisor(
                    appointment_type_id=appointment_type.id,
                    advisor_id=advisor.id,
                    priority=idx
                ))

        db.session.commit()

        ActivityLog.log_activity(
            current_user.id,
            'create_appointment_type',
            'appointment_type',
            appointment_type.id,
            f'Creó el servicio de citas {appointment_type.name}',
            request
        )

        flash('Servicio de citas creado correctamente.', 'success')
        return redirect(url_for('admin_appointments.admin_appointments_dashboard'))

    return render_template(
        'admin/appointments/type_form.html',
        appointment_type=None,
        advisors=advisors,
    )


@admin_appointments_bp.route('/slots/create', methods=['POST'])
@admin_required
def create_manual_slot():
    ensure_models()
    type_id = request.form.get('appointment_type_id', type=int)
    advisor_id = request.form.get('advisor_id', type=int)
    start_raw = request.form.get('start_datetime', '').strip()
    capacity = request.form.get('capacity', type=int) or 1

    appointment_type = AppointmentType.query.get_or_404(type_id)
    advisor = Advisor.query.get_or_404(advisor_id)

    try:
        start_datetime = datetime.strptime(start_raw, '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Formato de fecha inválido.', 'error')
        return redirect(url_for('admin_appointments.admin_appointments_dashboard'))

    end_datetime = start_datetime + appointment_type.duration()

    slot = AppointmentSlot(
        appointment_type_id=appointment_type.id,
        advisor_id=advisor.id,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        capacity=max(1, capacity),
        is_auto_generated=False,
        created_by=current_user.id,
    )

    db.session.add(slot)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'create_slot',
        'appointment_slot',
        slot.id,
        f'Creó un slot manual para {appointment_type.name}',
        request
    )

    flash('Slot creado satisfactoriamente.', 'success')
    return redirect(url_for('admin_appointments.admin_appointments_dashboard'))


@admin_appointments_bp.route('/advisors')
@admin_required
def list_advisors():
    ensure_models()
    advisors = Advisor.query.order_by(Advisor.created_at.desc()).all()
    available_users = User.query.filter_by(is_advisor=False).order_by(User.first_name.asc()).all()
    return render_template(
        'admin/appointments/advisors.html',
        advisors=advisors,
        available_users=available_users,
    )


@admin_appointments_bp.route('/advisors/create', methods=['POST'])
@admin_required
def create_advisor():
    ensure_models()
    user_id = request.form.get('user_id', type=int)
    user = User.query.get_or_404(user_id)

    if user.is_advisor:
        flash('Este usuario ya es asesor.', 'warning')
        return redirect(url_for('admin_appointments.list_advisors'))

    advisor = Advisor(
        user_id=user.id,
        headline=request.form.get('headline', '').strip(),
        bio=request.form.get('bio', '').strip(),
        specializations=request.form.get('specializations', '').strip(),
        meeting_url=request.form.get('meeting_url', '').strip(),
    )

    user.is_advisor = True
    db.session.add(advisor)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'create_advisor',
        'advisor',
        advisor.id,
        f'Designó como asesor a {user.first_name} {user.last_name}',
        request
    )

    flash('Asesor creado correctamente.', 'success')
    return redirect(url_for('admin_appointments.list_advisors'))


# ---------------------------------------------------------------------------
# API Pública mínima (slots disponibles)
# ---------------------------------------------------------------------------
@appointments_api_bp.route('/slots')
@login_required
def api_slots():
    ensure_models()
    type_id = request.args.get('type_id', type=int)
    query = _slot_queryset().filter(AppointmentSlot.is_available == True)  # noqa
    if type_id:
        query = query.filter(AppointmentSlot.appointment_type_id == type_id)

    slots = query.limit(50).all()
    return jsonify([
        {
            'id': slot.id,
            'appointment_type': slot.appointment_type.name,
            'advisor': slot.advisor.user.first_name if slot.advisor and slot.advisor.user else None,
            'start': slot.start_datetime.isoformat(),
            'end': slot.end_datetime.isoformat(),
            'capacity': slot.capacity,
            'remaining': slot.remaining_seats(),
        }
        for slot in slots
    ])

