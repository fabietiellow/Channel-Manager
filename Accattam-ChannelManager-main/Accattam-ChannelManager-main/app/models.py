from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.sql import func
from flask_login import UserMixin

db = SQLAlchemy()


class Shop(db.Model):
    """Rappresenta un negozio: ogni shop, in teoria, ha credenziali eBay proprie"""
    __tablename__ = 'shop'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    
    # Credenziali eBay (hardcoded per sandbox, ma idealmente separati per shop)
    ebay_app_id = db.Column(db.String(200))
    ebay_dev_id = db.Column(db.String(200))
    ebay_cert_id = db.Column(db.String(200))
    ebay_token = db.Column(db.Text)
    ebay_siteid = db.Column(db.String(10), default='0')
    
    # Credenziali Catawiki
    catawiki_api_key = db.Column(db.String(200))
    
    # Stato prodotto
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relazioni tra le classi
    users = db.relationship('User', backref='shop', lazy=True, cascade='all, delete-orphan')
    products = db.relationship('Product', backref='shop', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Shop {self.name}>'


class User(UserMixin, db.Model):
    """Utente associato a uno specifico shop"""
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    
    email = db.Column(db.String(100), nullable=False)
    password = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    # Ruolo nello shop (al momento sono di default employee, ma posso impostare altri
    role = db.Column(db.String(50), default='employee')  # admin, manager, employee
    
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Relazioni
    products = db.relationship('Product', backref='owner', lazy=True)
    
    # Email unica PER shop (due shop possono avere user con stessa email)
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'email', name='uq_shop_user_email'),
    )
    
    def __repr__(self):
        return f'<User {self.email} - Shop {self.shop_id}>'


class Product(db.Model):
    """Prodotto associato a shop e gestito da user"""
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    shop_id = db.Column(db.Integer, db.ForeignKey('shop.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reference = db.Column(db.String(50), nullable=False)
    
    # Campi comuni
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    category = db.Column(db.String(100), default='Bag')
    brand = db.Column(db.String(100), default="Unknown")
    condition = db.Column(db.String(50))
    color = db.Column(db.String(50), default="Black")
    material = db.Column(db.String(100), default="Leather")
    gender = db.Column(db.String(20), default="Unisex")
    price = db.Column(db.Float)
    
    # Tracking
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    
    # Tracking vendita eBay
    ebay_sold = db.Column(db.Boolean, default=False)
    ebay_sold_at = db.Column(db.DateTime, nullable=True)
    ebay_buyer_username = db.Column(db.String(100), nullable=True)
    ebay_order_id = db.Column(db.String(100), nullable=True)
    ebay_sale_price = db.Column(db.Float, nullable=True)
    
    # Relazioni
    ebay_data = db.relationship('ProductEbay', backref='product', uselist=False, cascade='all, delete-orphan')
    catawiki_data = db.relationship('ProductCatawiki', backref='product', uselist=False, cascade='all, delete-orphan')
    
    # Reference deve essere unica PER shop
    __table_args__ = (
        db.UniqueConstraint('shop_id', 'reference', name='uq_shop_reference'),
    )
    
    def to_ebay_dict(self):
        if not self.ebay_data:
            return None
        return self.ebay_data.to_dict(self)
    
    def to_catawiki_dict(self):
        if not self.catawiki_data:
            return None
        return self.catawiki_data.to_dict(self)
    
    def __repr__(self):
        return f'<Product {self.reference} - Shop {self.shop_id}>'


class ProductEbay(db.Model):
    """Dati specifici eBay"""
    __tablename__ = 'product_ebay'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    style = db.Column(db.String(50))
    ebay_item_id = db.Column(db.String(50), nullable=True)
    ebay_published_at = db.Column(db.DateTime, nullable=True)
    
    def to_dict(self, product):
        if product.gender == "Women":
            category_id = "169291"
            color_field = "Exterior Color"
            material_field = "Exterior Material"
        elif product.gender == "Men":
            category_id = "52357"
            color_field = "Color"
            material_field = "Material"
        else:
            category_id = "169291"
            color_field = "Exterior Color"
            material_field = "Exterior Material"
        
        return {
            "Item": {
                "Title": product.title,
                "Description": product.description,
                "PrimaryCategory": {"CategoryID": category_id},
                "StartPrice": str(product.price) if product.price else "1.00",
                "ConditionID": "1000" if product.condition == "New" else "3000",
                "Currency": "USD",
                "Country": "US",
                "ListingType": "FixedPriceItem",
                "ListingDuration": "GTC",
                "Quantity": 1,
                "DispatchTimeMax": 3,
                "PostalCode": "95125",
                "PictureDetails": {
                    "PictureURL": ["https://example.com/photo1.jpg"]
                },
                "ItemSpecifics": {
                    "NameValueList": [
                        {"Name": "Department", "Value": product.gender or "Unisex"},
                        {"Name": "Brand", "Value": product.brand},
                        {"Name": "Style", "Value": self.style},
                        {"Name": color_field, "Value": product.color},
                        {"Name": material_field, "Value": product.material},
                    ]
                },
                "ReturnPolicy": {
                    "ReturnsAcceptedOption": "ReturnsAccepted",
                    "RefundOption": "MoneyBack",
                    "ReturnsWithinOption": "Days_30",
                    "ShippingCostPaidByOption": "Buyer"
                },
                "ShippingDetails": {
                    "ShippingType": "Flat",
                    "ShippingServiceOptions": {
                        "ShippingServicePriority": 1,
                        "ShippingService": "USPSPriority",
                        "ShippingServiceCost": "5.00",
                        "ShippingServiceAdditionalCost": "0.00"
                    }
                }
            }
        }
    
    def __repr__(self):
        return f'<ProductEbay for product_id={self.product_id}>'


class ProductCatawiki(db.Model):
    """Dati specifici Catawiki"""
    __tablename__ = 'product_catawiki'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    
    height = db.Column(db.Float)
    width = db.Column(db.Float)
    era = db.Column(db.String(50))
    culture = db.Column(db.String(100))
    century_timeframe = db.Column(db.String(50))
    acquired_from = db.Column(db.String(100))
    year_acquired = db.Column(db.String(10))
    country_acquired_from = db.Column(db.String(100))
    previous_owner_acq_from = db.Column(db.String(100))
    previous_owner_year_acq = db.Column(db.String(10))
    previous_owner_country_acq = db.Column(db.String(100))
    legal_verify = db.Column(db.String(10), default="yes")
    catawiki_exported_at = db.Column(db.DateTime, nullable=True)
    shipping_italy = db.Column(db.Numeric(10, 2), default=5.00)
    shipping_eu = db.Column(db.Numeric(10, 2), default=12.00)
    shipping_row = db.Column(db.Numeric(10, 2), default=20.00)
    
    def to_dict(self, product):
        return {
            "reference": product.reference,
            "object_type": product.category or "Bag",
            "language": "English",
            "description": product.description or "",
            "material": product.material,
            "colour": product.color,
            "condition": product.condition or "Used",
            "gender": product.gender,
            "brand": product.brand,
            "era": self.era,
            "height": self.height,
            "width": self.width,
            "culture": self.culture,
            "century_timeframe": self.century_timeframe,
            "acquired_from": self.acquired_from,
            "year_acquired": self.year_acquired,
            "country_acquired_from": self.country_acquired_from,
            "Previous_owner_acq_from": self.previous_owner_acq_from,
            "Previous_owner_year_acq": self.previous_owner_year_acq,
            "Previous_owner_country_acq": self.previous_owner_country_acq,
            "Legal_verify": self.legal_verify,
            "photo_urls": ["https://example.com/photo1.jpg"],
            "estimated_value": product.price,
            "Shipping_italy": float(self.shipping_italy) if self.shipping_italy else 5,
            "Shipping_eu": float(self.shipping_eu) if self.shipping_eu else 12,
            "Shipping_row": float(self.shipping_row) if self.shipping_row else 20,
        }
    
    def __repr__(self):
        return f'<ProductCatawiki for product_id={self.product_id}>'
