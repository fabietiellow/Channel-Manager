from flask import Blueprint, send_file, render_template, request, redirect, url_for, flash, g
from pathlib import Path
from app.utils.store_services.catawiki_csv import write_catawiki_csv
from app.models import Product, ProductEbay, ProductCatawiki, db, User, Shop
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError
from datetime import datetime, timedelta
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from sqlalchemy.orm import joinedload
from decimal import Decimal
from functools import wraps
import os
import io

load_dotenv()
views_bp = Blueprint('views', __name__)

# Check current_user caricandone login e il suo shop
def shop_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_shop'):
            g.current_shop = Shop.query.get(current_user.shop_id)
            if not g.current_shop or not g.current_shop.is_active:
                flash('Shop non trovato o disattivato', 'error')
                logout_user()
                return redirect(url_for('views.login'))
        return f(*args, **kwargs)
    return decorated_function

# Funzione per eBay API con credenziali dello shop
def get_ebay_api(shop=None):
    """Restituisce API eBay con credenziali dello shop, in questo caso di .env"""
    return Trading(
        domain=os.getenv('EBAY_DOMAIN', 'api.sandbox.ebay.com'),
        config_file=None,
        appid=os.getenv('EBAY_APPID'),      
        devid=os.getenv('EBAY_DEVID'),      
        certid=os.getenv('EBAY_CERTID'),    
        token=os.getenv('EBAY_TOKEN'),      
        siteid='0',
        https=True,
        compatibility=os.getenv('EBAY_COMPATIBILITY', '967'),
    )

# ROUTE BASE
@views_bp.route("/", methods=['GET'])
def start():
    return "<p>It Works!</p>"

# ROUTE SHOP REGISTRATION
@views_bp.route("/shop/register")
def shop_register():
    return render_template('shop_register.html')

@views_bp.route("/shop/register", methods=['POST'])
def shop_register_post():
    shop_name = request.form.get('shop_name')
    shop_email = request.form.get('shop_email')
    admin_email = request.form.get('admin_email')
    admin_name = request.form.get('admin_name')
    admin_password = request.form.get('admin_password')
    
    # Credenziali eBay (Sono hardcoded per sandbox, ma basterebbe implementarle in get_ebay_api)
    ebay_app_id = request.form.get('ebay_app_id', '')
    ebay_dev_id = request.form.get('ebay_dev_id', '')
    ebay_cert_id = request.form.get('ebay_cert_id', '')
    ebay_token = request.form.get('ebay_token', '')
    
    # Validazione
    if not all([shop_name, shop_email, admin_email, admin_name, admin_password]):
        flash('Tutti i campi obbligatori devono essere compilati', 'error')
        return redirect(url_for('views.shop_register'))
    
    # Verifica se shop email esiste già
    existing_shop = Shop.query.filter_by(email=shop_email).first()
    if existing_shop:
        flash('Email shop già esistente', 'error')
        return redirect(url_for('views.shop_register'))
    
    try:
        # Crea Shop
        new_shop = Shop(
            name=shop_name,
            email=shop_email,
            ebay_app_id=ebay_app_id,
            ebay_dev_id=ebay_dev_id,
            ebay_cert_id=ebay_cert_id,
            ebay_token=ebay_token,
            is_active=True
        )
        db.session.add(new_shop)
        db.session.flush()  # Ottieni shop_id
        
        # Crea User Admin
        admin_user = User(
            shop_id=new_shop.id,
            email=admin_email,
            name=admin_name,
            password=generate_password_hash(admin_password, method='pbkdf2:sha256'),
            role='admin',
            is_active=True
        )
        db.session.add(admin_user)
        db.session.commit()
        
        flash(f'Shop "{shop_name}" registrato con successo! Effettua il login.', 'success')
        return redirect(url_for('views.login'))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Errore durante la registrazione: {str(e)}', 'error')
        return redirect(url_for('views.shop_register'))

# LOGIN
@views_bp.route("/login")
def login():
    return render_template('login.html')

@views_bp.route("/login", methods=['POST'])
def login_post():
    email = request.form.get('email')
    password = request.form.get('password')
    remember = True if request.form.get('remember') else False
    
    user = User.query.filter_by(email=email).first()
    
    # Verifica credenziali e shop attivo
    if not user or not check_password_hash(user.password, password):
        flash('Email o password non corretti', 'error')
        return redirect(url_for('views.login'))
    
    if not user.is_active:
        flash('Utente disattivato', 'error')
        return redirect(url_for('views.login'))
    
    if not user.shop.is_active:
        flash('Shop disattivato, contatta l\'amministratore', 'error')
        return redirect(url_for('views.login'))
    
    # Login riuscito
    login_user(user, remember=remember)
    flash(f'Benvenuto {user.name} - Shop: {user.shop.name}', 'success')
    return redirect(url_for('views.products_list'))

# ROUTE USER REGISTRATION IN SHOP ESISTENTE
@views_bp.route("/signup")
def signup():
    # Mostra lista shop attivi per selezione
    active_shops = Shop.query.filter_by(is_active=True).all()
    return render_template('signup.html', shops=active_shops)

@views_bp.route("/signup", methods=['POST'])
def signup_post():
    '''Prendi dati dal form di signup'''
    shop_id = request.form.get('shop_id')
    email = request.form.get('email')
    name = request.form.get('name')
    password = request.form.get('password')
    
    if not shop_id:
        flash('Devi selezionare uno shop', 'error')
        return redirect(url_for('views.signup'))
    
    # Verifica se email esiste già in QUESTO shop
    existing_user = User.query.filter_by(shop_id=shop_id, email=email).first()
    if existing_user:
        flash('Email già esistente in questo shop', 'error')
        return redirect(url_for('views.signup'))
    
    # Crea nuovo utente
    new_user = User(
        shop_id=int(shop_id),
        email=email,
        name=name,
        password=generate_password_hash(password, method='pbkdf2:sha256'),
        role='employee'
    )
    
    db.session.add(new_user)
    db.session.commit()
    
    flash('Registrazione completata, effettua il login', 'success')
    return redirect(url_for('views.login'))

# ROUTE LOGOUT
@views_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('views.login'))

# ROUTE LISTA PRODOTTI
@views_bp.route("/products", methods=["GET"])
@shop_required
def products_list():
    # Filtra per shop_id e user_id
    products = Product.query.options(
        joinedload(Product.ebay_data),
        joinedload(Product.catawiki_data)
    ).filter_by(
        shop_id=g.current_shop.id
    ).order_by(Product.created_at.desc()).all()
    
    return render_template("products_list.html", products=products)

# ROUTE ADD PRODUCT
@views_bp.route("/add-product", methods=['GET', 'POST'])
@shop_required
def add_product():
    if request.method == 'POST':
        reference = request.form.get('reference')
        title = request.form.get('title')
        
        if not reference or not title:
            flash("Errore: Reference e Title sono obbligatori!", 'error')
            return redirect(url_for('views.add_product'))
        
        # Check reference univoca PER SHOP
        existing = Product.query.filter_by(
            shop_id=g.current_shop.id,
            reference=reference
        ).first()
        if existing:
            flash(f"Errore: Reference '{reference}' già esistente in questo shop!", 'error')
            return redirect(url_for('views.add_product'))
        
        # Crea Product con shop_id
        new_product = Product(
            shop_id=g.current_shop.id,
            user_id=current_user.id,
            reference=reference,
            title=title,
            description=request.form.get('description'),
            category=request.form.get('category', 'Bag'),
            condition=request.form.get('condition'),
            price=float(request.form.get('price')) if request.form.get('price') else None,
            brand=request.form.get('brand', 'Unknown'),
            color=request.form.get('color', 'Black'),
            material=request.form.get('material', 'Leather'),
            gender=request.form.get('gender', 'Unisex')
        )
        db.session.add(new_product)
        db.session.flush()
        
        # Crea ProductEbay se abilitato
        if request.form.get('enable_ebay') == 'yes':
            ebay_data = ProductEbay(
                product_id=new_product.id,
                style=request.form.get('style')
            )
            db.session.add(ebay_data)
        
        # Crea ProductCatawiki se abilitato
        if request.form.get('enable_catawiki') == 'yes':
            catawiki_data = ProductCatawiki(
                product_id=new_product.id,
                height=float(request.form.get('height')) if request.form.get('height') else None,
                width=float(request.form.get('width')) if request.form.get('width') else None,
                era=request.form.get('era'),
                culture=request.form.get('culture'),
                century_timeframe=request.form.get('century_timeframe'),
                acquired_from=request.form.get('acquired_from'),
                year_acquired=request.form.get('year_acquired'),
                country_acquired_from=request.form.get('country_acquired_from'),
                previous_owner_acq_from=request.form.get('previous_owner_acq_from'),
                previous_owner_year_acq=request.form.get('previous_owner_year_acq'),
                previous_owner_country_acq=request.form.get('previous_owner_country_acq'),
                legal_verify=request.form.get('legal_verify', 'yes'),
                shipping_italy=Decimal(request.form.get('shipping_italy', 5.00)),
                shipping_eu=Decimal(request.form.get('shipping_eu', 12.00)),
                shipping_row=Decimal(request.form.get('shipping_row', 20.00)),
            )
            db.session.add(catawiki_data)
        
        db.session.commit()
        flash(f'Prodotto "{title}" aggiunto con successo!', 'success')
        return redirect(url_for('views.products_list'))
    
    return render_template('add_product.html')

# ROUTE EDIT PRODUCT
@views_bp.route("/edit-product/<reference>", methods=['GET', 'POST'])
@shop_required
def edit_product(reference):
    product = Product.query.options(
        joinedload(Product.ebay_data),
        joinedload(Product.catawiki_data)
    ).filter_by(
        shop_id=g.current_shop.id,
        reference=reference
    ).first_or_404()
    
    if request.method == 'POST':
        product.title = request.form.get('title')
        product.description = request.form.get('description')
        product.category = request.form.get('category')
        product.condition = request.form.get('condition')
        product.price = float(request.form.get('price')) if request.form.get('price') else None
        product.brand = request.form.get('brand', 'Unknown')
        product.color = request.form.get('color', 'Black')
        product.material = request.form.get('material', 'Leather')
        product.gender = request.form.get('gender', 'Unisex')
        
        if not product.title:
            flash('Il titolo è obbligatorio!', 'error')
            return redirect(url_for('views.edit_product', reference=reference))
        
        if product.ebay_data:
            product.ebay_data.style = request.form.get('style')
        
        if product.catawiki_data:
            product.catawiki_data.height = float(request.form.get('height')) if request.form.get('height') else None
            product.catawiki_data.width = float(request.form.get('width')) if request.form.get('width') else None
            product.catawiki_data.era = request.form.get('era')
            product.catawiki_data.culture = request.form.get('culture')
            product.catawiki_data.century_timeframe = request.form.get('century_timeframe')
            product.catawiki_data.acquired_from = request.form.get('acquired_from')
            product.catawiki_data.year_acquired = request.form.get('year_acquired')
            product.catawiki_data.country_acquired_from = request.form.get('country_acquired_from')
            product.catawiki_data.previous_owner_acq_from = request.form.get('previous_owner_acq_from')
            product.catawiki_data.previous_owner_year_acq = request.form.get('previous_owner_year_acq')
            product.catawiki_data.previous_owner_country_acq = request.form.get('previous_owner_country_acq')
            product.catawiki_data.legal_verify = request.form.get('legal_verify', 'yes')
            product.catawiki_data.shipping_italy = Decimal(request.form.get('shipping_italy', 5.00))
            product.catawiki_data.shipping_eu = Decimal(request.form.get('shipping_eu', 12.00))
            product.catawiki_data.shipping_row = Decimal(request.form.get('shipping_row', 20.00))
        
        db.session.commit()
        
        # Aggiorna su eBay se pubblicato
        if product.ebay_data and product.ebay_data.ebay_item_id:
            try:
                api = get_ebay_api()
                ebay_payload = {
                    "Item": {
                        "ItemID": product.ebay_data.ebay_item_id,
                        "Title": product.title,
                        "Description": product.description,
                        "StartPrice": str(product.price) if product.price else "1.00",
                        "ItemSpecifics": {
                            "NameValueList": [
                                {"Name": "Department", "Value": product.gender or "Unisex"},
                                {"Name": "Brand", "Value": product.brand},
                                {"Name": "Style", "Value": product.ebay_data.style or "Bag"},
                                {"Name": "Exterior Color", "Value": product.color},
                                {"Name": "Exterior Material", "Value": product.material},
                            ]
                        }
                    }
                }
                response = api.execute("ReviseItem", ebay_payload)
                if response.reply.Ack in ["Success", "Warning"]:
                    flash(f'Prodotto modificato nel database e su eBay!', 'success')
                else:
                    flash(f'Modificato nel database, ma errore eBay: {response.reply.Errors}', 'warning')
            except Exception as e:
                flash(f'Modificato nel database, ma errore eBay: {str(e)}', 'warning')
        else:
            flash(f'Prodotto "{product.title}" modificato con successo!', 'success')
        
        return redirect(url_for('views.products_list'))
    
    return render_template('edit_product.html', product=product)

# ROUTE DELETE PRODUCT DA DATABASE
@views_bp.route("/delete-product/<reference>", methods=['GET'])
@shop_required
def delete_product(reference):
    product = Product.query.options(
        joinedload(Product.ebay_data)
    ).filter_by(
        shop_id=g.current_shop.id,
        reference=reference
    ).first()
    
    if not product:
        flash(f'Prodotto non trovato!', 'error')
        return redirect(url_for('views.products_list'))
    
    if product.ebay_data and product.ebay_data.ebay_item_id:
        flash(f'Impossibile eliminare "{product.title}": ancora pubblicato su eBay!', 'error')
        return redirect(url_for('views.products_list'))
    
    product_title = product.title
    db.session.delete(product)
    db.session.commit()
    
    flash(f'Prodotto "{product_title}" eliminato con successo!', 'success')
    return redirect(url_for('views.products_list'))

# ROUTE EBAY LISTING
@views_bp.route("/generate-ebay-listing/<reference>", methods=['GET'])
@shop_required
def generate_ebay_listing(reference):
    product = Product.query.options(
        joinedload(Product.ebay_data)
    ).filter_by(
        shop_id=g.current_shop.id,
        reference=reference
    ).first_or_404()
    
    if product.ebay_data and product.ebay_data.ebay_item_id:
        flash(f'Prodotto già pubblicato su eBay (ItemID: {product.ebay_data.ebay_item_id})', 'warning')
        return redirect(url_for('views.products_list'))
    
    ebay_payload = product.to_ebay_dict()
    
    try:
        api = get_ebay_api()
        response = api.execute("AddItem", ebay_payload)
        
        if response.reply.Ack in ["Success", "Warning"]:
            item_id = response.reply.ItemID
            
            if not product.ebay_data:
                product.ebay_data = ProductEbay(product_id=product.id)
            
            product.ebay_data.ebay_item_id = item_id
            product.ebay_data.ebay_published_at = datetime.now()
            db.session.commit()
            
            flash(f'✅ Listing creato con successo! ItemID: {item_id}', 'success')
        else:
            errors = response.reply.Errors if hasattr(response.reply, 'Errors') else "Unknown error"
            flash(f'❌ Errore pubblicazione: {errors}', 'error')
    
    except ConnectionError as e:
        flash(f'❌ Errore connessione eBay: {str(e)}', 'error')
    except Exception as e:
        flash(f'❌ Errore generico: {str(e)}', 'error')
    
    return redirect(url_for('views.products_list'))

# ROUTE EBAY ELIMINA LISTING
@views_bp.route("/delete-ebay-listing/<item_id>", methods=['GET'])
@shop_required
def delete_ebay_listing(item_id):
    ebay_record = ProductEbay.query.filter_by(ebay_item_id=item_id).first()
    
    if not ebay_record or ebay_record.product.shop_id != g.current_shop.id:
        flash('Prodotto non trovato o non autorizzato!', 'error')
        return redirect(url_for('views.products_list'))
    
    product = ebay_record.product
    
    try:
        api = get_ebay_api()
        payload = {"ItemID": item_id, "EndingReason": "NotAvailable"}
        response = api.execute("EndItem", payload)
        
        if response.reply.Ack in ["Success", "Warning"]:
            ebay_record.ebay_item_id = None
            ebay_record.ebay_published_at = None
            db.session.commit()
            flash(f'✅ Listing eliminato da eBay!', 'success')
        else:
            error_msg = response.reply.Errors if hasattr(response.reply, 'Errors') else "Unknown error"
            flash(f'❌ Errore eliminazione: {error_msg}', 'error')
    
    except Exception as e:
        flash(f'❌ Errore: {str(e)}', 'error')
    
    return redirect(url_for('views.products_list'))

# ROUTE BULK UPLOAD EBAY
@views_bp.route("/publish-multiple-ebay", methods=['POST'])
@shop_required
def publish_multiple_ebay():
    selected_references = request.form.getlist('selected_products')
    
    if not selected_references:
        flash('Nessun prodotto selezionato!', 'warning')
        return redirect(url_for('views.products_list'))
    
    success_count = 0
    error_count = 0
    already_published = 0
    
    for reference in selected_references:
        product = Product.query.options(
            joinedload(Product.ebay_data)
        ).filter_by(
            shop_id=g.current_shop.id,
            reference=reference
        ).first()
        
        if not product:
            continue
        
        if product.ebay_data and product.ebay_data.ebay_item_id:
            already_published += 1
            continue
        
        try:
            api = get_ebay_api()
            ebay_payload = product.to_ebay_dict()
            response = api.execute("AddItem", ebay_payload)
            
            if response.reply.Ack in ["Success", "Warning"]:
                if not product.ebay_data:
                    product.ebay_data = ProductEbay(product_id=product.id)
                
                product.ebay_data.ebay_item_id = response.reply.ItemID
                product.ebay_data.ebay_published_at = datetime.now()
                db.session.commit()
                success_count += 1
            else:
                error_count += 1
        except Exception:
            error_count += 1
    
    if success_count > 0:
        flash(f'✅ {success_count} prodotti pubblicati!', 'success')
    if already_published > 0:
        flash(f'ℹ️ {already_published} già pubblicati (saltati).', 'warning')
    if error_count > 0:
        flash(f'❌ {error_count} prodotti con errori', 'error')
    
    return redirect(url_for('views.products_list'))

# ROUTE BULK DELETE EBAY
@views_bp.route("/delete-multiple-ebay", methods=['POST'])
@shop_required
def delete_multiple_ebay():
    selected_references = request.form.getlist('selected_products_delete')
    
    if not selected_references:
        flash('Nessun prodotto selezionato!', 'warning')
        return redirect(url_for('views.products_list'))
    
    success_count = 0
    error_count = 0
    not_published = 0
    
    for reference in selected_references:
        product = Product.query.options(
            joinedload(Product.ebay_data)
        ).filter_by(
            shop_id=g.current_shop.id,
            reference=reference
        ).first()
        
        if not product:
            continue
        
        if not product.ebay_data or not product.ebay_data.ebay_item_id:
            not_published += 1
            continue
        
        try:
            api = get_ebay_api()
            payload = {"ItemID": product.ebay_data.ebay_item_id, "EndingReason": "NotAvailable"}
            response = api.execute("EndItem", payload)
            
            if response.reply.Ack in ["Success", "Warning"]:
                product.ebay_data.ebay_item_id = None
                product.ebay_data.ebay_published_at = None
                db.session.commit()
                success_count += 1
            else:
                error_count += 1
        except Exception:
            error_count += 1
    
    if success_count > 0:
        flash(f'✅ {success_count} prodotti eliminati da eBay!', 'success')
    if not_published > 0:
        flash(f'ℹ️ {not_published} non pubblicati (saltati).', 'warning')
    if error_count > 0:
        flash(f'❌ {error_count} errori', 'error')
    
    return redirect(url_for('views.products_list'))

# ROUTE ELIMINAZIONE MULTIPLA DATABASE
@views_bp.route("/delete-multiple-products", methods=['POST'])
@shop_required
def delete_multiple_products():
    selected_references = request.form.getlist('selected_products_db')
    
    if not selected_references:
        flash('Nessun prodotto selezionato!', 'warning')
        return redirect(url_for('views.products_list'))
    
    success_count = 0
    blocked_count = 0
    
    for reference in selected_references:
        product = Product.query.options(
            joinedload(Product.ebay_data)
        ).filter_by(
            shop_id=g.current_shop.id,
            reference=reference
        ).first()
        
        if not product:
            continue
        
        if product.ebay_data and product.ebay_data.ebay_item_id:
            blocked_count += 1
            continue
        
        try:
            db.session.delete(product)
            db.session.commit()
            success_count += 1
        except Exception:
            pass
    
    if success_count > 0:
        flash(f'✅ {success_count} prodotti eliminati!', 'success')
    if blocked_count > 0:
        flash(f'❌ {blocked_count} NON eliminati (pubblicati su eBay)', 'error')
    
    return redirect(url_for('views.products_list'))

# ROUTE CREAZIONE CSV CATAWIKI
@views_bp.route('/catawiki/export', methods=['POST'])
@shop_required
def catawiki_export():
    product_ids = request.form.getlist('product_ids[]')
    
    if not product_ids:
        flash('Nessun prodotto selezionato', 'error')
        return redirect(url_for('views.products_list'))
    
    product_ids = [int(pid) for pid in product_ids]
    
    products = Product.query.options(
        joinedload(Product.catawiki_data)
    ).filter(
        Product.id.in_(product_ids),
        Product.shop_id == g.current_shop.id
    ).all()
    
    products_with_catawiki = [p for p in products if p.catawiki_data]
    
    if not products_with_catawiki:
        flash('Nessun prodotto con dati Catawiki', 'error')
        return redirect(url_for('views.products_list'))
    
    items_to_export = [p.to_catawiki_dict() for p in products_with_catawiki]
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    temp_path = Path(f"temp_catawiki_{timestamp}.csv")
    
    try:
        write_catawiki_csv(items_to_export, temp_path)
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            csv_content = f.read()
        
        mem_file = io.BytesIO(csv_content.encode('utf-8'))
        mem_file.seek(0)
        
        filename = f"catawiki_{len(items_to_export)}items_{timestamp}.csv"
        
        for p in products_with_catawiki:
            p.catawiki_data.catawiki_exported_at = datetime.now()
        db.session.commit()
        
        flash(f'✓ Esportati {len(items_to_export)} prodotti per Catawiki', 'success')
        
        return send_file(mem_file, mimetype='text/csv', as_attachment=True, download_name=filename)
    
    finally:
        if temp_path.exists():
            temp_path.unlink()

# FUNZIONE E ROUTE CHECK VENDITE PER USER
def check_ebay_sales_for_user(user_id):
    """Controlla vendite eBay per utente"""
    user = User.query.get(user_id)
    if not user:
        return 0, []
    
    published_products = Product.query.options(
        joinedload(Product.ebay_data)
    ).filter(
        Product.shop_id == user.shop_id,
        Product.ebay_sold == False
    ).join(ProductEbay).filter(
        ProductEbay.ebay_item_id.isnot(None)
    ).all()
    
    if not published_products:
        return 0, []
    
    try:
        shop = Shop.query.get(user.shop_id)
        api = get_ebay_api(shop)
        last_30_days = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        payload = {
            "CreateTimeFrom": last_30_days,
            "OrderRole": "Seller",
            "OrderStatus": "All",
            "Pagination": {"EntriesPerPage": 100, "PageNumber": 1}
        }
        
        response = api.execute("GetOrders", payload)
        
        if response.reply.Ack not in ["Success", "Warning"]:
            return 0, []
        
        if not hasattr(response.reply, 'OrderArray') or not hasattr(response.reply.OrderArray, 'Order'):
            return 0, []
        
        orders = response.reply.OrderArray.Order
        if not isinstance(orders, list):
            orders = [orders]
        
        new_sales_count = 0
        sold_products = []
        products_by_item_id = {p.ebay_data.ebay_item_id: p for p in published_products if p.ebay_data}
        
        for order in orders:
            if not hasattr(order, 'TransactionArray'):
                continue
            
            transactions = order.TransactionArray.Transaction
            if not isinstance(transactions, list):
                transactions = [transactions]
            
            for transaction in transactions:
                item_id = transaction.Item.ItemID
                
                if item_id in products_by_item_id:
                    product = products_by_item_id[item_id]
                    
                    try:
                        end_payload = {"ItemID": item_id, "EndingReason": "NotAvailable"}
                        api.execute("EndItem", end_payload)
                    except Exception:
                        pass
                    
                    product.ebay_sold = True
                    product.ebay_sold_at = datetime.now()
                    product.ebay_order_id = order.OrderID if hasattr(order, 'OrderID') else None
                    
                    if hasattr(transaction, 'TransactionPrice'):
                        product.ebay_sale_price = float(transaction.TransactionPrice.value)
                    else:
                        product.ebay_sale_price = product.price
                    
                    if hasattr(order, 'BuyerUserID'):
                        product.ebay_buyer_username = order.BuyerUserID
                    elif hasattr(transaction, 'Buyer'):
                        product.ebay_buyer_username = transaction.Buyer.UserID
                    else:
                        product.ebay_buyer_username = "Unknown"
                    
                    product.ebay_data.ebay_item_id = None
                    product.ebay_data.ebay_published_at = None
                    
                    new_sales_count += 1
                    sold_products.append(product)
                    del products_by_item_id[item_id]
        
        if new_sales_count > 0:
            db.session.commit()
        
        return new_sales_count, sold_products
    
    except Exception as e:
        print(f"Errore controllo vendite eBay: {str(e)}")
        return 0, []

@views_bp.route("/check-ebay-sales", methods=['GET'])
@shop_required
def check_ebay_sales():
    num_sales, sold_products = check_ebay_sales_for_user(current_user.id)
    
    if num_sales == 0:
        flash('✅ Nessuna nuova vendita su eBay.', 'info')
    else:
        products_list = ", ".join([f"{p.title} (€{p.ebay_sale_price})" for p in sold_products])
        flash(f'🎉 {num_sales} vendite: {products_list}', 'success')
    
    return redirect(url_for('views.products_list'))
