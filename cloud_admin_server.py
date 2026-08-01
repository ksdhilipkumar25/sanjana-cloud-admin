# ══════════════════════════════════════════════════════════════════════
#  SANJANA SOFTWARE — 24/7 Cloud Owner Control Panel (Render.com)
# ══════════════════════════════════════════════════════════════════════
import os, sys, time, traceback
from datetime import datetime, date
from flask import Flask, request, jsonify, Response, redirect

app = Flask(__name__)

# Database configuration
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

tmp_dir = os.environ.get('TMPDIR') or os.environ.get('TEMP') or '/tmp'
db_file = os.path.join(tmp_dir, 'cloud_owner.db').replace('\\', '/')
app.config['SQLALCHEMY_DATABASE_URI']        = db_url or f'sqlite:///{db_file}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY']                     = 'sanjana-cloud-owner-secret-key-2026'

from flask_sqlalchemy import SQLAlchemy
db = SQLAlchemy(app)

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'dhilip@25')

# ── Cloud Models ──
class CloudShop(db.Model):
    __tablename__ = 'cloud_shop'
    id              = db.Column(db.Integer, primary_key=True)
    local_shop_id   = db.Column(db.Integer, index=True)
    shop_name       = db.Column(db.String(150), nullable=False)
    owner_name      = db.Column(db.String(100))
    email           = db.Column(db.String(120), index=True)
    phone           = db.Column(db.String(30))
    address         = db.Column(db.Text)
    approved        = db.Column(db.Boolean, default=True)
    is_stopped      = db.Column(db.Boolean, default=False)
    med_count       = db.Column(db.Integer, default=0)
    bill_count      = db.Column(db.Integer, default=0)
    today_bills     = db.Column(db.Integer, default=0)
    total_revenue   = db.Column(db.Float, default=0.0)
    today_revenue   = db.Column(db.Float, default=0.0)
    joined_on       = db.Column(db.String(50))
    license_end     = db.Column(db.String(50))
    last_heartbeat  = db.Column(db.DateTime, default=datetime.utcnow)
    login_time      = db.Column(db.String(50), default='-')

class CloudRenewal(db.Model):
    __tablename__ = 'cloud_renewal'
    id           = db.Column(db.Integer, primary_key=True)
    shop_id      = db.Column(db.Integer, index=True)
    shop_name    = db.Column(db.String(150))
    owner_name   = db.Column(db.String(100))
    email        = db.Column(db.String(120))
    phone        = db.Column(db.String(30))
    license_end  = db.Column(db.String(50))
    requested_at = db.Column(db.String(50))
    status       = db.Column(db.String(20), default='pending')

# Initialize DB once at startup
with app.app_context():
    db.create_all()

@app.after_request
def add_header(response):
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@app.errorhandler(Exception)
def handle_exception(e):
    tb = traceback.format_exc()
    print("[CLOUD ERROR]", tb)
    return f"""<div style="font-family:sans-serif;padding:30px;background:#0d1117;color:#ff7b72;min-height:100vh;">
      <h2>⚠️ Application Error</h2>
      <pre style="background:#161b22;padding:20px;border-radius:8px;overflow-x:auto;color:#c9d1d9;">{tb}</pre>
    </div>""", 500

@app.route('/')
def index():
    return redirect('/owner-admin')

@app.route('/owner-admin')
def owner_admin():
    # Look for admin.html in root directory or templates folder
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'admin.html'),
        os.path.join(os.path.dirname(__file__), 'templates', 'admin.html')
    ]
    for p in possible_paths:
        if os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                return Response(f.read(), mimetype='text/html')
    
    return Response("""<!DOCTYPE html>
<html><head><title>Sanjana Cloud Admin</title></head>
<body style="font-family:sans-serif;background:#080c12;color:#e8f0fe;text-align:center;padding:50px;">
  <h2>⚠️ admin.html File Not Found</h2>
  <p>Please upload <code>admin.html</code> to your GitHub repository root.</p>
</body></html>""", mimetype='text/html', status=404)

@app.route('/static/<path:filename>')
def serve_static(filename):
    static_dir = os.path.join(os.path.dirname(__file__), 'static')
    from flask import send_from_directory
    return send_from_directory(static_dir, filename)

# ── API for Shop Desktop App Heartbeat ──
@app.route('/api/sync/heartbeat', methods=['POST'])
def shop_heartbeat():
    data = request.json or {}
    email = data.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400

    shop = CloudShop.query.filter_by(email=email).first()
    if not shop:
        shop = CloudShop(email=email)
        db.session.add(shop)

    shop.local_shop_id  = data.get('shop_id')
    shop.shop_name      = data.get('shop_name', 'Pharmacy Shop')
    shop.owner_name     = data.get('owner_name', '')
    shop.phone          = data.get('phone', '')
    shop.address        = data.get('address', '')
    shop.approved       = data.get('approved', True)
    shop.med_count      = data.get('med_count', 0)
    shop.bill_count     = data.get('bill_count', 0)
    shop.today_bills    = data.get('today_bills', 0)
    shop.total_revenue  = data.get('total_revenue', 0.0)
    shop.today_revenue  = data.get('today_revenue', 0.0)
    shop.joined_on      = data.get('joined_on', 'N/A')
    shop.license_end    = data.get('license_end', 'N/A')
    shop.login_time     = data.get('login_time', '-')
    shop.last_heartbeat = datetime.utcnow()

    # Sync license renewal request if submitted from desktop software
    if data.get('has_renewal_request'):
        existing_renewal = CloudRenewal.query.filter_by(shop_id=shop.id, status='pending').first()
        if not existing_renewal:
            new_renewal = CloudRenewal(
                shop_id=shop.id,
                shop_name=shop.shop_name,
                owner_name=shop.owner_name,
                email=shop.email,
                phone=shop.phone,
                license_end=shop.license_end,
                requested_at=data.get('renewal_requested_at', datetime.utcnow().strftime('%Y-%m-%d %H:%M')),
                status='pending'
            )
            db.session.add(new_renewal)

    db.session.commit()

    return jsonify({
        'status': 'ok',
        'is_stopped': bool(shop.is_stopped),
        'approved': bool(shop.approved),
        'license_end': shop.license_end
    })

# ── API for Owner Dashboard ──
@app.route('/api/admin/shops', methods=['POST'])
def get_all_shops():
    if (request.json or {}).get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    shops = CloudShop.query.all()
    result = []
    now = datetime.utcnow()
    today_str = date.today().strftime('%Y-%m-%d')

    active_count = 0
    total_bills_all = 0
    today_bills_all = 0
    total_revenue_all = 0.0
    today_revenue_all = 0.0
    total_meds_all = 0
    expiring_soon = 0

    for s in shops:
        is_active = False
        if s.last_heartbeat:
            diff_secs = (now - s.last_heartbeat).total_seconds()
            if diff_secs <= 120:
                is_active = True
                active_count += 1

        days_left = 999
        if s.license_end and s.license_end != 'N/A':
            try:
                dt = datetime.strptime(s.license_end.split()[0], '%Y-%m-%d').date()
                days_left = (dt - date.today()).days
            except Exception:
                pass

        if 0 <= days_left <= 30:
            expiring_soon += 1

        total_bills_all   += (s.bill_count or 0)
        today_bills_all   += (s.today_bills or 0)
        total_revenue_all += (s.total_revenue or 0.0)
        today_revenue_all += (s.today_revenue or 0.0)
        total_meds_all    += (s.med_count or 0)

        latest_req = CloudRenewal.query.filter_by(shop_id=s.id).order_by(CloudRenewal.id.desc()).first()

        result.append({
            'id':             s.id,
            'shop_name':      s.shop_name,
            'owner_name':     s.owner_name,
            'email':          s.email,
            'phone':          s.phone,
            'address':        s.address,
            'approved':       s.approved,
            'is_stopped':     s.is_stopped,
            'med_count':      s.med_count,
            'bill_count':     s.bill_count,
            'today_bills':    s.today_bills,
            'total_revenue':  round(s.total_revenue or 0.0, 2),
            'today_revenue':  round(s.today_revenue or 0.0, 2),
            'joined_on':      s.joined_on,
            'license_end':    s.license_end,
            'license_days':   days_left,
            'renewal_status': latest_req.status if latest_req else None,
            'is_active':      is_active,
            'login_time':     s.login_time or '-'
        })

    pending_reqs = CloudRenewal.query.filter_by(status='pending').order_by(CloudRenewal.id.desc()).all()
    pending_renewals = []
    for req in pending_reqs:
        pending_renewals.append({
            'request_id':   req.id,
            'shop_id':      req.shop_id,
            'shop_name':    req.shop_name,
            'owner_name':   req.owner_name,
            'email':        req.email,
            'phone':        req.phone,
            'license_end':  req.license_end,
            'requested_at': req.requested_at
        })

    return jsonify({
        'shops':              result,
        'active_count':       active_count,
        'total_count':        len(shops),
        'pending_renewals':   pending_renewals,
        'total_bills_all':    total_bills_all,
        'today_bills_all':    today_bills_all,
        'total_revenue_all':  round(total_revenue_all, 2),
        'today_revenue_all':  round(today_revenue_all, 2),
        'total_meds_all':     total_meds_all,
        'expiring_soon':      expiring_soon,
        'today_str':          today_str
    })

@app.route('/api/admin/toggle-shop-stop', methods=['POST'])
def toggle_shop_stop():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    shop = CloudShop.query.get(data.get('shop_id'))
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404

    is_stopped = bool(data.get('is_stopped', True))
    shop.is_stopped = is_stopped
    db.session.commit()

    action_str = "STOPPED" if is_stopped else "ALLOWED"
    return jsonify({
        'message': f'Shop "{shop.shop_name}" access has been {action_str.lower()} successfully.',
        'is_stopped': is_stopped
    })

@app.route('/api/admin/approve-shop', methods=['POST'])
def approve_shop():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    shop = CloudShop.query.get(data.get('shop_id'))
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404
    shop.approved = True
    db.session.commit()
    return jsonify({'message': f'{shop.shop_name} has been approved!'})

@app.route('/api/admin/reject-shop', methods=['POST'])
def reject_shop():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    shop = CloudShop.query.get(data.get('shop_id'))
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404
    name = shop.shop_name
    db.session.delete(shop)
    db.session.commit()
    return jsonify({'message': f'{name} has been rejected.'})

@app.route('/api/admin/delete-shop', methods=['POST'])
def delete_shop():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    shop = CloudShop.query.get(data.get('shop_id'))
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404
    name = shop.shop_name
    db.session.delete(shop)
    db.session.commit()
    return jsonify({'message': f'"{name}" deleted.'})

@app.route('/api/admin/approve-license-renewal', methods=['POST'])
def approve_license_renewal():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    req_id = data.get('request_id')
    req = CloudRenewal.query.get(req_id) if req_id else None
    if not req:
        return jsonify({'error': 'Renewal request not found'}), 404

    shop = CloudShop.query.get(req.shop_id)
    if not shop:
        return jsonify({'error': 'Shop not found'}), 404

    # Extend license by 1 year
    try:
        current_end = datetime.strptime(shop.license_end.split()[0], '%Y-%m-%d').date()
    except Exception:
        current_end = date.today()
    new_end = current_end.replace(year=current_end.year + 1)
    shop.license_end = str(new_end)
    req.status = 'approved'
    db.session.commit()

    return jsonify({'message': f'License renewed for {shop.shop_name} until {new_end}!'})

@app.route('/api/admin/reject-license-renewal', methods=['POST'])
def reject_license_renewal():
    data = request.json or {}
    if data.get('password') != ADMIN_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401

    req_id = data.get('request_id')
    req = CloudRenewal.query.get(req_id) if req_id else None
    if not req:
        return jsonify({'error': 'Renewal request not found'}), 404

    req.status = 'rejected'
    db.session.commit()

    return jsonify({'message': f'Renewal request for {req.shop_name} rejected.'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
