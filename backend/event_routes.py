#!/usr/bin/env python3
"""
Rutas y vistas para la gestión de eventos, descuentos y su consumo desde el
panel administrativo, el portal de miembros y APIs públicas.
"""

from datetime import datetime, timedelta
import os
import re
import unicodedata

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from functools import wraps

# Decorador admin_required
def admin_required(f):
    """Decorador para requerir permisos de administrador"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            from flask import flash, redirect, url_for
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Inicializar referencias a modelos dinámicamente para evitar importaciones
# circulares con app.py
db = None
Event = None
EventImage = None
Discount = None
EventDiscount = None
ActivityLog = None
allowed_file = None


def init_models():
    """Importa los modelos necesarios desde app.py una vez que existen."""
    global db, Event, EventImage, Discount, EventDiscount, ActivityLog, allowed_file, EventRegistration
    try:
        from app import (
            db as _db,
            Event as _Event,
            EventImage as _EventImage,
            Discount as _Discount,
            EventDiscount as _EventDiscount,
            ActivityLog as _ActivityLog,
            allowed_file as _allowed_file,
            EventRegistration as _EventRegistration,
        )

        db = _db
        Event = _Event
        EventImage = _EventImage
        Discount = _Discount
        EventDiscount = _EventDiscount
        ActivityLog = _ActivityLog
        allowed_file = _allowed_file
        EventRegistration = _EventRegistration
    except ImportError:
        pass


def ensure_models():
    """Garantiza que los modelos estén inicializados antes de usarlos."""
    if Event is None:
        init_models()


def _slugify(value: str) -> str:
    """Genera un slug URL-safe basado en el título."""
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')
    return value or f"evento-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _unique_slug(base_slug: str, event_id=None) -> str:
    ensure_models()
    slug = base_slug
    counter = 1
    while True:
        query = Event.query.filter(Event.slug == slug)
        if event_id:
            query = query.filter(Event.id != event_id)
        exists = db.session.query(query.exists()).scalar()
        if not exists:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def _parse_datetime(field_name: str):
    value = request.form.get(field_name, '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


def _uploads_dir():
    folder = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'events')
    os.makedirs(folder, exist_ok=True)
    return folder


def _remove_file_if_exists(path):
    if not path:
        return
    absolute = os.path.join(current_app.root_path, '..', path.lstrip('/'))
    if os.path.exists(absolute):
        try:
            os.remove(absolute)
        except OSError:
            pass


def _save_file(storage, prefix='event'):
    if not storage or storage.filename == '' or not allowed_file(storage.filename):
        return None
    filename = secure_filename(storage.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    new_name = f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    storage.save(os.path.join(_uploads_dir(), new_name))
    return f"/static/uploads/events/{new_name}"


def _serialize_event(event, membership_type=None):
    data = {
        'id': event.id,
        'slug': event.slug,
        'title': event.title,
        'summary': event.summary,
        'description': event.description,
        'category': event.category,
        'format': event.format,
        'tags': event.tags,
        'currency': event.currency,
        'start_date': event.start_date.isoformat() if event.start_date else None,
        'end_date': event.end_date.isoformat() if event.end_date else None,
        'registration_deadline': event.registration_deadline.isoformat() if event.registration_deadline else None,
        'cover_image': event.cover_url(),
        'is_virtual': event.is_virtual,
        'location': event.location,
        'country': event.country,
        'has_certificate': event.has_certificate,
        'certificate_instructions': event.certificate_instructions,
        'visibility': event.visibility,
        'publish_status': event.publish_status,
        'featured': event.featured,
    }
    pricing = event.pricing_for_membership(membership_type)
    data['pricing'] = {
        'base_price': pricing['base_price'],
        'final_price': pricing['final_price'],
        'discount': {
            'name': pricing['discount'].name,
            'value': pricing['discount'].value,
            'type': pricing['discount'].discount_type,
            'membership_tier': pricing['discount'].membership_tier,
        } if pricing['discount'] else None
    }
    return data


# Blueprints
events_bp = Blueprint('events', __name__, url_prefix='/events')
admin_events_bp = Blueprint('admin_events', __name__, url_prefix='/admin/events')
events_api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


# ------------------------------------------------------------------------------
# Portal de miembros
# ------------------------------------------------------------------------------
@events_bp.route('/')
@login_required
def list_events():
    ensure_models()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    status = request.args.get('status', 'published')
    category = request.args.get('category', '').strip()
    search = request.args.get('q', '').strip()

    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(or_(Event.title.ilike(like), Event.summary.ilike(like), Event.tags.ilike(like)))

    events = query.order_by(Event.start_date.asc()).all()
    categories = sorted({evt.category for evt in events if evt.category})

    return render_template(
        'events/list.html',
        events=events,
        categories=categories,
        active_category=category,
        search=search,
        status=status,
        membership=membership,
        membership_type=membership_type
    )


@events_bp.route('/<string:slug>')
@login_required
def event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    pricing = event.pricing_for_membership(membership_type)
    
    # Verificar si el usuario ya está registrado
    registration = EventRegistration.query.filter_by(
        event_id=event.id,
        user_id=current_user.id
    ).first() if EventRegistration else None
    
    # Verificar capacidad disponible
    is_full = False
    available_spots = None
    if event.capacity and event.capacity > 0:
        registered_count = EventRegistration.query.filter_by(
            event_id=event.id,
            registration_status='confirmed'
        ).count() if EventRegistration else 0
        available_spots = event.capacity - registered_count
        is_full = available_spots <= 0
    
    return render_template(
        'events/detail.html',
        event=event,
        membership=membership,
        pricing=pricing,
        registration=registration,
        is_full=is_full,
        available_spots=available_spots
    )


@events_bp.route('/<string:slug>/register', methods=['POST'])
@login_required
def register_to_event(slug):
    """Registrar usuario a un evento"""
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    
    # Verificar si ya está registrado
    existing_registration = EventRegistration.query.filter_by(
        event_id=event.id,
        user_id=current_user.id
    ).first() if EventRegistration else None
    
    if existing_registration:
        flash('Ya estás registrado en este evento.', 'info')
        return redirect(url_for('events.event_detail', slug=slug))
    
    # Verificar capacidad
    if event.capacity and event.capacity > 0:
        registered_count = EventRegistration.query.filter_by(
            event_id=event.id,
            registration_status='confirmed'
        ).count() if EventRegistration else 0
        if registered_count >= event.capacity:
            flash('Lo sentimos, este evento ya está lleno.', 'error')
            return redirect(url_for('events.event_detail', slug=slug))
    
    # Calcular precio con descuentos
    pricing = event.pricing_for_membership(membership_type)
    base_price = pricing['base_price']
    final_price = pricing['final_price']
    discount_applied = base_price - final_price
    
    # Crear registro
    registration = EventRegistration(
        event_id=event.id,
        user_id=current_user.id,
        base_price=base_price,
        final_price=final_price,
        discount_applied=discount_applied,
        membership_type=membership_type,
        registration_status='pending' if final_price > 0 else 'confirmed'
    )
    
    db.session.add(registration)
    
    # Actualizar contador de registrados
    if event.registered_count is None:
        event.registered_count = 0
    event.registered_count += 1
    
    # Log de actividad
    ActivityLog.log_activity(
        current_user.id,
        'register_event',
        'event',
        event.id,
        f'Usuario registrado al evento: {event.title}',
        request
    )
    
    db.session.commit()
    
    flash('Te has registrado exitosamente al evento. Recibirás un email de confirmación.', 'success')
    return redirect(url_for('events.event_detail', slug=slug))


@events_bp.route('/<string:slug>/cancel-registration', methods=['POST'])
@login_required
def cancel_event_registration(slug):
    """Cancelar registro a un evento"""
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    registration = EventRegistration.query.filter_by(
        event_id=event.id,
        user_id=current_user.id
    ).first_or_404() if EventRegistration else None
    
    if not registration:
        flash('No tienes un registro activo para este evento.', 'error')
        return redirect(url_for('events.event_detail', slug=slug))
    
    registration.registration_status = 'cancelled'
    
    # Actualizar contador
    if event.registered_count and event.registered_count > 0:
        event.registered_count -= 1
    
    # Log de actividad
    ActivityLog.log_activity(
        current_user.id,
        'cancel_event_registration',
        'event',
        event.id,
        f'Registro cancelado al evento: {event.title}',
        request
    )
    
    db.session.commit()
    
    flash('Tu registro al evento ha sido cancelado.', 'info')
    return redirect(url_for('events.event_detail', slug=slug))


# ------------------------------------------------------------------------------
# API pública
# ------------------------------------------------------------------------------
@events_api_bp.route('/', methods=['GET'])
def api_events():
    ensure_models()
    status = request.args.get('status', 'published')
    limit = request.args.get('limit', type=int)
    membership_type = request.args.get('membership_type')

    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    query = query.order_by(Event.start_date.asc())
    if limit:
        query = query.limit(limit)

    events = query.all()
    return jsonify({'events': [_serialize_event(evt, membership_type) for evt in events]})


@events_api_bp.route('/<string:slug>', methods=['GET'])
def api_event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership_type = request.args.get('membership_type')
    return jsonify({'event': _serialize_event(event, membership_type)})


# ------------------------------------------------------------------------------
# Panel Administrativo - Eventos
# ------------------------------------------------------------------------------
@admin_events_bp.route('/')
@admin_required
def admin_events_index():
    ensure_models()
    status = request.args.get('status', 'all')
    category = request.args.get('category', '').strip()

    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)

    events = query.order_by(Event.start_date.desc()).all()
    stats = {
        'total': Event.query.count(),
        'published': Event.query.filter_by(publish_status='published').count(),
        'drafts': Event.query.filter_by(publish_status='draft').count(),
        'archived': Event.query.filter_by(publish_status='archived').count(),
    }

    return render_template(
        'admin/events/list.html',
        events=events,
        status=status,
        category=category,
        stats=stats
    )


@admin_events_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_event():
    ensure_models()
    discounts = Discount.query.order_by(Discount.name.asc()).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)

        slug = request.form.get('slug', '').strip() or _slugify(title)
        slug = _unique_slug(slug)

        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas de inicio y fin son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la de inicio.', 'error')
            return redirect(request.url)

        event = Event(
            title=title,
            slug=slug,
            summary=request.form.get('summary', '').strip(),
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'general').strip() or 'general',
            format=request.form.get('format', 'virtual').strip() or 'virtual',
            tags=request.form.get('tags', '').strip(),
            base_price=request.form.get('base_price', type=float) or 0.0,
            currency=request.form.get('currency', 'USD').upper(),
            registration_url=request.form.get('registration_url', '').strip(),
            contact_email=request.form.get('contact_email', '').strip(),
            contact_phone=request.form.get('contact_phone', '').strip(),
            location=request.form.get('location', '').strip(),
            country=request.form.get('country', '').strip(),
            is_virtual=bool(request.form.get('is_virtual')),
            has_certificate=bool(request.form.get('has_certificate')),
            certificate_instructions=request.form.get('certificate_instructions', '').strip(),
            capacity=request.form.get('capacity', type=int) or 0,
            visibility=request.form.get('visibility', 'members'),
            publish_status=request.form.get('publish_status', 'draft'),
            featured=bool(request.form.get('featured')),
            start_date=start_date,
            end_date=end_date,
            registration_deadline=_parse_datetime('registration_deadline'),
            created_by=current_user.id
        )

        db.session.add(event)
        db.session.flush()

        cover_path = _save_file(request.files.get('cover_image'), prefix='cover')
        if cover_path:
            event.cover_image = cover_path

        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=idx,
                    is_primary=False
                ))

        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            try:
                discount = Discount.query.get(int(discount_id))
            except (TypeError, ValueError):
                discount = None
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))

        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'create_event',
            'event',
            event.id,
            f'Evento creado: {event.title}',
            request
        )
        flash('Evento creado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))

    default_start = (datetime.utcnow() + timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    default_end = default_start + timedelta(hours=2)
    return render_template(
        'admin/events/form.html',
        action='create',
        event=None,
        discounts=discounts,
        default_start=default_start,
        default_end=default_end
    )


@admin_events_bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    discounts = Discount.query.order_by(Discount.name.asc()).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)

        slug = request.form.get('slug', '').strip() or _slugify(title)
        event.slug = _unique_slug(slug, event_id=event.id)

        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas de inicio y fin son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la de inicio.', 'error')
            return redirect(request.url)

        event.title = title
        event.summary = request.form.get('summary', '').strip()
        event.description = request.form.get('description', '').strip()
        event.category = request.form.get('category', 'general').strip() or 'general'
        event.format = request.form.get('format', 'virtual').strip() or 'virtual'
        event.tags = request.form.get('tags', '').strip()
        event.base_price = request.form.get('base_price', type=float) or 0.0
        event.currency = request.form.get('currency', 'USD').upper()
        event.registration_url = request.form.get('registration_url', '').strip()
        event.contact_email = request.form.get('contact_email', '').strip()
        event.contact_phone = request.form.get('contact_phone', '').strip()
        event.location = request.form.get('location', '').strip()
        event.country = request.form.get('country', '').strip()
        event.is_virtual = bool(request.form.get('is_virtual'))
        event.has_certificate = bool(request.form.get('has_certificate'))
        event.certificate_instructions = request.form.get('certificate_instructions', '').strip()
        event.capacity = request.form.get('capacity', type=int) or 0
        event.visibility = request.form.get('visibility', 'members')
        event.publish_status = request.form.get('publish_status', 'draft')
        event.featured = bool(request.form.get('featured'))
        event.start_date = start_date
        event.end_date = end_date
        event.registration_deadline = _parse_datetime('registration_deadline')

        if request.form.get('remove_cover'):
            _remove_file_if_exists(event.cover_image)
            event.cover_image = None

        new_cover = _save_file(request.files.get('cover_image'), prefix='cover')
        if new_cover:
            _remove_file_if_exists(event.cover_image)
            event.cover_image = new_cover

        delete_ids = request.form.getlist('delete_images')
        for image_id in delete_ids:
            image = EventImage.query.filter_by(id=image_id, event_id=event.id).first()
            if image:
                _remove_file_if_exists(image.file_path)
                db.session.delete(image)

        current_order = len(event.images)
        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=current_order + idx,
                    is_primary=False
                ))

        EventDiscount.query.filter_by(event_id=event.id).delete()
        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            try:
                discount = Discount.query.get(int(discount_id))
            except (TypeError, ValueError):
                discount = None
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))

        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_event',
            'event',
            event.id,
            f'Evento actualizado: {event.title}',
            request
        )
        flash('Evento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))

    return render_template(
        'admin/events/form.html',
        action='edit',
        event=event,
        discounts=discounts,
        default_start=event.start_date,
        default_end=event.end_date
    )


@admin_events_bp.route('/<int:event_id>/delete', methods=['POST'])
@admin_required
def delete_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    title = event.title

    _remove_file_if_exists(event.cover_image)
    for image in event.images:
        _remove_file_if_exists(image.file_path)

    db.session.delete(event)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'delete_event',
        'event',
        event_id,
        f'Evento eliminado: {title}',
        request
    )
    flash('Evento eliminado correctamente.', 'info')
    return redirect(url_for('admin_events.admin_events_index'))


# ------------------------------------------------------------------------------
# Panel Administrativo - Descuentos
# ------------------------------------------------------------------------------
@admin_events_bp.route('/discounts')
@admin_required
def discounts_index():
    ensure_models()
    discounts = Discount.query.order_by(Discount.created_at.desc()).all()
    return render_template('admin/events/discount_list.html', discounts=discounts)


@admin_events_bp.route('/discounts/create', methods=['GET', 'POST'])
@admin_required
def create_discount():
    ensure_models()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre es obligatorio.', 'error')
            return redirect(request.url)

        discount = Discount(
            name=name,
            code=request.form.get('code', '').strip() or None,
            description=request.form.get('description', '').strip(),
            discount_type=request.form.get('discount_type', 'percentage'),
            value=request.form.get('value', type=float) or 0.0,
            membership_tier=request.form.get('membership_tier', '').strip() or None,
            category=request.form.get('category', 'event'),
            applies_automatically='applies_automatically' in request.form,
            is_active='is_active' in request.form,
            max_uses=request.form.get('max_uses', type=int),
            start_date=_parse_datetime('start_date'),
            end_date=_parse_datetime('end_date')
        )
        db.session.add(discount)
        db.session.commit()

        ActivityLog.log_activity(
            current_user.id,
            'create_discount',
            'discount',
            discount.id,
            f'Descuento creado: {discount.name}',
            request
        )
        flash('Descuento creado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))

    return render_template('admin/events/discount_form.html', action='create', discount=None)


@admin_events_bp.route('/discounts/<int:discount_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)

    if request.method == 'POST':
        discount.name = request.form.get('name', '').strip()
        discount.code = request.form.get('code', '').strip() or None
        discount.description = request.form.get('description', '').strip()
        discount.discount_type = request.form.get('discount_type', 'percentage')
        discount.value = request.form.get('value', type=float) or 0.0
        discount.membership_tier = request.form.get('membership_tier', '').strip() or None
        discount.category = request.form.get('category', 'event')
        discount.applies_automatically = 'applies_automatically' in request.form
        discount.is_active = 'is_active' in request.form
        discount.max_uses = request.form.get('max_uses', type=int)
        discount.start_date = _parse_datetime('start_date')
        discount.end_date = _parse_datetime('end_date')

        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_discount',
            'discount',
            discount.id,
            f'Descuento actualizado: {discount.name}',
            request
        )
        flash('Descuento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))

    return render_template('admin/events/discount_form.html', action='edit', discount=discount)


@admin_events_bp.route('/discounts/<int:discount_id>/delete', methods=['POST'])
@admin_required
def delete_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)
    name = discount.name
    db.session.delete(discount)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'delete_discount',
        'discount',
        discount_id,
        f'Descuento eliminado: {name}',
        request
    )
    flash('Descuento eliminado.', 'info')
    return redirect(url_for('admin_events.discounts_index'))
#!/usr/bin/env python3
"""
Rutas para la gestión de eventos y descuentos del ecosistema RELATIC.
"""

from datetime import datetime, timedelta
import os
import re
import unicodedata

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from functools import wraps

# Decorador admin_required
def admin_required(f):
    """Decorador para requerir permisos de administrador"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            from flask import flash, redirect, url_for
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Modelos inicializados dinámicamente (evita importaciones circulares)
db = None
Event = None
EventImage = None
Discount = None
EventDiscount = None
ActivityLog = None
allowed_file = None


def init_models():
    """Importar modelos desde app una vez que la aplicación está lista."""
    global db, Event, EventImage, Discount, EventDiscount, ActivityLog, allowed_file
    try:
        from app import (
            db as _db,
            Event as _Event,
            EventImage as _EventImage,
            Discount as _Discount,
            EventDiscount as _EventDiscount,
            ActivityLog as _ActivityLog,
            allowed_file as _allowed_file,
        )
        db = _db
        Event = _Event
        EventImage = _EventImage
        Discount = _Discount
        EventDiscount = _EventDiscount
        ActivityLog = _ActivityLog
        allowed_file = _allowed_file
    except ImportError:
        pass


def ensure_models():
    if Event is None:
        init_models()


def _slugify(value: str) -> str:
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value or f"evento-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _unique_slug(base_slug: str, event_id=None) -> str:
    ensure_models()
    slug = base_slug
    counter = 1
    while True:
        query = Event.query.filter(Event.slug == slug)
        if event_id:
            query = query.filter(Event.id != event_id)
        exists = db.session.query(query.exists()).scalar()
        if not exists:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def _parse_datetime(field_name: str):
    value = request.form.get(field_name, '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


def _uploads_dir():
    base_dir = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'events')
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _remove_file_if_exists(path):
    if not path:
        return
    absolute_path = os.path.join(current_app.root_path, '..', path.lstrip('/'))
    if os.path.exists(absolute_path):
        try:
            os.remove(absolute_path)
        except OSError:
            pass


def _save_file(storage, prefix='event'):
    if not storage or storage.filename == '' or not allowed_file(storage.filename):
        return None
    filename = secure_filename(storage.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    unique_name = f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    folder = _uploads_dir()
    storage.save(os.path.join(folder, unique_name))
    return f"/static/uploads/events/{unique_name}"


def _serialize_event(event, membership_type=None):
    pricing = event.pricing_for_membership(membership_type)
    return {
        'id': event.id,
        'slug': event.slug,
        'title': event.title,
        'summary': event.summary,
        'category': event.category,
        'format': event.format,
        'tags': event.tags,
        'base_price': pricing['base_price'],
        'final_price': pricing['final_price'],
        'currency': event.currency,
        'start_date': event.start_date.isoformat() if event.start_date else None,
        'end_date': event.end_date.isoformat() if event.end_date else None,
        'registration_deadline': event.registration_deadline.isoformat() if event.registration_deadline else None,
        'cover_image': event.cover_url(),
        'is_virtual': event.is_virtual,
        'location': event.location,
        'country': event.country,
        'has_certificate': event.has_certificate,
        'certificate_instructions': event.certificate_instructions,
        'status': event.publish_status,
        'visibility': event.visibility,
        'featured': event.featured,
        'discount': {
            'name': pricing['discount'].name if pricing['discount'] else None,
            'value': pricing['discount'].value if pricing['discount'] else None,
            'type': pricing['discount'].discount_type if pricing['discount'] else None,
        } if pricing['discount'] else None,
    }


# Blueprints
events_bp = Blueprint('events', __name__, url_prefix='/events')
admin_events_bp = Blueprint('admin_events', __name__, url_prefix='/admin/events')
events_api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


# -----------------------------------------------------------------------------
# Rutas para miembros
# -----------------------------------------------------------------------------
@events_bp.route('/')
@login_required
def list_events():
    ensure_models()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    status = request.args.get('status', 'published')
    category = request.args.get('category', '').strip()
    search = request.args.get('q', '').strip()
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Event.title.ilike(like),
                Event.summary.ilike(like),
                Event.tags.ilike(like)
            )
        )
    
    events = query.order_by(Event.start_date.asc()).all()
    categories = sorted({evt.category for evt in events if evt.category})
    
    return render_template(
        'events/list.html',
        events=events,
        categories=categories,
        active_category=category,
        search=search,
        membership=membership,
        status=status,
        membership_type=membership_type
    )


@events_bp.route('/<string:slug>')
@login_required
def event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    pricing = event.pricing_for_membership(membership_type)
    return render_template(
        'events/detail.html',
        event=event,
        membership=membership,
        pricing=pricing
    )


# -----------------------------------------------------------------------------
# API JSON
# -----------------------------------------------------------------------------
@events_api_bp.route('/', methods=['GET'])
def api_events():
    ensure_models()
    status = request.args.get('status', 'published')
    limit = request.args.get('limit', type=int)
    membership_type = request.args.get('membership_type')
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    
    query = query.order_by(Event.start_date.asc())
    if limit:
        query = query.limit(limit)
    
    events = query.all()
    return jsonify({'events': [_serialize_event(evt, membership_type) for evt in events]})


@events_api_bp.route('/<string:slug>', methods=['GET'])
def api_event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership_type = request.args.get('membership_type')
    return jsonify({'event': _serialize_event(event, membership_type)})


# -----------------------------------------------------------------------------
# Panel Administrativo - Eventos
# -----------------------------------------------------------------------------
@admin_events_bp.route('/')
@admin_required
def admin_events_index():
    ensure_models()
    status = request.args.get('status', 'all')
    category = request.args.get('category', '').strip()
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)
    
    events = query.order_by(Event.start_date.desc()).all()
    stats = {
        'total': Event.query.count(),
        'published': Event.query.filter_by(publish_status='published').count(),
        'drafts': Event.query.filter_by(publish_status='draft').count(),
        'archived': Event.query.filter_by(publish_status='archived').count(),
    }
    
    return render_template(
        'admin/events/list.html',
        events=events,
        status=status,
        category=category,
        stats=stats
    )


@admin_events_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_event():
    ensure_models()
    discounts = Discount.query.order_by(Discount.name.asc()).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)
        
        slug = request.form.get('slug', '').strip() or _slugify(title)
        slug = _unique_slug(slug)
        
        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas de inicio y fin son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'error')
            return redirect(request.url)
        
        event = Event(
            title=title,
            slug=slug,
            summary=request.form.get('summary', '').strip(),
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'general').strip() or 'general',
            format=request.form.get('format', 'virtual').strip() or 'virtual',
            tags=request.form.get('tags', '').strip(),
            base_price=request.form.get('base_price', type=float) or 0.0,
            currency=request.form.get('currency', 'USD').upper(),
            registration_url=request.form.get('registration_url', '').strip(),
            contact_email=request.form.get('contact_email', '').strip(),
            contact_phone=request.form.get('contact_phone', '').strip(),
            location=request.form.get('location', '').strip(),
            country=request.form.get('country', '').strip(),
            is_virtual=bool(request.form.get('is_virtual')),
            has_certificate=bool(request.form.get('has_certificate')),
            certificate_instructions=request.form.get('certificate_instructions', '').strip(),
            capacity=request.form.get('capacity', type=int) or 0,
            visibility=request.form.get('visibility', 'members'),
            publish_status=request.form.get('publish_status', 'draft'),
            featured=bool(request.form.get('featured')),
            start_date=start_date,
            end_date=end_date,
            registration_deadline=_parse_datetime('registration_deadline'),
            created_by=current_user.id
        )
        
        db.session.add(event)
        db.session.flush()
        
        cover_path = _save_file(request.files.get('cover_image'), prefix='cover')
        if cover_path:
            event.cover_image = cover_path
        
        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=idx,
                    is_primary=False
                ))
        
        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            try:
                discount = Discount.query.get(int(discount_id))
            except (TypeError, ValueError):
                discount = None
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))
        
        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'create_event',
            'event',
            event.id,
            f'Se creó el evento {event.title}',
            request
        )
        flash('Evento creado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))
    
    default_start = (datetime.utcnow() + timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    default_end = default_start + timedelta(hours=2)
    
    return render_template(
        'admin/events/form.html',
        action='create',
        discounts=discounts,
        event=None,
        default_start=default_start,
        default_end=default_end
    )


@admin_events_bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    discounts = Discount.query.order_by(Discount.name.asc()).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)
        
        slug = request.form.get('slug', '').strip() or _slugify(title)
        event.slug = _unique_slug(slug, event_id=event.id)
        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'error')
            return redirect(request.url)
        
        event.title = title
        event.summary = request.form.get('summary', '').strip()
        event.description = request.form.get('description', '').strip()
        event.category = request.form.get('category', 'general').strip() or 'general'
        event.format = request.form.get('format', 'virtual').strip() or 'virtual'
        event.tags = request.form.get('tags', '').strip()
        event.base_price = request.form.get('base_price', type=float) or 0.0
        event.currency = request.form.get('currency', 'USD').upper()
        event.registration_url = request.form.get('registration_url', '').strip()
        event.contact_email = request.form.get('contact_email', '').strip()
        event.contact_phone = request.form.get('contact_phone', '').strip()
        event.location = request.form.get('location', '').strip()
        event.country = request.form.get('country', '').strip()
        event.is_virtual = bool(request.form.get('is_virtual'))
        event.has_certificate = bool(request.form.get('has_certificate'))
        event.certificate_instructions = request.form.get('certificate_instructions', '').strip()
        event.capacity = request.form.get('capacity', type=int) or 0
        event.visibility = request.form.get('visibility', 'members')
        event.publish_status = request.form.get('publish_status', 'draft')
        event.featured = bool(request.form.get('featured'))
        event.start_date = start_date
        event.end_date = end_date
        event.registration_deadline = _parse_datetime('registration_deadline')
        
        if request.form.get('remove_cover'):
            _remove_file_if_exists(event.cover_image)
            event.cover_image = None
        
        new_cover = _save_file(request.files.get('cover_image'), prefix='cover')
        if new_cover:
            _remove_file_if_exists(event.cover_image)
            event.cover_image = new_cover
        
        delete_ids = request.form.getlist('delete_images')
        for image_id in delete_ids:
            image = EventImage.query.filter_by(id=image_id, event_id=event.id).first()
            if image:
                _remove_file_if_exists(image.file_path)
                db.session.delete(image)
        
        current_order = len(event.images)
        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=current_order + idx,
                    is_primary=False
                ))
        
        # Actualizar descuentos
        EventDiscount.query.filter_by(event_id=event.id).delete()
        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            try:
                discount = Discount.query.get(int(discount_id))
            except (TypeError, ValueError):
                discount = None
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))
        
        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_event',
            'event',
            event.id,
            f'Se actualizó el evento {event.title}',
            request
        )
        flash('Evento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))
    
    return render_template(
        'admin/events/form.html',
        action='edit',
        discounts=discounts,
        event=event,
        default_start=event.start_date,
        default_end=event.end_date
    )


@admin_events_bp.route('/<int:event_id>/delete', methods=['POST'])
@admin_required
def delete_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    title = event.title
    
    # Borrar archivos asociados
    _remove_file_if_exists(event.cover_image)
    for image in event.images:
        _remove_file_if_exists(image.file_path)
    
    db.session.delete(event)
    db.session.commit()
    
    ActivityLog.log_activity(
        current_user.id,
        'delete_event',
        'event',
        event_id,
        f'Se eliminó el evento {title}',
        request
    )
    flash('Evento eliminado correctamente.', 'info')
    return redirect(url_for('admin_events.admin_events_index'))


# -----------------------------------------------------------------------------
# Panel Administrativo - Descuentos
# -----------------------------------------------------------------------------
@admin_events_bp.route('/discounts')
@admin_required
def discounts_index():
    ensure_models()
    discounts = Discount.query.order_by(Discount.created_at.desc()).all()
    return render_template('admin/events/discount_list.html', discounts=discounts)


@admin_events_bp.route('/discounts/create', methods=['GET', 'POST'])
@admin_required
def create_discount():
    ensure_models()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre es obligatorio.', 'error')
            return redirect(request.url)
        
        discount = Discount(
            name=name,
            code=request.form.get('code', '').strip() or None,
            description=request.form.get('description', '').strip(),
            discount_type=request.form.get('discount_type', 'percentage'),
            value=request.form.get('value', type=float) or 0.0,
            membership_tier=request.form.get('membership_tier', '').strip() or None,
            category=request.form.get('category', 'event'),
            applies_automatically='applies_automatically' in request.form,
            is_active='is_active' in request.form,
            max_uses=request.form.get('max_uses', type=int),
            start_date=_parse_datetime('start_date'),
            end_date=_parse_datetime('end_date')
        )
        db.session.add(discount)
        db.session.commit()
        
        ActivityLog.log_activity(
            current_user.id,
            'create_discount',
            'discount',
            discount.id,
            f'Se creó el descuento {discount.name}',
            request
        )
        flash('Descuento creado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))
    
    return render_template('admin/events/discount_form.html', action='create', discount=None)


@admin_events_bp.route('/discounts/<int:discount_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)
    
    if request.method == 'POST':
        discount.name = request.form.get('name', '').strip()
        discount.code = request.form.get('code', '').strip() or None
        discount.description = request.form.get('description', '').strip()
        discount.discount_type = request.form.get('discount_type', 'percentage')
        discount.value = request.form.get('value', type=float) or 0.0
        discount.membership_tier = request.form.get('membership_tier', '').strip() or None
        discount.category = request.form.get('category', 'event')
        discount.applies_automatically = 'applies_automatically' in request.form
        discount.is_active = 'is_active' in request.form
        discount.max_uses = request.form.get('max_uses', type=int)
        discount.start_date = _parse_datetime('start_date')
        discount.end_date = _parse_datetime('end_date')
        
        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_discount',
            'discount',
            discount.id,
            f'Se actualizó el descuento {discount.name}',
            request
        )
        flash('Descuento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))
    
    return render_template('admin/events/discount_form.html', action='edit', discount=discount)


@admin_events_bp.route('/discounts/<int:discount_id>/delete', methods=['POST'])
@admin_required
def delete_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)
    name = discount.name
    db.session.delete(discount)
    db.session.commit()
    
    ActivityLog.log_activity(
        current_user.id,
        'delete_discount',
        'discount',
        discount_id,
        f'Se eliminó el descuento {name}',
        request
    )
    flash('Descuento eliminado.', 'info')
    return redirect(url_for('admin_events.discounts_index'))
#!/usr/bin/env python3
"""
Rutas para la gestión de eventos y descuentos del ecosistema RELATIC.

Incluye:
- CRUD de eventos en el panel administrativo
- CRUD básico de descuentos reutilizables
- Endpoints públicos (miembros) y API JSON para consumir desde el frontend
"""

from datetime import datetime
import os
import re
import unicodedata

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from functools import wraps

# Decorador admin_required
def admin_required(f):
    """Decorador para requerir permisos de administrador"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_admin:
            from flask import flash, redirect, url_for
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Modelos y utilidades inicializados dinámicamente para evitar importaciones circulares
db = None
Event = None
EventImage = None
Discount = None
EventDiscount = None
ActivityLog = None
allowed_file = None


def init_models():
    """Importar modelos desde app una vez que la aplicación esté inicializada."""
    global db, Event, EventImage, Discount, EventDiscount, ActivityLog, allowed_file
    try:
        from app import (
            db as _db,
            Event as _Event,
            EventImage as _EventImage,
            Discount as _Discount,
            EventDiscount as _EventDiscount,
            ActivityLog as _ActivityLog,
            allowed_file as _allowed_file,
        )

        db = _db
        Event = _Event
        EventImage = _EventImage
        Discount = _Discount
        EventDiscount = _EventDiscount
        ActivityLog = _ActivityLog
        allowed_file = _allowed_file
    except ImportError:
        pass


def ensure_models():
    """Asegura que los modelos estén inicializados antes de usarlos."""
    if Event is None:
        init_models()


def _slugify(value: str) -> str:
    value = unicodedata.normalize('NFKD', value or '').encode('ascii', 'ignore').decode('ascii')
    value = value.lower()
    value = re.sub(r'[^a-z0-9]+', '-', value).strip('-')
    return value or f"evento-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"


def _unique_slug(base_slug: str, event_id=None) -> str:
    ensure_models()
    slug = base_slug
    counter = 1
    while True:
        query = Event.query.filter(Event.slug == slug)
        if event_id:
            query = query.filter(Event.id != event_id)
        exists = db.session.query(query.exists()).scalar()
        if not exists:
            return slug
        slug = f"{base_slug}-{counter}"
        counter += 1


def _parse_datetime(field_name: str):
    value = request.form.get(field_name, '').strip()
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M')
    except ValueError:
        return None


def _uploads_dir():
    base_dir = os.path.join(current_app.root_path, '..', 'static', 'uploads', 'events')
    os.makedirs(base_dir, exist_ok=True)
    return base_dir


def _save_file(storage, prefix='event'):
    if not storage or storage.filename == '' or not allowed_file(storage.filename):
        return None
    filename = secure_filename(storage.filename)
    ext = filename.rsplit('.', 1)[1].lower()
    unique_name = f"{prefix}_{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}.{ext}"
    folder = _uploads_dir()
    storage.save(os.path.join(folder, unique_name))
    return f"/static/uploads/events/{unique_name}"


def _serialize_event(event, membership_type=None):
    pricing = event.pricing_for_membership(membership_type)
    return {
        'id': event.id,
        'slug': event.slug,
        'title': event.title,
        'summary': event.summary,
        'category': event.category,
        'format': event.format,
        'tags': event.tags,
        'base_price': pricing['base_price'],
        'final_price': pricing['final_price'],
        'currency': event.currency,
        'start_date': event.start_date.isoformat() if event.start_date else None,
        'end_date': event.end_date.isoformat() if event.end_date else None,
        'registration_deadline': event.registration_deadline.isoformat() if event.registration_deadline else None,
        'cover_image': event.cover_url(),
        'is_virtual': event.is_virtual,
        'location': event.location,
        'country': event.country,
        'has_certificate': event.has_certificate,
        'certificate_instructions': event.certificate_instructions,
        'status': event.publish_status,
        'visibility': event.visibility,
        'featured': event.featured,
        'discount': {
            'name': pricing['discount'].name if pricing['discount'] else None,
            'value': pricing['discount'].value if pricing['discount'] else None,
            'type': pricing['discount'].discount_type if pricing['discount'] else None,
        } if pricing['discount'] else None,
    }


# Blueprints
events_bp = Blueprint('events', __name__, url_prefix='/events')
admin_events_bp = Blueprint('admin_events', __name__, url_prefix='/admin/events')
events_api_bp = Blueprint('events_api', __name__, url_prefix='/api/events')


# -----------------------------------------------------------------------------
# Rutas para miembros
# -----------------------------------------------------------------------------
@events_bp.route('/')
@login_required
def list_events():
    ensure_models()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    status = request.args.get('status', 'published')
    category = request.args.get('category', '').strip()
    search = request.args.get('q', '').strip()
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Event.title.ilike(like),
                Event.summary.ilike(like),
                Event.tags.ilike(like)
            )
        )
    
    events = query.order_by(Event.start_date.asc()).all()
    categories = sorted({evt.category for evt in events if evt.category})
    
    return render_template(
        'events/list.html',
        events=events,
        categories=categories,
        active_category=category,
        search=search,
        membership=membership,
        status=status
    )


@events_bp.route('/<string:slug>')
@login_required
def event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership = current_user.get_active_membership()
    membership_type = membership.membership_type if membership else None
    pricing = event.pricing_for_membership(membership_type)
    return render_template(
        'events/detail.html',
        event=event,
        membership=membership,
        pricing=pricing
    )


# -----------------------------------------------------------------------------
# API JSON
# -----------------------------------------------------------------------------
@events_api_bp.route('/', methods=['GET'])
def api_events():
    ensure_models()
    status = request.args.get('status', 'published')
    limit = request.args.get('limit', type=int)
    membership_type = request.args.get('membership_type')
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    
    query = query.order_by(Event.start_date.asc())
    if limit:
        query = query.limit(limit)
    
    events = query.all()
    return jsonify({'events': [_serialize_event(evt, membership_type) for evt in events]})


@events_api_bp.route('/<string:slug>', methods=['GET'])
def api_event_detail(slug):
    ensure_models()
    event = Event.query.filter_by(slug=slug).first_or_404()
    membership_type = request.args.get('membership_type')
    return jsonify({'event': _serialize_event(event, membership_type)})


# -----------------------------------------------------------------------------
# Panel Administrativo - Eventos
# -----------------------------------------------------------------------------
@admin_events_bp.route('/')
@admin_required
def admin_events_index():
    ensure_models()
    status = request.args.get('status', 'all')
    category = request.args.get('category', '').strip()
    
    query = Event.query
    if status != 'all':
        query = query.filter(Event.publish_status == status)
    if category:
        query = query.filter(Event.category == category)
    
    events = query.order_by(Event.start_date.desc()).all()
    stats = {
        'total': Event.query.count(),
        'published': Event.query.filter_by(publish_status='published').count(),
        'drafts': Event.query.filter_by(publish_status='draft').count(),
        'archived': Event.query.filter_by(publish_status='archived').count(),
    }
    
    return render_template(
        'admin/events/list.html',
        events=events,
        status=status,
        category=category,
        stats=stats
    )


@admin_events_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create_event():
    ensure_models()
    discounts = Discount.query.order_by(Discount.name.asc()).all()
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)
        
        slug = request.form.get('slug', '').strip() or _slugify(title)
        slug = _unique_slug(slug)
        
        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas de inicio y fin son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'error')
            return redirect(request.url)
        
        event = Event(
            title=title,
            slug=slug,
            summary=request.form.get('summary', '').strip(),
            description=request.form.get('description', '').strip(),
            category=request.form.get('category', 'general').strip() or 'general',
            format=request.form.get('format', 'virtual').strip() or 'virtual',
            tags=request.form.get('tags', '').strip(),
            base_price=request.form.get('base_price', type=float) or 0.0,
            currency=request.form.get('currency', 'USD').upper(),
            registration_url=request.form.get('registration_url', '').strip(),
            contact_email=request.form.get('contact_email', '').strip(),
            contact_phone=request.form.get('contact_phone', '').strip(),
            location=request.form.get('location', '').strip(),
            country=request.form.get('country', '').strip(),
            is_virtual=bool(request.form.get('is_virtual')),
            has_certificate=bool(request.form.get('has_certificate')),
            certificate_instructions=request.form.get('certificate_instructions', '').strip(),
            capacity=request.form.get('capacity', type=int) or 0,
            visibility=request.form.get('visibility', 'members'),
            publish_status=request.form.get('publish_status', 'draft'),
            featured=bool(request.form.get('featured')),
            start_date=start_date,
            end_date=end_date,
            registration_deadline=_parse_datetime('registration_deadline'),
            created_by=current_user.id
        )
        
        db.session.add(event)
        db.session.flush()
        
        cover_file = request.files.get('cover_image')
        cover_path = _save_file(cover_file, prefix='cover') if cover_file else None
        if cover_path:
            event.cover_image = cover_path
        
        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=idx,
                    is_primary=False
                ))
        
        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            discount = Discount.query.get(discount_id)
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))
        
        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'create_event',
            'event',
            event.id,
            f'Se creó el evento {event.title}',
            request
        )
        flash('Evento creado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))
    
    default_start = (datetime.utcnow() + timedelta(days=7)).replace(minute=0, second=0, microsecond=0)
    default_end = default_start + timedelta(hours=2)
    return render_template(
        'admin/events/form.html',
        action='create',
        event=None,
        discounts=discounts,
        default_start=default_start,
        default_end=default_end
    )


@admin_events_bp.route('/<int:event_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    discounts = Discount.query.order_by(Discount.name.asc()).all()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        if not title:
            flash('El título es obligatorio.', 'error')
            return redirect(request.url)

        slug = request.form.get('slug', '').strip() or _slugify(title)
        event.slug = _unique_slug(slug, event_id=event.id)

        start_date = _parse_datetime('start_date')
        end_date = _parse_datetime('end_date')
        if not start_date or not end_date:
            flash('Las fechas de inicio y fin son obligatorias.', 'error')
            return redirect(request.url)
        if end_date <= start_date:
            flash('La fecha de fin debe ser posterior a la fecha de inicio.', 'error')
            return redirect(request.url)

        event.title = title
        event.summary = request.form.get('summary', '').strip()
        event.description = request.form.get('description', '').strip()
        event.category = request.form.get('category', 'general').strip() or 'general'
        event.format = request.form.get('format', 'virtual').strip() or 'virtual'
        event.tags = request.form.get('tags', '').strip()
        event.base_price = request.form.get('base_price', type=float) or 0.0
        event.currency = request.form.get('currency', 'USD').upper()
        event.registration_url = request.form.get('registration_url', '').strip()
        event.contact_email = request.form.get('contact_email', '').strip()
        event.contact_phone = request.form.get('contact_phone', '').strip()
        event.location = request.form.get('location', '').strip()
        event.country = request.form.get('country', '').strip()
        event.is_virtual = bool(request.form.get('is_virtual'))
        event.has_certificate = bool(request.form.get('has_certificate'))
        event.certificate_instructions = request.form.get('certificate_instructions', '').strip()
        event.capacity = request.form.get('capacity', type=int) or 0
        event.visibility = request.form.get('visibility', 'members')
        event.publish_status = request.form.get('publish_status', 'draft')
        event.featured = bool(request.form.get('featured'))
        event.start_date = start_date
        event.end_date = end_date
        event.registration_deadline = _parse_datetime('registration_deadline')

        if request.form.get('remove_cover'):
            _remove_file_if_exists(event.cover_image)
            event.cover_image = None

        new_cover = _save_file(request.files.get('cover_image'), prefix='cover')
        if new_cover:
            _remove_file_if_exists(event.cover_image)
            event.cover_image = new_cover

        delete_ids = request.form.getlist('delete_images')
        for image_id in delete_ids:
            image = EventImage.query.filter_by(id=image_id, event_id=event.id).first()
            if image:
                _remove_file_if_exists(image.file_path)
                db.session.delete(image)

        current_order = len(event.images)
        gallery_files = request.files.getlist('gallery_images')
        for idx, file in enumerate(gallery_files):
            path = _save_file(file, prefix='gallery')
            if path:
                db.session.add(EventImage(
                    event_id=event.id,
                    file_path=path,
                    sort_order=current_order + idx,
                    is_primary=False
                ))

        EventDiscount.query.filter_by(event_id=event.id).delete()
        selected_discounts = request.form.getlist('discount_ids')
        for order, discount_id in enumerate(selected_discounts, start=1):
            discount = Discount.query.get(discount_id)
            if discount:
                db.session.add(EventDiscount(
                    event_id=event.id,
                    discount_id=discount.id,
                    priority=order
                ))

        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_event',
            'event',
            event.id,
            f'Se actualizó el evento {event.title}',
            request
        )
        flash('Evento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.admin_events_index'))

    return render_template(
        'admin/events/form.html',
        action='edit',
        event=event,
        discounts=discounts,
        default_start=event.start_date,
        default_end=event.end_date
    )


@admin_events_bp.route('/<int:event_id>/delete', methods=['POST'])
@admin_required
def delete_event(event_id):
    ensure_models()
    event = Event.query.get_or_404(event_id)
    title = event.title
    
    _remove_file_if_exists(event.cover_image)
    for image in event.images:
        _remove_file_if_exists(image.file_path)
        db.session.delete(image)
    
    db.session.delete(event)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'delete_event',
        'event',
        event_id,
        f'Evento eliminado: {title}',
        request
    )
    flash('Evento eliminado.', 'info')
    return redirect(url_for('admin_events.admin_events_index'))


# ------------------------------------------------------------------------------
# Panel Administrativo - Descuentos
# ------------------------------------------------------------------------------
@admin_events_bp.route('/discounts')
@admin_required
def discounts_index():
    ensure_models()
    discounts = Discount.query.order_by(Discount.created_at.desc()).all()
    return render_template('admin/events/discount_list.html', discounts=discounts)


@admin_events_bp.route('/discounts/create', methods=['GET', 'POST'])
@admin_required
def create_discount():
    ensure_models()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('El nombre es obligatorio.', 'error')
            return redirect(request.url)

        discount = Discount(
            name=name,
            code=request.form.get('code', '').strip() or None,
            description=request.form.get('description', '').strip(),
            discount_type=request.form.get('discount_type', 'percentage'),
            value=request.form.get('value', type=float) or 0.0,
            membership_tier=request.form.get('membership_tier', '').strip() or None,
            category=request.form.get('category', 'event'),
            applies_automatically='applies_automatically' in request.form,
            is_active='is_active' in request.form,
            max_uses=request.form.get('max_uses', type=int),
            start_date=_parse_datetime('start_date'),
            end_date=_parse_datetime('end_date')
        )
        db.session.add(discount)
        db.session.commit()

        ActivityLog.log_activity(
            current_user.id,
            'create_discount',
            'discount',
            discount.id,
            f'Descuento creado: {discount.name}',
            request
        )
        flash('Descuento creado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))

    return render_template('admin/events/discount_form.html', action='create', discount=None)


@admin_events_bp.route('/discounts/<int:discount_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)

    if request.method == 'POST':
        discount.name = request.form.get('name', '').strip()
        discount.code = request.form.get('code', '').strip() or None
        discount.description = request.form.get('description', '').strip()
        discount.discount_type = request.form.get('discount_type', 'percentage')
        discount.value = request.form.get('value', type=float) or 0.0
        discount.membership_tier = request.form.get('membership_tier', '').strip() or None
        discount.category = request.form.get('category', 'event')
        discount.applies_automatically = 'applies_automatically' in request.form
        discount.is_active = 'is_active' in request.form
        discount.max_uses = request.form.get('max_uses', type=int)
        discount.start_date = _parse_datetime('start_date')
        discount.end_date = _parse_datetime('end_date')

        db.session.commit()
        ActivityLog.log_activity(
            current_user.id,
            'update_discount',
            'discount',
            discount.id,
            f'Descuento actualizado: {discount.name}',
            request
        )
        flash('Descuento actualizado correctamente.', 'success')
        return redirect(url_for('admin_events.discounts_index'))

    return render_template('admin/events/discount_form.html', action='edit', discount=discount)


@admin_events_bp.route('/discounts/<int:discount_id>/delete', methods=['POST'])
@admin_required
def delete_discount(discount_id):
    ensure_models()
    discount = Discount.query.get_or_404(discount_id)
    name = discount.name
    db.session.delete(discount)
    db.session.commit()

    ActivityLog.log_activity(
        current_user.id,
        'delete_discount',
        'discount',
        discount_id,
        f'Descuento eliminado: {name}',
        request
    )
    flash('Descuento eliminado.', 'info')
    return redirect(url_for('admin_events.discounts_index'))

